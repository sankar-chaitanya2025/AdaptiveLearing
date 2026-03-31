"""Problem bank API routes."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import SessionLocal
from services.problem_service import get_problems, get_problem_by_id, select_problem

router = APIRouter(prefix="/problems", tags=["problems"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class SelectRequest(BaseModel):
    target_topic: str = Field(..., description="Topic to select a problem for")
    student_vector: dict[str, float] = Field(..., description="Student capability vector")


@router.get("")
def list_problems(topic: Optional[str] = None, db: Session = Depends(get_db)):
    """List all problems, optionally filtered by topic."""
    return get_problems(db, topic=topic)


@router.get("/{problem_id}")
def read_problem(problem_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get a single problem by ID."""
    problem = get_problem_by_id(db, problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return {
        "id": str(problem.id),
        "title": problem.title,
        "topic": problem.topic,
        "difficulty": problem.difficulty,
        "statement": problem.statement,
        "visible_tests": problem.visible_tests,
        "hidden_tests": problem.hidden_tests,
        "prerequisite_topics": problem.prerequisite_topics,
        "created_by": problem.created_by.value if problem.created_by else None,
    }


@router.post("/select")
def select_best_problem(payload: SelectRequest, db: Session = Depends(get_db)):
    """Select the best problem for a student on a target topic."""
    available = get_problems(db, topic=payload.target_topic)
    if not available:
        raise HTTPException(status_code=404, detail=f"No problems found for topic: {payload.target_topic}")
    result = select_problem(payload.student_vector, available, payload.target_topic)
    if not result:
        raise HTTPException(status_code=404, detail="No matching problem found")
    return result
