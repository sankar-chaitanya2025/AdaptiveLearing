"""
backend/api/study.py
Stage 12 — User Study Module API router.

Endpoints:
  POST /study/pre-test              — start / resume a pre-test session
  POST /study/submit-test/{pid}     — evaluate one problem submission
  POST /study/confidence            — record a Likert confidence rating
  POST /study/post-test             — check eligibility, start post-test
  GET  /study/export                — stream CSV (instructor/admin only)

Auth: all endpoints require a user_id in the request body.
      /export additionally requires role == "instructor".

NOTE: This project does not yet have JWT middleware, so auth is implemented
as a user_id lookup dependency — matching the pattern in submissions.py and
capability.py.  Swap for Header-based JWT when auth middleware is wired.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session as DBSession

from database import get_db
from models.user import User, UserRole
from services import study_service

logger = logging.getLogger("study.api")

router = APIRouter(prefix="/study", tags=["study"])


# ---------------------------------------------------------------------------
# Helpers / dependencies
# ---------------------------------------------------------------------------

def _get_user(user_id: uuid.UUID, db: DBSession) -> User:
    """Fetch user or raise 404."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")
    return user


def _require_instructor(user: User) -> None:
    """Raise 403 if user is not an instructor."""
    if user.role != UserRole.instructor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is restricted to instructors.",
        )


def _problem_to_dict(problem) -> dict[str, Any]:
    """Serialise a Problem ORM row into the API response shape."""
    return {
        "id":          str(problem.id),
        "title":       problem.title,
        "topic":       problem.topic,
        "difficulty":  problem.difficulty,
        "statement":   problem.statement,
        "visible_tests": problem.visible_tests,
    }


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class PreTestRequest(BaseModel):
    user_id: uuid.UUID


class PreTestResponse(BaseModel):
    session_id: int
    test_type: str
    group: str
    problems: list[dict]
    started_at: str


class SubmitTestRequest(BaseModel):
    user_id:    uuid.UUID
    session_id: int
    code:       str = Field(..., min_length=1)


class SubmitTestResponse(BaseModel):
    submission_id:        str
    problem_id:           str
    visible_score:        float
    hidden_score:         float
    combined_score:       float
    time_to_solve_seconds: float | None
    session_complete:     bool
    session_total_score:  float | None


class ConfidenceRequest(BaseModel):
    user_id:    uuid.UUID
    session_id: int
    rating:     int = Field(..., ge=1, le=5)


class ConfidenceResponse(BaseModel):
    survey_id:  int
    session_id: int
    rating:     int
    message:    str


class PostTestRequest(BaseModel):
    user_id: uuid.UUID


class PostTestResponse(BaseModel):
    session_id:       int
    test_type:        str
    group:            str
    problems:         list[dict]
    started_at:       str
    practice_sessions: int


class ExportRequest(BaseModel):
    """Query params are passed as body for simplicity (no JWT in project yet)."""
    user_id: uuid.UUID


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/pre-test", response_model=PreTestResponse, status_code=201)
def start_pre_test(
    body: PreTestRequest,
    db:   DBSession = Depends(get_db),
) -> PreTestResponse:
    """
    Start (or resume) a pre-test session for the given user.

    - Assigns study group if not yet set (50/50 random).
    - Returns 10 study problems in a session-unique randomised order.
    - Idempotent: an existing open pre-test session is returned as-is.
    """
    user  = _get_user(body.user_id, db)
    group = study_service.assign_group(user, db)

    session, problems = study_service.start_test_session(user, "pre", db)

    return PreTestResponse(
        session_id=session.id,
        test_type="pre",
        group=group,
        problems=[_problem_to_dict(p) for p in problems],
        started_at=session.started_at.isoformat(),
    )


@router.post(
    "/submit-test/{problem_id}",
    response_model=SubmitTestResponse,
    status_code=200,
)
def submit_test_problem(
    problem_id: uuid.UUID,
    body: SubmitTestRequest,
    db:   DBSession = Depends(get_db),
) -> SubmitTestResponse:
    """
    Evaluate a student's code submission for one study test problem.

    - Scoring is DETERMINISTIC (sandbox only; no Brain A/B).
    - Records time_to_solve as delta from session.started_at.
    - Returns combined_score = (visible + hidden) / 2.
    - If all 10 problems answered, closes the session and computes total_score.
    """
    user = _get_user(body.user_id, db)

    # Resolve the open session
    from models.study import StudyTestSession
    session = (
        db.query(StudyTestSession)
        .filter(
            StudyTestSession.id      == body.session_id,
            StudyTestSession.user_id == user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Study test session {body.session_id} not found for this user.",
        )
    if session.completed_at is not None:
        raise HTTPException(
            status_code=400,
            detail="This test session is already completed.",
        )

    # Verify the problem belongs to the study set
    from models.problem import Problem
    problem = (
        db.query(Problem)
        .filter(Problem.id == problem_id, Problem.is_study_only == True)  # noqa: E712
        .first()
    )
    if not problem:
        raise HTTPException(
            status_code=404,
            detail=f"Study problem {problem_id} not found.",
        )

    # Verify problem is in this session's order
    if str(problem_id) not in session.problem_order:
        raise HTTPException(
            status_code=400,
            detail=f"Problem {problem_id} is not part of session {session.id}.",
        )

    sub = study_service.score_submission(session, problem, body.code, db)

    db.refresh(session)
    return SubmitTestResponse(
        submission_id=str(sub.id),
        problem_id=str(problem_id),
        visible_score=sub.visible_score,
        hidden_score=sub.hidden_score,
        combined_score=round((sub.visible_score + sub.hidden_score) / 2, 4),
        time_to_solve_seconds=sub.time_to_solve_seconds,
        session_complete=session.completed_at is not None,
        session_total_score=round(session.total_score, 4) if session.total_score is not None else None,
    )


@router.post("/confidence", response_model=ConfidenceResponse, status_code=201)
def submit_confidence(
    body: ConfidenceRequest,
    db:   DBSession = Depends(get_db),
) -> ConfidenceResponse:
    """
    Record a Likert confidence rating (1–5) for a test session.

    Multiple ratings per session are allowed (e.g. per-problem confidence);
    the export averages all ratings for a user.
    """
    user = _get_user(body.user_id, db)

    try:
        survey = study_service.save_confidence(user.id, body.session_id, body.rating, db)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ConfidenceResponse(
        survey_id=survey.id,
        session_id=survey.session_id,
        rating=survey.rating,
        message="Confidence rating saved.",
    )


@router.post("/post-test", response_model=PostTestResponse, status_code=201)
def start_post_test(
    body: PostTestRequest,
    db:   DBSession = Depends(get_db),
) -> PostTestResponse:
    """
    Unlock and start the post-test for a user.

    Eligibility gate: the user must have ≥ 5 completed practice sessions.
    Returns 403 with remaining count if gate is not met.

    The 10 problems are re-randomised with the new session id as seed —
    a different order from the pre-test ensures order effects are controlled.
    """
    user = _get_user(body.user_id, db)
    group = user.study_group or study_service.assign_group(user, db)

    eligible, count = study_service.check_posttest_eligibility(user.id, db)
    if not eligible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Post-test locked. You need {study_service.REQUIRED_PRACTICE_SESSIONS} "
                f"practice sessions; you have completed {count}."
            ),
        )

    session, problems = study_service.start_test_session(user, "post", db)

    return PostTestResponse(
        session_id=session.id,
        test_type="post",
        group=group,
        problems=[_problem_to_dict(p) for p in problems],
        started_at=session.started_at.isoformat(),
        practice_sessions=count,
    )


@router.get("/export")
def export_csv(
    user_id: uuid.UUID,
    db: DBSession = Depends(get_db),
) -> StreamingResponse:
    """
    Stream a CSV of all study results.
    Restricted to users with role == instructor.

    Columns: user_id, group, pre_score, post_score, avg_time,
             hint_rate, avg_confidence, start_date, end_date

    The CSV is streamed row-by-row to handle large cohorts without OOM.
    Load directly into SPSS/R with read.csv() or pd.read_csv().
    """
    requester = _get_user(user_id, db)
    _require_instructor(requester)

    def _stream():
        yield from study_service.generate_export_csv(db)

    filename = f"adaptlab_study_export_{uuid.uuid4().hex[:8]}.csv"
    return StreamingResponse(
        _stream(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
