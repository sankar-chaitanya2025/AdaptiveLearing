import uuid
from sqlalchemy import ForeignKey, text, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.user import User
    from models.session import Session

class StudyMetric(Base):
    __tablename__ = "study_metrics"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    pre_test_score: Mapped[float] = mapped_column(Float)
    post_test_score: Mapped[float] = mapped_column(Float)
    confidence_rating: Mapped[int] = mapped_column(Integer) # 1-5
    time_to_solve: Mapped[float] = mapped_column(Float)

    user: Mapped["User"] = relationship(back_populates="study_metrics")
    session: Mapped["Session"] = relationship(back_populates="study_metrics")

    def __repr__(self) -> str:
        return f"<StudyMetric id={self.id} user_id={self.user_id} session_id={self.session_id}>"
