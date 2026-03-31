import uuid
from datetime import datetime
from sqlalchemy import ForeignKey, text, String, Float, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.user import User
    from models.problem import Problem

class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    problem_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String)
    visible_score: Mapped[float] = mapped_column(Float)
    hidden_score: Mapped[float] = mapped_column(Float)
    brain_a_feedback: Mapped[str] = mapped_column(String)
    gamed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    user: Mapped["User"] = relationship(back_populates="submissions")
    problem: Mapped["Problem"] = relationship(back_populates="submissions")

    def __repr__(self) -> str:
        return f"<Submission id={self.id} problem_id={self.problem_id} scores=({self.visible_score},{self.hidden_score})>"
