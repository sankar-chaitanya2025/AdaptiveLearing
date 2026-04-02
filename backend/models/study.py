"""
Stage 12 — Study Module models

New tables:
  study_test_sessions    — one row per pre/post test sitting
  study_test_submissions — one row per problem attempted in a test
  study_confidence_surveys — Likert ratings per session

New columns:
  problems.is_study_only   — excludes problem from practice/generator paths
  users.study_group        — control | adaptlab (assigned on pre-test start)
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey,
    Integer, SmallInteger, String, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class StudyGroup(str, enum.Enum):
    control  = "control"
    adaptlab = "adaptlab"


class TestType(str, enum.Enum):
    pre  = "pre"
    post = "post"


# ---------------------------------------------------------------------------
# StudyTestSession — one row per pre/post sitting
# Integer PK to match the dialogue_sessions convention (spec §UUID/Integer Split)
# ---------------------------------------------------------------------------

class StudyTestSession(Base):
    __tablename__ = "study_test_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    test_type: Mapped[TestType] = mapped_column(
        Enum(TestType, name="testtype"),
        nullable=False,
        index=True,
    )

    # Ordered list of problem UUIDs presented to this user in this session.
    # Stored as an array via JSON for DB portability (avoid PG ARRAY dep).
    problem_order: Mapped[list] = mapped_column(
        type_=__import__("sqlalchemy").JSON,
        nullable=False,
        default=list,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    # Aggregate: mean(hidden_score) across all 10 submissions in this session.
    total_score: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)

    # Relationships
    submissions: Mapped[list["StudyTestSubmission"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    surveys: Mapped[list["StudyConfidenceSurvey"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<StudyTestSession id={self.id} user={self.user_id} "
            f"type={self.test_type} score={self.total_score}>"
        )


# ---------------------------------------------------------------------------
# StudyTestSubmission — one row per problem in a test session
# UUID PK to match the submissions table convention
# ---------------------------------------------------------------------------

class StudyTestSubmission(Base):
    __tablename__ = "study_test_submissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("study_test_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    problem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("problems.id", ondelete="CASCADE"),
        nullable=False,
    )

    code: Mapped[str] = mapped_column(String, nullable=False, default="")

    # Deterministic sandbox score — no Brain A/B on test path
    visible_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    hidden_score:  Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Seconds from session.started_at to this submission
    time_to_solve_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    session: Mapped["StudyTestSession"] = relationship(back_populates="submissions")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<StudyTestSubmission id={self.id} session={self.session_id} "
            f"problem={self.problem_id} score={self.hidden_score:.3f}>"
        )


# ---------------------------------------------------------------------------
# StudyConfidenceSurvey — Likert rating (1–5) per session
# ---------------------------------------------------------------------------

class StudyConfidenceSurvey(Base):
    __tablename__ = "study_confidence_surveys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("study_test_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Likert scale 1–5
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    session: Mapped["StudyTestSession"] = relationship(back_populates="surveys")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<StudyConfidenceSurvey id={self.id} session={self.session_id} rating={self.rating}>"
