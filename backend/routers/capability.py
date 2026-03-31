"""
Capability Engine API routes.

POST /capability/update   — update a student's mastery after a submission
GET  /capability/vector/{user_id} — retrieve the full capability vector
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import SessionLocal
from services.capability_service import update_capability, get_vector

router = APIRouter(prefix="/capability", tags=["capability"])


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------

def get_db():
    """Yield a SQLAlchemy session, ensuring it closes after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class UpdateRequest(BaseModel):
    """Payload for POST /capability/update."""
    user_id: uuid.UUID = Field(..., description="UUID of the student")
    topic: str = Field(..., description="Topic slug, e.g. 'dynamic_programming'")
    submission_score: float = Field(..., ge=0.0, le=1.0, description="Raw correctness score (0-1)")
    time_taken: float = Field(..., ge=0.0, description="Seconds the student spent")
    time_limit: float = Field(..., gt=0.0, description="Maximum allowed seconds")
    hint_used: bool = Field(False, description="Whether a hint was consumed")
    attempt_num: int = Field(1, ge=1, description="Attempt number (1-based)")


class UpdateResponse(BaseModel):
    """Response from POST /capability/update."""
    user_id: str
    topic: str
    old_score: float
    new_score: float
    confidence: float
    zone: str
    redirect: Optional[str] = None


class VectorResponse(BaseModel):
    """Response from GET /capability/vector/{user_id}."""
    user_id: str
    vector: dict[str, float]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/update", response_model=UpdateResponse)
def capability_update(payload: UpdateRequest, db: Session = Depends(get_db)):
    """Update a student's capability vector after a submission."""
    result = update_capability(
        user_id=payload.user_id,
        topic=payload.topic,
        submission_score=payload.submission_score,
        time_taken=payload.time_taken,
        time_limit=payload.time_limit,
        hint_used=payload.hint_used,
        attempt_num=payload.attempt_num,
        db=db,
    )
    return result


@router.get("/vector/{user_id}", response_model=VectorResponse)
def capability_vector(user_id: uuid.UUID, db: Session = Depends(get_db)):
    """Retrieve the full capability vector for a student."""
    vector = get_vector(user_id, db)
    return {"user_id": str(user_id), "vector": vector}
