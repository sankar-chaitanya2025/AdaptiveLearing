"""
backend/services/fatigue_service.py
Stage 13 — Cognitive Fatigue Detection Service.

Implements the exact algorithm specified in the Stage 13 brief:

    FATIGUE_WINDOW    = 4      # last N submissions evaluated
    FATIGUE_THRESHOLD = 0.35   # mean score below which fatigue is suspected
    DIFFICULTY_REDUCTION = 0.2 # mu shift amount (0.5 → 0.35)
    TREND_THRESHOLD   = -0.1   # score decline required for confirmation

A session is marked fatigued when BOTH conditions hold simultaneously:
  1. mean(recent[-4:]) < 0.35
  2. recent[-1] - recent[0] < -0.1  (performance is declining, not flat)

Auto-reset fires when consecutive_successes >= 2 while fatigued.

Design decisions:
  - Only `hidden_score` is used for fatigue detection (it is the true measure
    of correctness; visible_score can be trivially gamed).
  - The service is pure DB logic; it never calls Ollama/Brain A/B.
  - Study test sessions (StudyTestSession) are never passed here.
    The caller (submission handler) is responsible for that exclusion.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session as DBSession

from models.session import Session as PracticeSession
from models.fatigue_event import FatigueEvent

logger = logging.getLogger("fatigue_service")

# ---------------------------------------------------------------------------
# Tuning constants (exact values from specification)
# ---------------------------------------------------------------------------
FATIGUE_WINDOW:      int   = 4
FATIGUE_THRESHOLD:   float = 0.35
DIFFICULTY_REDUCTION: float = 0.20          # applied as mu = 0.5 - 0.2
NORMAL_MU:           float = 0.50
FATIGUED_MU:         float = NORMAL_MU - DIFFICULTY_REDUCTION   # 0.35
TREND_THRESHOLD:     float = -0.10
SUCCESS_THRESHOLD:   float = 0.80           # score > this counts as a 'success'
RESET_SUCCESSES:     int   = 2              # consecutive successes to reset fatigue


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class FatigueResult:
    fatigued:       bool
    recommendation: str                = ""
    message:        str                = ""
    target_mu:      float              = NORMAL_MU
    avg_window:     Optional[float]    = None
    trend:          Optional[float]    = None
    # Session state after the check
    consecutive_successes: int         = 0
    reset_occurred:        bool        = False


# ---------------------------------------------------------------------------
# Pure detection algorithm (no DB, fully testable)
# ---------------------------------------------------------------------------

def check_fatigue(session_scores: list[float]) -> FatigueResult:
    """
    Exact algorithm from spec §Core algorithm.

    Args:
        session_scores: full list of hidden_scores for this session,
                        oldest first.

    Returns:
        FatigueResult with fatigued=True iff both conditions hold.
    """
    if len(session_scores) < FATIGUE_WINDOW:
        return FatigueResult(fatigued=False)

    recent = session_scores[-FATIGUE_WINDOW:]
    avg   = sum(recent) / len(recent)
    trend = recent[-1] - recent[0]   # negative = declining  (spec §trend)

    if avg < FATIGUE_THRESHOLD and trend < TREND_THRESHOLD:
        return FatigueResult(
            fatigued=True,
            recommendation="reduce_difficulty",
            message=(
                "Taking a short break often helps. "
                "Try a slightly easier problem."
            ),
            target_mu=FATIGUED_MU,
            avg_window=round(avg, 4),
            trend=round(trend, 4),
        )

    return FatigueResult(
        fatigued=False,
        avg_window=round(avg, 4),
        trend=round(trend, 4),
    )


# ---------------------------------------------------------------------------
# Session-score retrieval helper
# ---------------------------------------------------------------------------

def get_session_hidden_scores(session_id: uuid.UUID, db: DBSession) -> list[float]:
    """
    Return all hidden_scores for this practice session in chronological order.
    Pulls from the main `submissions` table filtered by session FK is not available
    (submissions don't carry session_id directly), so we use the session's
    consecutive_fails / fatigue_score as a hint about score history.

    IMPORTANT: Because the `submissions` table has no session_id FK, the caller
    must pass in the scores accumulated during the request (or retrieve them from
    FatigueEvent history).  This helper provides a best-effort reconstruction
    from the session's user and the creation timestamps within started_at window.
    """
    from models.submission import Submission
    session: Optional[PracticeSession] = db.query(PracticeSession).filter(
        PracticeSession.id == session_id
    ).first()
    if not session:
        return []

    rows = (
        db.query(Submission)
        .filter(
            Submission.user_id == session.user_id,
            Submission.created_at >= session.started_at,
        )
        .order_by(Submission.created_at.asc())
        .all()
    )
    return [r.hidden_score for r in rows]


# ---------------------------------------------------------------------------
# Database-aware check + state update
# ---------------------------------------------------------------------------

def check_and_update_fatigue(
    session: PracticeSession,
    latest_hidden_score: float,
    db: DBSession,
) -> FatigueResult:
    """
    Core entry point called from the submission handler after every submission.

    Workflow:
      1. Append latest_hidden_score to the session's historical scores.
      2. Run check_fatigue() on the full score list.
      3. Update consecutive_successes (increment if score > 0.8, else reset to 0).
      4. If newly fatigued: set session.fatigued=True, session.fatigue_detected_at,
         and insert a FatigueEvent row.
      5. If auto-reset fires (fatigued + 2 consecutive successes): clear fatigue.
      6. Commit all state changes.
      7. Return FatigueResult with current session state.

    Args:
        session:              The active PracticeSession ORM object (already loaded).
        latest_hidden_score:  The hidden_score from the most recent submission.
        db:                   Active SQLAlchemy session.

    Returns:
        FatigueResult reflecting the outcome of this check.
    """
    # --- 1. Rebuild score list for this session ---
    all_scores = get_session_hidden_scores(session.id, db)
    # latest score may not be committed yet — ensure it's included
    if not all_scores or all_scores[-1] != latest_hidden_score:
        all_scores.append(latest_hidden_score)

    # --- 2. Run detection algorithm ---
    result = check_fatigue(all_scores)

    # --- 3. Track consecutive successes ---
    reset_occurred = False
    if latest_hidden_score > SUCCESS_THRESHOLD:
        session.consecutive_successes = (session.consecutive_successes or 0) + 1
    else:
        session.consecutive_successes = 0

    # --- 4. Auto-reset: 2 consecutive successes while fatigued ---
    if session.fatigued and session.consecutive_successes >= RESET_SUCCESSES:
        logger.info(
            "Fatigue RESET for session %s (consecutive_successes=%d).",
            session.id, session.consecutive_successes,
        )
        session.fatigued = False
        session.fatigue_detected_at = None
        session.consecutive_successes = 0
        reset_occurred = True
        result = FatigueResult(
            fatigued=False,
            reset_occurred=True,
            consecutive_successes=0,
            target_mu=NORMAL_MU,
            avg_window=result.avg_window,
            trend=result.trend,
        )

    # --- 5. New fatigue event ---
    elif result.fatigued and not session.fatigued:
        logger.warning(
            "Fatigue DETECTED for session %s "
            "(avg_window=%.4f, trend=%.4f).",
            session.id, result.avg_window, result.trend,
        )
        now = datetime.now(timezone.utc)
        session.fatigued = True
        session.fatigue_detected_at = now
        session.consecutive_successes = 0

        event = FatigueEvent(
            session_id=session.id,
            detected_at=now,
            avg_score_window=result.avg_window,
            trend_score=result.trend,
            recommendation=result.recommendation,
            message=result.message,
            target_mu=result.target_mu,
        )
        db.add(event)

    # --- 6. Carry existing fatigue forward (already fatigued, not resetting) ---
    elif session.fatigued and not reset_occurred:
        result = FatigueResult(
            fatigued=True,
            recommendation="reduce_difficulty",
            message="Taking a short break often helps. Try a slightly easier problem.",
            target_mu=FATIGUED_MU,
            avg_window=result.avg_window,
            trend=result.trend,
            consecutive_successes=session.consecutive_successes,
        )

    # --- 7. Commit ---
    db.commit()

    result.consecutive_successes = session.consecutive_successes
    result.reset_occurred = reset_occurred
    return result


# ---------------------------------------------------------------------------
# Convenience: resolve effective mu for problem selector
# ---------------------------------------------------------------------------

def effective_mu(session: Optional[PracticeSession]) -> float:
    """
    Return the Gaussian μ appropriate for the session's current fatigue state.
    Falls back gracefully to NORMAL_MU if session is None.
    """
    if session is None:
        return NORMAL_MU
    return FATIGUED_MU if session.fatigued else NORMAL_MU
