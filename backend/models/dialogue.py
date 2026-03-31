"""
AdaptLab Stage 8 — Dialogue Model
SQLAlchemy ORM model for persisting multi-turn Socratic dialogue sessions.
Fixed for UUID submission_id mismatch.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID  # Required for your UUID project
from sqlalchemy.orm import relationship

# Import your project's declarative Base.
from database import Base 


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------

class DialogueStatus(str, enum.Enum):
    """Lifecycle states for a Socratic dialogue session."""
    OPEN       = "OPEN"       # Dialogue is in progress
    RESOLVED   = "RESOLVED"   # Student demonstrated target insight
    EXHAUSTED  = "EXHAUSTED"  # Max turns reached; bridge explanation delivered


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class DialogueSession(Base):
    """
    Represents one complete Socratic dialogue loop triggered by a failed
    coding submission.
    """

    __tablename__ = "dialogue_sessions"

    # Primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # ------------------------------------------------------------------
    # FOREIGN KEY FIX: Changed from Integer to UUID to match submissions table
    # ------------------------------------------------------------------
    submission_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("submissions.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )

    # Dialogue state
    turn_count = Column(Integer, nullable=False, default=0)

    # Stored as a JSON array of {"role": str, "content": str} objects.
    history = Column(JSON, nullable=False, default=list)

    # Knowledge-gap context set by Brain B at session creation
    root_cause = Column(
        String(512),
        nullable=False,
        default="",
        comment="Conceptual gap identified by Brain B during error analysis",
    )

    target_insight = Column(
        String(512),
        nullable=False,
        default="",
        comment="One-sentence rubric Brain A checks student responses against",
    )

    # Status
    status = Column(
        Enum(DialogueStatus),
        nullable=False,
        default=DialogueStatus.OPEN,
        index=True,
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def append_turn(self, role: str, content: str) -> None:
        """
        Append one message to the conversation history and increment
        turn_count when the student (role == 'student') speaks.
        """
        # SQLAlchemy does not always detect in-place mutations of JSON
        # columns, so we reassign with a new list.
        current = list(self.history) if self.history else []
        current.append({"role": role, "content": content})
        self.history = current

        if role == "student":
            self.turn_count = (self.turn_count or 0) + 1

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<DialogueSession id={self.id} submission_id={self.submission_id} "
            f"turns={self.turn_count} status={self.status}>"
        )