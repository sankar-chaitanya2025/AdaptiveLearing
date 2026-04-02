
from __future__ import annotations

import math
import uuid
from typing import Optional, Any

from sqlalchemy.orm import Session

from models.problem import Problem

MU_NORMAL:  float = 0.5
MU_FATIGUED: float = 0.35
SIGMA = 0.2


def gaussian_utility(
    problem_difficulty: float,
    student_score: float,
    mu: float = MU_NORMAL,
    sigma: float = SIGMA,
) -> float:
    """
    Gaussian selector utility.

    Stage 13: accepts a fatigue_mu argument so the selector can shift
    toward easier problems (mu=0.35) when the student is fatigued.

    Paper Eq.6 equivalent: U = exp(-((s_q - mu)^2) / (2*sigma^2))
    where s_q = estimated success rate for this student on this problem.
    """
    estimated_success = 1 - abs(problem_difficulty - student_score)
    utility = math.exp(-((estimated_success - mu) ** 2) / (2 * sigma ** 2))
    return utility


def select_problem(
    student_vector: dict[str, float],
    available_problems: list[dict],
    target_topic: str,
    fatigue_mu: float = MU_NORMAL,
) -> Optional[dict]:
    """
    Select the best-matching problem for a student on a given topic.

    Stage 13: fatigue_mu shifts the Gaussian peak:
      - Normal:  fatigue_mu = 0.5  (ZPD frontier)
      - Fatigued: fatigue_mu = 0.35 (easier problems preferred)

    Callers obtain fatigue_mu from fatigue_service.effective_mu(session).
    All existing callers that omit fatigue_mu continue to work unchanged.
    """
    scored = []
    for prob in available_problems:
        if prob["topic"] != target_topic:
            continue
        u = gaussian_utility(
            prob["difficulty"],
            student_vector.get(target_topic, 0.0),
            mu=fatigue_mu,
        )
        scored.append((u, prob))
    scored.sort(key=lambda x: -x[0])
    return scored[0][1] if scored else None


def get_problems(db: Session, topic: Optional[str] = None) -> list[dict[str, Any]]:
    """Fetch problems from DB, optionally filtered by topic.
    Stage 12: is_study_only=True problems are NEVER returned here — they are
    exclusively accessed through the /study/* endpoints.
    """
    query = db.query(Problem).filter(Problem.is_study_only == False)  # noqa: E712
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
