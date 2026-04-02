"""
backend/services/study_service.py
Stage 12 — User Study Module service layer.

Encapsulates all research-grade business logic:
  - Group assignment (50/50 randomised, persisted)
  - Deterministic problem order per session (seeded by session_id)
  - Eligibility gate (5 completed practice sessions required)
  - Test scoring (sandbox-only, no Brain A/B contamination)
  - CSV export aggregation for SPSS/R consumption

Scoring on the test path is DETERMINISTIC:
  score = (visible_score + hidden_score) / 2
Brain A/B are never called during tests to prevent experimental contamination.
"""

from __future__ import annotations

import csv
import io
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Generator

from sqlalchemy.orm import Session as DBSession

from models.problem import Problem
from models.study import StudyTestSession, StudyTestSubmission, StudyConfidenceSurvey, StudyGroup, TestType
from models.user import User
from services.sandbox import run_code

logger = logging.getLogger("study_service")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_PRACTICE_SESSIONS = 5   # eligibility gate for post-test
STUDY_TOPICS = ("arrays", "hash_maps", "recursion")


# ---------------------------------------------------------------------------
# Group assignment
# ---------------------------------------------------------------------------

def assign_group(user: User, db: DBSession) -> str:
    """
    Assign the user to 'control' or 'adaptlab' (50/50) if not already assigned.
    The assignment is persisted immediately so it survives page refreshes.
    Returns the group string.
    """
    if user.study_group:
        return user.study_group

    group = random.choice([StudyGroup.control.value, StudyGroup.adaptlab.value])
    user.study_group = group
    db.commit()
    db.refresh(user)
    logger.info("Assigned user %s to group '%s'.", user.id, group)
    return group


# ---------------------------------------------------------------------------
# Study problem fetching
# ---------------------------------------------------------------------------

def get_study_problems(db: DBSession) -> list[Problem]:
    """
    Return all problems with is_study_only=True, ordered by difficulty.
    These are the 10 fixed test-set problems.
    """
    return (
        db.query(Problem)
        .filter(Problem.is_study_only == True)   # noqa: E712
        .order_by(Problem.difficulty.asc())
        .all()
    )


def randomise_for_session(problems: list[Problem], session_id: int) -> list[Problem]:
    """
    Produce a session-specific randomised order.
    Uses session_id as the RNG seed so the order is reproducibly unique
    to each session without storing the full order (we store UUIDs, but
    this function can regenerate the order from an existing session's
    problem_order list as well).
    """
    rng = random.Random(session_id)
    shuffled = list(problems)
    rng.shuffle(shuffled)
    return shuffled


def problems_from_order(order: list[str], db: DBSession) -> list[Problem]:
    """
    Restore ordered problem list from a stored list of UUID strings.
    Preserves the original session order (no re-shuffle needed).
    """
    id_map: dict[str, Problem] = {}
    rows = db.query(Problem).filter(
        Problem.id.in_([uuid.UUID(oid) for oid in order])
    ).all()
    for r in rows:
        id_map[str(r.id)] = r
    return [id_map[oid] for oid in order if oid in id_map]


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

def start_test_session(
    user: User,
    test_type: str,
    db: DBSession,
) -> tuple[StudyTestSession, list[Problem]]:
    """
    Create a new test session and return it alongside the ordered problem list.
    Idempotent for open (not yet completed) sessions: returns the existing one.
    """
    # Check for an open session of this type
    existing = (
        db.query(StudyTestSession)
        .filter(
            StudyTestSession.user_id == user.id,
            StudyTestSession.test_type == test_type,
            StudyTestSession.completed_at == None,  # noqa: E711
        )
        .order_by(StudyTestSession.started_at.desc())
        .first()
    )
    if existing:
        problems = problems_from_order(existing.problem_order, db)
        return existing, problems

    study_problems = get_study_problems(db)
    if not study_problems:
        raise ValueError("No study problems found. Run scripts/seed_study.py first.")

    # Create session to obtain its integer ID (needed for RNG seed)
    session = StudyTestSession(
        user_id=user.id,
        test_type=test_type,
        problem_order=[],   # populated below
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.flush()   # populates session.id without committing

    ordered = randomise_for_session(study_problems, session.id)
    session.problem_order = [str(p.id) for p in ordered]
    db.commit()
    db.refresh(session)

    return session, ordered


def get_open_session(user_id: uuid.UUID, test_type: str, db: DBSession) -> StudyTestSession | None:
    return (
        db.query(StudyTestSession)
        .filter(
            StudyTestSession.user_id == user_id,
            StudyTestSession.test_type == test_type,
            StudyTestSession.completed_at == None,  # noqa: E711
        )
        .order_by(StudyTestSession.started_at.desc())
        .first()
    )


def get_latest_completed_session(
    user_id: uuid.UUID,
    test_type: str,
    db: DBSession,
) -> StudyTestSession | None:
    return (
        db.query(StudyTestSession)
        .filter(
            StudyTestSession.user_id == user_id,
            StudyTestSession.test_type == test_type,
            StudyTestSession.completed_at != None,  # noqa: E711
        )
        .order_by(StudyTestSession.started_at.desc())
        .first()
    )


def close_session_if_complete(session: StudyTestSession, db: DBSession) -> bool:
    """
    If all 10 study problems have a submission in this session, mark it
    completed and compute the aggregate score. Returns True if just closed.
    """
    total_problems = len(session.problem_order)
    submission_count = len(session.submissions)

    if submission_count < total_problems:
        return False

    scores = [s.hidden_score for s in session.submissions]
    session.total_score = sum(scores) / len(scores) if scores else 0.0
    session.completed_at = datetime.now(timezone.utc)
    db.commit()
    logger.info(
        "Session %d closed. total_score=%.4f", session.id, session.total_score
    )
    return True


# ---------------------------------------------------------------------------
# Eligibility gate
# ---------------------------------------------------------------------------

def count_practice_sessions(user_id: uuid.UUID, db: DBSession) -> int:
    """
    Return the number of completed practice sessions for this user.
    A 'practice session' is any Session row (not a StudyTestSession).
    For the control group: we count their normal Session rows.
    For the adaptlab group: same — Brain B interactions happen there.
    """
    from models.session import Session as PracticeSession
    return (
        db.query(PracticeSession)
        .filter(PracticeSession.user_id == user_id)
        .count()
    )


def check_posttest_eligibility(user_id: uuid.UUID, db: DBSession) -> tuple[bool, int]:
    """
    Returns (eligible: bool, practice_count: int).
    Eligible if practice_count >= REQUIRED_PRACTICE_SESSIONS.
    """
    count = count_practice_sessions(user_id, db)
    return count >= REQUIRED_PRACTICE_SESSIONS, count


# ---------------------------------------------------------------------------
# Test scoring (deterministic — no LLM)
# ---------------------------------------------------------------------------

def score_submission(
    session: StudyTestSession,
    problem: Problem,
    code: str,
    db: DBSession,
) -> StudyTestSubmission:
    """
    Run code against both test sets, record time_to_solve, persist.
    Returns the StudyTestSubmission row.
    Idempotent: if a submission for this (session, problem) already exists,
    return the existing one.
    """
    existing = (
        db.query(StudyTestSubmission)
        .filter(
            StudyTestSubmission.session_id == session.id,
            StudyTestSubmission.problem_id == problem.id,
        )
        .first()
    )
    if existing:
        logger.info(
            "Duplicate submission for session %d / problem %s — returning existing.",
            session.id, problem.id,
        )
        return existing

    # Timing
    now = datetime.now(timezone.utc)
    elapsed = (now - session.started_at).total_seconds()

    # Scoring
    visible_res = run_code(code, problem.visible_tests)
    hidden_res  = run_code(code, problem.hidden_tests)

    v_score = visible_res.get("score", 0.0)
    h_score = hidden_res.get("score", 0.0)

    sub = StudyTestSubmission(
        session_id=session.id,
        problem_id=problem.id,
        code=code,
        visible_score=v_score,
        hidden_score=h_score,
        time_to_solve_seconds=round(elapsed, 2),
        submitted_at=now,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    # Attempt to close the session if all problems answered
    db.refresh(session)
    close_session_if_complete(session, db)

    return sub


# ---------------------------------------------------------------------------
# Confidence survey
# ---------------------------------------------------------------------------

def save_confidence(
    user_id: uuid.UUID,
    session_id: int,
    rating: int,
    db: DBSession,
) -> StudyConfidenceSurvey:
    """
    Persist a Likert rating (1–5) for a test session.
    Raises ValueError if rating is out of bounds.
    """
    if not (1 <= rating <= 5):
        raise ValueError(f"Rating must be 1–5, got {rating}.")

    row = StudyConfidenceSurvey(
        user_id=user_id,
        session_id=session_id,
        rating=rating,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# CSV export — ready for SPSS/R
# ---------------------------------------------------------------------------

def generate_export_csv(db: DBSession) -> Generator[str, None, None]:
    """
    Streaming CSV generator yielding rows one at a time to avoid loading
    the entire dataset into memory.

    Columns match the spec exactly:
      user_id, group, pre_score, post_score, avg_time, hint_rate,
      avg_confidence, start_date, end_date

    Notes:
      - hint_rate is 0.0 for all records in this implementation (hint
        tracking not wired in test path; field kept for SPSS compatibility).
      - avg_confidence = mean of StudyConfidenceSurvey.rating for each user,
        normalised to 0–1 range (divide by 5).
      - pre_score / post_score = StudyTestSession.total_score (mean hidden_score).
      - avg_time = mean(time_to_solve_seconds) across all test submissions.
    """
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "user_id", "group", "pre_score", "post_score",
            "avg_time", "hint_rate", "avg_confidence",
            "start_date", "end_date",
        ],
        lineterminator="\r\n",
    )
    writer.writeheader()
    yield output.getvalue()
    output.truncate(0)
    output.seek(0)

    # Fetch all users who have started at least one study session
    users_with_sessions = (
        db.query(User)
        .join(StudyTestSession, StudyTestSession.user_id == User.id)
        .distinct()
        .all()
    )

    for user in users_with_sessions:
        pre_session  = get_latest_completed_session(user.id, "pre",  db)
        post_session = get_latest_completed_session(user.id, "post", db)

        # Build submission aggregates across both test types
        all_subs = (
            db.query(StudyTestSubmission)
            .join(StudyTestSession, StudyTestSubmission.session_id == StudyTestSession.id)
            .filter(StudyTestSession.user_id == user.id)
            .all()
        )

        times = [s.time_to_solve_seconds for s in all_subs if s.time_to_solve_seconds is not None]
        avg_time = round(sum(times) / len(times), 2) if times else None

        # Confidence: normalise 1-5 → 0.0-1.0
        surveys = (
            db.query(StudyConfidenceSurvey)
            .filter(StudyConfidenceSurvey.user_id == user.id)
            .all()
        )
        avg_confidence = None
        if surveys:
            avg_confidence = round(sum(s.rating for s in surveys) / (5 * len(surveys)), 4)

        # Dates: earliest started_at, latest completed_at across all sessions
        all_sessions = (
            db.query(StudyTestSession)
            .filter(StudyTestSession.user_id == user.id)
            .all()
        )
        start_date = min((s.started_at for s in all_sessions), default=None)
        end_date   = max(
            (s.completed_at for s in all_sessions if s.completed_at),
            default=None,
        )

        row = {
            "user_id":         str(user.id),
            "group":           user.study_group or "",
            "pre_score":       round(pre_session.total_score,  4) if pre_session  and pre_session.total_score  is not None else "",
            "post_score":      round(post_session.total_score, 4) if post_session and post_session.total_score is not None else "",
            "avg_time":        avg_time if avg_time is not None else "",
            "hint_rate":       "0.0",   # hint tracking reserved for future extension
            "avg_confidence":  avg_confidence if avg_confidence is not None else "",
            "start_date":      start_date.isoformat()  if start_date else "",
            "end_date":        end_date.isoformat()    if end_date   else "",
        }

        writer.writerow(row)
        yield output.getvalue()
        output.truncate(0)
        output.seek(0)
