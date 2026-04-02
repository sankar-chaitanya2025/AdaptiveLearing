"""
backend/plato/service.py
Stage 9 — Plato DB-layer service functions.

Pure DB helpers — no business logic, no Ollama calls.  Kept thin so that
train.py and generate.py own the pipeline logic and remain testable.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models.plato_log import PlatoLog
from models.problem import Problem, CreatedBy
from models.capability_vector import CapabilityVector
from plato.config import PlatoConfig
from plato.utils import content_hash

logger = logging.getLogger("plato.service")


# ---------------------------------------------------------------------------
# Training data queries
# ---------------------------------------------------------------------------

def fetch_training_logs(
    db: Session,
    min_utility: float,
    limit: Optional[int] = None,
) -> List[PlatoLog]:
    """
    Return plato_log rows eligible for WSFT training.

    Eligibility criteria:
      - utility_score >= min_utility
      - refined_problem is not null
      - used_in_training == False  (optional: also pull already-used rows for
        re-runs; keeping this flexible via parameter would be a future extension)
    """
    query = (
        db.query(PlatoLog)
        .filter(
            PlatoLog.utility_score >= min_utility,
            PlatoLog.refined_problem.isnot(None),
        )
        .order_by(PlatoLog.utility_score.desc(), PlatoLog.created_at.desc())
    )
    if limit:
        query = query.limit(limit)
    return query.all()


def mark_logs_used(db: Session, log_ids: List[uuid.UUID]) -> int:
    """
    Bulk-set used_in_training=True for the given log IDs.
    Returns the number of rows updated.
    """
    if not log_ids:
        return 0
    updated = (
        db.query(PlatoLog)
        .filter(PlatoLog.id.in_(log_ids))
        .update({"used_in_training": True}, synchronize_session=False)
    )
    db.commit()
    logger.info("Marked %d plato_log rows as used_in_training=True.", updated)
    return updated


# ---------------------------------------------------------------------------
# Source-problem queries for generation
# ---------------------------------------------------------------------------

def fetch_mastered_problems(
    db: Session,
    cfg: PlatoConfig,
    topic: Optional[str] = None,
) -> List[Problem]:
    """
    Return problems whose average student capability score exceeds the mastered
    threshold.  These are the source problems for 'harder variant' generation.

    Strategy: join problems with capability_vectors grouped by topic, then
    filter by average score.  As a pragmatic fallback if no vectors exist yet,
    fall back to problems with difficulty >= mastered_threshold.
    """
    try:
        # Fetch all distinct topics that have at least one capability vector
        # above the threshold, then pull matching problems.
        mastered_topics_subq = (
            db.query(CapabilityVector.topic)
            .filter(CapabilityVector.score >= cfg.mastered_threshold)
            .distinct()
            .subquery()
        )

        query = db.query(Problem).filter(
            Problem.topic.in_(mastered_topics_subq)
        )
        if topic:
            query = query.filter(Problem.topic == topic)

        problems = query.all()

        if problems:
            return problems

        # Fallback: no vector data — use difficulty proxy
        logger.warning(
            "No capability vectors found above threshold %.2f; "
            "falling back to difficulty-based mastered proxy.",
            cfg.mastered_threshold,
        )
        query = db.query(Problem).filter(
            Problem.difficulty >= cfg.mastered_threshold
        )
        if topic:
            query = query.filter(Problem.topic == topic)
        return query.all()

    except Exception as exc:
        logger.error("fetch_mastered_problems failed: %s", exc)
        return []


def fetch_failure_pattern_problems(
    db: Session,
    cfg: PlatoConfig,
    min_log_count: int = 3,
) -> List[Problem]:
    """
    Return source problems that appear >= min_log_count times in plato_logs
    above the insertion utility threshold.  These are 'targeted variant'
    candidates — Plato generates problems that specifically address the
    repeated failure mode.
    """
    from sqlalchemy import func

    try:
        subq = (
            db.query(
                PlatoLog.original_problem_id,
                func.count(PlatoLog.id).label("log_count"),
            )
            .filter(PlatoLog.utility_score >= cfg.min_utility_insert)
            .group_by(PlatoLog.original_problem_id)
            .having(func.count(PlatoLog.id) >= min_log_count)
            .subquery()
        )

        return (
            db.query(Problem)
            .join(subq, Problem.id == subq.c.original_problem_id)
            .all()
        )
    except Exception as exc:
        logger.error("fetch_failure_pattern_problems failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Problem insertion
# ---------------------------------------------------------------------------

def existing_hashes(db: Session) -> set[str]:
    """
    Compute content hashes of every statement in the problem bank.
    Used by the generation pipeline to skip near-duplicate inserts.
    """
    rows = db.query(Problem.statement).all()
    return {content_hash(r.statement) for r in rows if r.statement}


def insert_plato_problem(
    db: Session,
    candidate: Dict[str, Any],
    utility_score: float,
) -> Optional[Problem]:
    """
    Insert a Plato-generated problem into the problem bank.
    Returns the ORM instance on success, None on failure.

    Ensures:
      - created_by = 'plato'
      - solution and answer columns are NOT stored on Problem (the ORM model
        does not have them); they live only in the candidate dict / plato_logs
    """
    try:
        prob = Problem(
            title=candidate["title"],
            topic=candidate.get("topic", "generated"),
            difficulty=float(candidate["difficulty"]),
            statement=candidate["statement"],
            visible_tests=candidate.get("visible_tests", []),
            hidden_tests=candidate.get("hidden_tests", []),
            prerequisite_topics=candidate.get("prerequisite_topics", []),
            created_by=CreatedBy.plato,
        )
        db.add(prob)
        db.commit()
        db.refresh(prob)
        logger.info(
            "Inserted Plato problem id=%s title=%r utility=%.3f",
            prob.id,
            prob.title,
            utility_score,
        )
        return prob
    except Exception as exc:
        db.rollback()
        logger.error("insert_plato_problem failed: %s", exc)
        return None
