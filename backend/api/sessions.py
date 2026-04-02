"""
backend/api/sessions.py
Stage 13 — Session management and fatigue inspection endpoints.

Endpoints:
  POST /session                            — create a new practice session
  GET  /session/{session_id}               — fetch session state (includes fatigue)
  POST /session/{session_id}/check-fatigue — explicit fatigue check after submission
  GET  /instructor/fatigue-events          — paginated audit trail for dashboard

The /session router replaces the previous ad-hoc session handling in submissions.py;
existing sessions table and FK relationships are unchanged.
"""
from __future__ import annotations

import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from database import get_db
from models.session import Session as PracticeSession
from models.user import User, UserRole
from models.fatigue_event import FatigueEvent
from services.fatigue_service import check_and_update_fatigue, effective_mu

logger = logging.getLogger("sessions.api")

router = APIRouter(tags=["sessions"])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_session_or_404(session_id: uuid.UUID, db: DBSession) -> PracticeSession:
    s = db.query(PracticeSession).filter(PracticeSession.id == session_id).first()
    if not s:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found.",
        )
    return s


def _session_dict(s: PracticeSession) -> dict:
    return {
        "id":                    str(s.id),
        "user_id":               str(s.user_id),
        "started_at":            s.started_at.isoformat(),
        "fatigue_score":         s.fatigue_score,
        "consecutive_fails":     s.consecutive_fails,
        # Stage 13 fields
        "fatigued":              s.fatigued,
        "consecutive_successes": s.consecutive_successes,
        "fatigue_detected_at":   s.fatigue_detected_at.isoformat() if s.fatigue_detected_at else None,
        "effective_mu":          effective_mu(s),
    }


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    user_id: uuid.UUID


class FatigueCheckRequest(BaseModel):
    latest_hidden_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="hidden_score from the most recent submission in this session",
    )


class FatigueCheckResponse(BaseModel):
    session_id:           str
    fatigued:             bool
    recommendation:       str
    message:              str
    target_mu:            float
    consecutive_successes: int
    reset_occurred:       bool
    avg_window:           Optional[float]
    trend:                Optional[float]
    # Current full session state
    session:              dict


class FatigueEventOut(BaseModel):
    id:              str
    session_id:      str
    detected_at:     str
    avg_score_window: float
    trend_score:     float
    recommendation:  str
    message:         str
    target_mu:       float


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/session", status_code=201)
def create_session(
    body: CreateSessionRequest,
    db: DBSession = Depends(get_db),
) -> dict:
    """
    Create a new practice session for a student.
    Returns the new session with all Stage 13 fatigue fields.
    """
    user = db.query(User).filter(User.id == body.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User {body.user_id} not found.")

    session = PracticeSession(user_id=body.user_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_dict(session)


@router.get("/session/{session_id}")
def get_session(
    session_id: uuid.UUID,
    db: DBSession = Depends(get_db),
) -> dict:
    """Fetch full session state including current fatigue status."""
    return _session_dict(_get_session_or_404(session_id, db))


@router.post(
    "/session/{session_id}/check-fatigue",
    response_model=FatigueCheckResponse,
)
def check_fatigue_endpoint(
    session_id: uuid.UUID,
    body: FatigueCheckRequest,
    db: DBSession = Depends(get_db),
) -> FatigueCheckResponse:
    """
    Explicit fatigue check — called after every submission.

    The submission handler calls this automatically when session_id is present
    in the SubmissionRequest. This endpoint is exposed separately so the
    frontend or test harness can also trigger it directly.

    Business rules enforced here:
    - Study test sessions are never passed (the sessions table only holds
      practice sessions; StudyTestSession has a separate table).
    - Gamed submissions should not be passed (caller's responsibility).
    """
    session = _get_session_or_404(session_id, db)

    result = check_and_update_fatigue(
        session=session,
        latest_hidden_score=body.latest_hidden_score,
        db=db,
    )
    db.refresh(session)

    return FatigueCheckResponse(
        session_id=str(session_id),
        fatigued=result.fatigued,
        recommendation=result.recommendation,
        message=result.message,
        target_mu=result.target_mu,
        consecutive_successes=result.consecutive_successes,
        reset_occurred=result.reset_occurred,
        avg_window=result.avg_window,
        trend=result.trend,
        session=_session_dict(session),
    )


# ---------------------------------------------------------------------------
# Instructor endpoints
# ---------------------------------------------------------------------------

@router.get("/instructor/fatigue-events")
def list_fatigue_events(
    session_id: Optional[uuid.UUID] = Query(None, description="Filter by session UUID"),
    page:       int                  = Query(1, ge=1),
    page_size:  int                  = Query(50, ge=1, le=200),
    db:         DBSession            = Depends(get_db),
) -> dict:
    """
    Paginated audit trail of fatigue events for the instructor dashboard.

    Query params:
      session_id  — if supplied, returns events only for that session
      page        — 1-indexed page number (default 1)
      page_size   — rows per page (default 50, max 200)

    Access: open to any authenticated caller in this implementation.
    Add role-check middleware when JWT auth is wired into the project.
    """
    query = db.query(FatigueEvent).order_by(FatigueEvent.detected_at.desc())

    if session_id is not None:
        query = query.filter(FatigueEvent.session_id == session_id)

    total  = query.count()
    offset = (page - 1) * page_size
    rows   = query.offset(offset).limit(page_size).all()

    events = [
        FatigueEventOut(
            id=str(e.id),
            session_id=str(e.session_id),
            detected_at=e.detected_at.isoformat(),
            avg_score_window=e.avg_score_window,
            trend_score=e.trend_score,
            recommendation=e.recommendation,
            message=e.message,
            target_mu=e.target_mu,
        )
        for e in rows
    ]

    return {
        "total":     total,
        "page":      page,
        "page_size": page_size,
        "pages":     max(1, -(-total // page_size)),  # ceiling division
        "events":    [e.model_dump() for e in events],
    }
