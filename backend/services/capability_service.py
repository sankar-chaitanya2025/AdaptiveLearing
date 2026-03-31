"""
Capability Engine for AdaptLab.

Implements the adaptive learning logic that tracks student mastery
across topics using Exponential Moving Average (EMA), Zone of Proximal
Development (ZPD) classification, and Prerequisite-Aware Capability
Backtracking (PACB) for intelligent topic redirection.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from models.capability_vector import CapabilityVector

# ---------------------------------------------------------------------------
# Topic prerequisite graph
# ---------------------------------------------------------------------------
TOPIC_GRAPH: dict[str, list[str]] = {
    "dynamic_programming": ["recursion", "arrays"],
    "backtracking":        ["recursion"],
    "binary_search":       ["sorting", "arrays"],
    "sliding_window":      ["arrays", "two_pointers"],
    "graphs":              ["hash_maps", "arrays"],
    "two_pointers":        ["arrays", "sorting"],
    "sorting":             ["arrays"],
    "recursion":           [],
    "arrays":              [],
    "hash_maps":           [],
}

BASE_ALPHA: float = 0.3


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------

def compute_confidence(
    time_taken: float,
    time_limit: float,
    hint_used: bool,
    attempt_num: int,
) -> float:
    """Return a confidence multiplier in [0.0, 1.0].

    The multiplier rewards submissions that:
    - finish well within the time limit,
    - don't rely on hints,
    - are solved on the first attempt.

    Args:
        time_taken:  Seconds the student actually spent.
        time_limit:  Maximum allowed seconds for the problem.
        hint_used:   Whether a hint was consumed.
        attempt_num: Which attempt this is (1-based).

    Returns:
        A float between 0.0 and 1.0.
    """
    # Time ratio: faster → higher confidence
    time_ratio: float = max(0.0, 1.0 - (time_taken / time_limit)) if time_limit > 0 else 0.5

    # Hint penalty: -0.2 if a hint was used
    hint_penalty: float = 0.2 if hint_used else 0.0

    # Attempt decay: each retry beyond the first costs 0.1
    attempt_penalty: float = min((attempt_num - 1) * 0.1, 0.5)

    confidence: float = max(0.0, min(1.0, time_ratio - hint_penalty - attempt_penalty))
    return round(confidence, 4)


def apply_ema(old_score: float, submission_score: float, alpha: float = BASE_ALPHA) -> float:
    """Compute an Exponential Moving Average update.

    new_score = α * submission_score + (1 − α) * old_score

    Args:
        old_score:        The student's current mastery score for the topic.
        submission_score: The raw score from the latest submission (0-1).
        alpha:            Smoothing factor (0 < α ≤ 1).

    Returns:
        Updated mastery score, rounded to 4 decimal places.
    """
    new_score: float = alpha * submission_score + (1.0 - alpha) * old_score
    return round(new_score, 4)


def get_zpd_zone(score: float) -> str:
    """Classify a mastery score into a Zone of Proximal Development label.

    | Zone          | Score range |
    |---------------|-------------|
    | mastered      | ≥ 0.8       |
    | zpd           | 0.4 – 0.79  |
    | need_support  | < 0.4       |

    Args:
        score: Current mastery score in [0, 1].

    Returns:
        One of ``"mastered"``, ``"zpd"``, or ``"need_support"``.
    """
    if score >= 0.8:
        return "mastered"
    if score >= 0.4:
        return "zpd"
    return "need_support"


def pacb_redirect(
    student_vector: dict[str, float],
    failing_topic: str,
    threshold: float = 0.4,
) -> Optional[str]:
    """Prerequisite-Aware Capability Backtracking.

    If the student is struggling with ``failing_topic``, check whether any
    of its prerequisites are below the threshold.  If so, return the weakest
    prerequisite so the system can redirect the student there first.

    Args:
        student_vector: Mapping of topic → current mastery score.
        failing_topic:  The topic the student is struggling with.
        threshold:      Score below which a prerequisite is considered weak.

    Returns:
        The name of the weakest prerequisite topic, or ``None`` if all
        prerequisites meet the threshold (or the topic has none).
    """
    prereqs: list[str] = TOPIC_GRAPH.get(failing_topic, [])
    if not prereqs:
        return None

    weakest_topic: Optional[str] = None
    weakest_score: float = threshold  # only consider scores *below* threshold

    for prereq in prereqs:
        prereq_score: float = student_vector.get(prereq, 0.0)
        if prereq_score < weakest_score:
            weakest_score = prereq_score
            weakest_topic = prereq

    return weakest_topic


# ---------------------------------------------------------------------------
# Database-aware functions
# ---------------------------------------------------------------------------

def update_capability(
    user_id: uuid.UUID,
    topic: str,
    submission_score: float,
    time_taken: float,
    time_limit: float,
    hint_used: bool,
    attempt_num: int,
    db: Session,
) -> dict:
    """Update a student's capability vector for a single topic.

    Workflow:
    1. Compute a confidence multiplier from timing / hint / attempt data.
    2. Weight the raw submission score by the confidence.
    3. EMA-blend the weighted score into the student's stored mastery.
    4. Persist the new score to the ``capability_vectors`` table.

    Args:
        user_id:          UUID of the student.
        topic:            Topic slug (must be a key in TOPIC_GRAPH).
        submission_score: Raw correctness score from the grader (0-1).
        time_taken:       Seconds the student actually spent.
        time_limit:       Maximum allowed seconds.
        hint_used:        Whether a hint was consumed.
        attempt_num:      Which attempt this is (1-based).
        db:               Active SQLAlchemy session.

    Returns:
        A dict with keys: ``user_id``, ``topic``, ``old_score``,
        ``new_score``, ``confidence``, ``zone``, ``redirect``.
    """
    # --- 1. confidence ---
    confidence: float = compute_confidence(time_taken, time_limit, hint_used, attempt_num)

    # --- 2. weighted score ---
    weighted_score: float = submission_score * confidence

    # --- 3. fetch or create the vector row ---
    vector: Optional[CapabilityVector] = (
        db.query(CapabilityVector)
        .filter(
            CapabilityVector.user_id == user_id,
            CapabilityVector.topic == topic,
        )
        .first()
    )

    old_score: float = 0.0
    if vector is None:
        vector = CapabilityVector(user_id=user_id, topic=topic, score=0.0)
        db.add(vector)
    else:
        old_score = vector.score

    # --- 4. EMA update ---
    new_score: float = apply_ema(old_score, weighted_score)
    vector.score = new_score
    db.commit()
    db.refresh(vector)

    # --- 5. ZPD + PACB ---
    zone: str = get_zpd_zone(new_score)

    # Build a lightweight student vector for PACB by reading all rows
    full_vector: dict[str, float] = get_vector(user_id, db)
    redirect: Optional[str] = None
    if zone == "need_support":
        redirect = pacb_redirect(full_vector, topic)

    return {
        "user_id": str(user_id),
        "topic": topic,
        "old_score": old_score,
        "new_score": new_score,
        "confidence": confidence,
        "zone": zone,
        "redirect": redirect,
    }


def get_vector(user_id: uuid.UUID, db: Session) -> dict[str, float]:
    """Return the full capability vector for a student.

    Args:
        user_id: UUID of the student.
        db:      Active SQLAlchemy session.

    Returns:
        A dict mapping topic names to mastery scores.  Topics with no
        stored row default to 0.0 (returned only for topics present in
        the database — callers can merge with TOPIC_GRAPH keys if they
        need all topics).
    """
    rows = (
        db.query(CapabilityVector)
        .filter(CapabilityVector.user_id == user_id)
        .all()
    )
    return {row.topic: row.score for row in rows}
