import uuid
import enum
from sqlalchemy import String, Float, Enum, text, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
from typing import List, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from models.submission import Submission
    from models.plato_log import PlatoLog

class CreatedBy(str, enum.Enum):
    plato = "plato"
    human = "human"

class Problem(Base):
    __tablename__ = "problems"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    title: Mapped[str] = mapped_column(String)
    topic: Mapped[str] = mapped_column(String, index=True)
    difficulty: Mapped[float] = mapped_column(Float)
    statement: Mapped[str] = mapped_column(String)
    visible_tests: Mapped[dict[str, Any]] = mapped_column(JSON)
    hidden_tests: Mapped[dict[str, Any]] = mapped_column(JSON)
    prerequisite_topics: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_by: Mapped[CreatedBy] = mapped_column(Enum(CreatedBy, name="createdby", native_enum=False))
    # Stage 12: isolates study problems from the practice/generator paths.
    # Brain B, Plato, and get_problems() must filter is_study_only=False.
    is_study_only: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    submissions: Mapped[List["Submission"]] = relationship(back_populates="problem", cascade="all, delete-orphan")
    plato_logs: Mapped[List["PlatoLog"]] = relationship(back_populates="original_problem", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Problem id={self.id} title={self.title} topic={self.topic} difficulty={self.difficulty}>"
