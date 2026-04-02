"""
models/fatigue_event.py
Stage 13 — Fatigue Event audit trail model.

One row is inserted every time a session transitions from normal → fatigued.
These rows are never deleted (research audit log) and feed the instructor
fatigue dashboard at GET /instructor/fatigue-events.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class FatigueEvent(Base):
    __tablename__ = "fatigue_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # The practice session that triggered this event (UUID, matches sessions.id)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Timestamp the fatigue was first detected in this session
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Stats from the detection window (last FATIGUE_WINDOW submissions)
    avg_score_window: Mapped[float] = mapped_column(Float, nullable=False)
    trend_score:      Mapped[float] = mapped_column(Float, nullable=False)

    # Recommendation emitted at detection time
    recommendation: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="reduce_difficulty",
    )

    # Human-readable message sent to the student
    message: Mapped[str] = mapped_column(String(512), nullable=False, default="")

    # The μ value shifted in response to this event
    target_mu: Mapped[float] = mapped_column(Float, nullable=False, default=0.35)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<FatigueEvent id={self.id} session={self.session_id} "
            f"avg={self.avg_score_window:.3f} trend={self.trend_score:.3f}>"
        )
