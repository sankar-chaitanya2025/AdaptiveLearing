"""
routers/submissions.py
Extended for Stage 13: fatigue detection integrated into the submission flow.

Changes from previous version:
  - SubmissionRequest now accepts an optional session_id (UUID string).
  - After scoring, check_and_update_fatigue() is called when a session_id
    is supplied and the session exists.
  - select_problem() receives fatigue_mu from the session's fatigue state.
  - Response includes fatigue_state dict so the frontend knows to display
    the "easier problem" prompt.
  - Study test sessions are EXCLUDED from fatigue detection (is_study_only
    problems flow through /study/* endpoints, not here).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import uuid

from database import SessionLocal
from models.submission import Submission
from models.session import Session as PracticeSession
from services.problem_service import get_problem_by_id, get_problems, select_problem
from services.capability_service import update_capability
from services.sandbox import run_code
from services.fatigue_service import check_and_update_fatigue, effective_mu, NORMAL_MU
from ai.brain_a import evaluate_submission
from ai.brain_b import BrainB

router = APIRouter(prefix="/submissions", tags=["submissions"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class SubmissionRequest(BaseModel):
    user_id: str
    problem_id: str
    code: str
    # Stage 13: optional session_id enables fatigue-aware problem selection.
    # Pass the UUID of the active practice Session row.
    # Omit (or pass null) for sessionless submissions — behaviour unchanged.
    session_id: Optional[str] = None


@router.post("")
async def create_submission(request: SubmissionRequest, db: Session = Depends(get_db)):
    try:
        user_uuid    = uuid.UUID(request.user_id)
        problem_uuid = uuid.UUID(request.problem_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    # ── Resolve practice session (Stage 13) ───────────────────────────────
    practice_session: Optional[PracticeSession] = None
    if request.session_id:
        try:
            sid = uuid.UUID(request.session_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid session_id UUID format")

        practice_session = (
            db.query(PracticeSession)
            .filter(PracticeSession.id == sid, PracticeSession.user_id == user_uuid)
            .first()
        )
        # Silently ignore invalid session_id — don't break the submission flow

    # ── Problem lookup ─────────────────────────────────────────────────────
    problem = get_problem_by_id(db, request.problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    # Reject study-only problems from the normal submission path
    if getattr(problem, "is_study_only", False):
        raise HTTPException(
            status_code=400,
            detail="Study problems must be submitted via /study/submit-test.",
        )

    # ── Sandbox scoring ───────────────────────────────────────────────────
    visible_res = run_code(request.code, problem.visible_tests)
    if visible_res.get("error") and visible_res["error"] not in ("timeout", "no output", "parse error"):
        raise HTTPException(status_code=500, detail="Sandbox error: " + visible_res["error"])

    hidden_res = run_code(request.code, problem.hidden_tests)
    if hidden_res.get("error") and hidden_res["error"] not in ("timeout", "no output", "parse error"):
        raise HTTPException(status_code=500, detail="Sandbox error: " + hidden_res["error"])

    visible_score = visible_res.get("score", 0.0)
    hidden_score  = hidden_res.get("score", 0.0)

    gamed = False
    if visible_score > 0.8 and hidden_score < 0.3:
        gamed = True

    # ── Capability update ─────────────────────────────────────────────────
    if not gamed:
        update_capability(
            user_id=user_uuid,
            topic=problem.topic,
            submission_score=hidden_score,
            time_taken=30.0,
            time_limit=120.0,
            hint_used=False,
            attempt_num=1,
            db=db,
        )

    # ── Stage 13: Fatigue detection ───────────────────────────────────────
    fatigue_result = None
    if practice_session is not None and not gamed:
        fatigue_result = check_and_update_fatigue(
            session=practice_session,
            latest_hidden_score=hidden_score,
            db=db,
        )

    # ── Brain A evaluation ────────────────────────────────────────────────
    student_vector  = {problem.topic: hidden_score}
    sandbox_result  = {"visible": visible_res, "hidden": hidden_res}

    brain_a_result = await evaluate_submission(
        problem=problem,
        student_vector=student_vector,
        code=request.code,
        sandbox_result=sandbox_result,
    )

    # ── Brain B Socratic pipeline ─────────────────────────────────────────
    brain_b_data  = None
    plato_logged  = False
    if brain_a_result.call_brain_b:
        brain_b = BrainB()
        brain_b_data = await brain_b.full_pipeline(
            problem=problem,
            code=request.code,
            sandbox_result=sandbox_result,
            brain_a_failure_mode=brain_a_result.failure_mode,
            db=db,
        )
        plato_logged = brain_b_data.get("refined_problem") is not None

    # ── Next-problem selection (fatigue-aware μ) ──────────────────────────
    # Resolve fatigue_mu from the live session state after the fatigue check.
    # effective_mu() reads session.fatigued (already updated above in DB).
    if practice_session is not None:
        db.refresh(practice_session)  # ensure we see the committed fatigue state
    fatigue_mu = effective_mu(practice_session)

    available_problems = get_problems(db)
    next_problem = select_problem(
        student_vector=student_vector,
        available_problems=available_problems,
        target_topic=problem.topic,
        fatigue_mu=fatigue_mu,          # Stage 13 core integration
    )
    next_problem_id = str(next_problem["id"]) if next_problem else None

    # ── Persist submission ────────────────────────────────────────────────
    submission = Submission(
        user_id=user_uuid,
        problem_id=problem_uuid,
        code=request.code,
        visible_score=visible_score,
        hidden_score=hidden_score,
        brain_a_feedback=brain_a_result.feedback,
        gamed=gamed,
    )
    db.add(submission)
    db.commit()

    # ── Build response ────────────────────────────────────────────────────
    response = {
        "visible_score":  visible_score,
        "hidden_score":   hidden_score,
        "gamed":          gamed,
        "feedback":       brain_a_result.feedback,
        "call_brain_b":   brain_a_result.call_brain_b,
        "failure_mode":   brain_a_result.failure_mode,
        "next_problem_id": next_problem_id,
        # Stage 13: fatigue state for frontend display / adaptation
        "fatigue_state": (
            {
                "fatigued":               fatigue_result.fatigued,
                "message":                fatigue_result.message,
                "recommendation":         fatigue_result.recommendation,
                "target_mu":              fatigue_result.target_mu,
                "consecutive_successes":  fatigue_result.consecutive_successes,
                "reset_occurred":         fatigue_result.reset_occurred,
                "avg_window":             fatigue_result.avg_window,
                "trend":                  fatigue_result.trend,
            }
            if fatigue_result is not None
            else None
        ),
    }

    if brain_b_data:
        response["brain_b"]      = brain_b_data
        response["plato_logged"] = plato_logged

    return response
