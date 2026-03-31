import uuid
from sqlalchemy import ForeignKey, text, String, Float, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from models.problem import Problem

class PlatoLog(Base):
    __tablename__ = "plato_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    original_problem_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"))
    failure_mode: Mapped[str] = mapped_column(String)
    refined_problem: Mapped[dict[str, Any]] = mapped_column(JSON)
    utility_score: Mapped[float] = mapped_column(Float)
    used_in_training: Mapped[bool] = mapped_column(Boolean, default=False)

    original_problem: Mapped["Problem"] = relationship(back_populates="plato_logs")

    def __repr__(self) -> str:
        return f"<PlatoLog id={self.id} original_problem_id={self.original_problem_id} failure_mode={self.failure_mode}>"
