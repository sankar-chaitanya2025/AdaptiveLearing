import uuid
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import Boolean, ForeignKey, text, Float, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base

if TYPE_CHECKING:
    from models.user import User
    from models.study_metric import StudyMetric

class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    # Existing fatigue tracking (Stage 6/earlier)
    fatigue_score: Mapped[float] = mapped_column(Float, default=0.0)
    consecutive_fails: Mapped[int] = mapped_column(Integer, default=0)

    # Stage 13: fatigue-state fields (safe defaults, migration adds them)
    fatigued: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    consecutive_successes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    fatigue_detected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    user: Mapped["User"] = relationship(back_populates="sessions")
    study_metrics: Mapped[List["StudyMetric"]] = relationship(back_populates="session", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Session id={self.id} user_id={self.user_id} fatigue={self.fatigue_score}>"
