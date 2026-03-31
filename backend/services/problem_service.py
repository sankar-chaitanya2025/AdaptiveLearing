
from __future__ import annotations

import math
import uuid
from typing import Optional, Any

from sqlalchemy.orm import Session

from models.problem import Problem

SIGMA = 0.2


def gaussian_utility(problem_difficulty: float, student_score: float, sigma: float = SIGMA) -> float:
    """Compute Gaussian utility for a problem given student mastery."""
    estimated_success = 1 - abs(problem_difficulty - student_score)
    utility = math.exp(-((estimated_success - 1.0) ** 2) / (2 * sigma ** 2))
    return utility


def select_problem(student_vector: dict[str, float], available_problems: list[dict], target_topic: str) -> Optional[dict]:
    """Select the best-matching problem for a student on a given topic."""
    scored = []
    for prob in available_problems:
        if prob["topic"] != target_topic:
            continue
        u = gaussian_utility(prob["difficulty"], student_vector.get(target_topic, 0.0))
        scored.append((u, prob))
    scored.sort(key=lambda x: -x[0])
    return scored[0][1] if scored else None


def get_problems(db: Session, topic: Optional[str] = None) -> list[dict[str, Any]]:
    """Fetch problems from DB, optionally filtered by topic."""
    query = db.query(Problem)
    if topic:
        query = query.filter(Problem.topic == topic)
    rows = query.all()
    return [
        {
            "id": str(r.id),
            "title": r.title,
            "topic": r.topic,
            "difficulty": r.difficulty,
            "statement": r.statement,
            "visible_tests": r.visible_tests,
            "hidden_tests": r.hidden_tests,
            "prerequisite_topics": r.prerequisite_topics,
            "created_by": r.created_by.value if r.created_by else None,
        }
        for r in rows
    ]


def get_problem_by_id(db: Session, problem_id: uuid.UUID) -> Optional[Problem]:
    """Fetch a single problem by its UUID."""
    return db.query(Problem).filter(Problem.id == problem_id).first()
