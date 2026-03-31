"""
AdaptLab Stage 8 — Dialogue API Router
FastAPI router exposing POST /dialogue/respond and POST /dialogue/start.
"""

from __future__ import annotations

import json
from uuid import UUID  # Use UUID to match our database fix
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# --- CLEAN IMPORTS (No 'backend.' prefix) ---
from database import get_db
from models.dialogue import DialogueSession, DialogueStatus
from ai.dialogue_manager import DialogueManager, DialogueTurnResult

router = APIRouter(prefix="/dialogue", tags=["Dialogue"])
_manager = DialogueManager()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class StartSessionRequest(BaseModel):
    """
    Called immediately after a failed submission to open a dialogue session.
    """
    # Changed from int to UUID to match our DB model
    submission_id: UUID = Field(..., description="ID of the failed submission")
    root_cause: str = Field(..., description="Conceptual gap from Brain B error analysis")
    target_insight: str = Field(..., description="Rubric sentence Brain A evaluates against")
    opening_question: str = Field(..., description="Brain B's first Socratic question")


class StartSessionResponse(BaseModel):
    session_id: int
    status: str
    tutor_message: str
    turn_count: int


class RespondRequest(BaseModel):
    session_id: int = Field(..., description="ID of the active DialogueSession")
    student_text: str = Field(..., min_length=1, description="Student's free-text response")


class RespondResponse(BaseModel):
    session_id: int
    status: str
    tutor_message: str
    understanding_shown: bool
    turn_count: int
    refined_prompt: Optional[str] = None
    next_problem: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_open_session(session_id: int, db: Session) -> DialogueSession:
    """Fetch a session and verify it is still OPEN."""
    session: Optional[DialogueSession] = (
        db.query(DialogueSession).filter(DialogueSession.id == session_id).first()
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DialogueSession {session_id} not found.",
        )
    if session.status != DialogueStatus.OPEN:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"DialogueSession {session_id} is already {session.status.value}.",
        )
    return session


def _build_respond_response(result: DialogueTurnResult) -> RespondResponse:
    return RespondResponse(
        session_id=result.session_id,
        status=result.status,
        tutor_message=result.tutor_message,
        understanding_shown=result.understanding_shown,
        turn_count=result.turn_count,
        refined_prompt=result.refined_prompt or None,
        next_problem=result.next_problem or None,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/start",
    response_model=StartSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Open a new Socratic dialogue session",
)
def start_session(
    body: StartSessionRequest,
    db: Session = Depends(get_db),
) -> StartSessionResponse:
    session = DialogueSession(
        submission_id=body.submission_id,
        root_cause=body.root_cause,
        target_insight=body.target_insight,
        status=DialogueStatus.OPEN,
        turn_count=0,
        history=[],
    )
    # Record Brain B's opening question as the first tutor message
    session.append_turn("tutor", body.opening_question)

    db.add(session)
    db.commit()
    db.refresh(session)

    return StartSessionResponse(
        session_id=session.id,
        status="OPEN",
        tutor_message=body.opening_question,
        turn_count=session.turn_count,
    )


@router.post(
    "/respond",
    response_model=RespondResponse,
    summary="Submit student response",
)
async def respond(
    body: RespondRequest,
    db: Session = Depends(get_db),
) -> RespondResponse:
    session = _get_open_session(body.session_id, db)

    try:
        result: DialogueTurnResult = await _manager.process_turn(
            session=session,
            student_text=body.student_text,
            db=db,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dialogue engine error: {exc}",
        ) from exc

    return _build_respond_response(result)


@router.get(
    "/{session_id}",
    summary="Retrieve session history",
)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    session: Optional[DialogueSession] = (
        db.query(DialogueSession).filter(DialogueSession.id == session_id).first()
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    return {
        "session_id":     session.id,
        "submission_id":  session.submission_id,
        "status":         session.status.value,
        "turn_count":     session.turn_count,
        "root_cause":     session.root_cause,
        "target_insight": session.target_insight,
        "history":        session.history,
        "created_at":     session.created_at.isoformat(),
        "updated_at":     session.updated_at.isoformat(),
    }