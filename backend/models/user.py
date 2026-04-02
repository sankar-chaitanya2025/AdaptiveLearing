import uuid
from datetime import datetime
from sqlalchemy import String, Enum, text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
from typing import List, TYPE_CHECKING, Optional
import enum

if TYPE_CHECKING:
    from models.capability_vector import CapabilityVector
    from models.submission import Submission
    from models.session import Session
    from models.study_metric import StudyMetric

class UserRole(str, enum.Enum):
    student = "student"
    instructor = "instructor"

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="userrole", native_enum=False), default=UserRole.student)
    hashed_password: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    # Stage 12: study group assignment (null = not yet assigned)
    study_group: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, default=None)

    # Relationships
    capability_vectors: Mapped[List["CapabilityVector"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    submissions: Mapped[List["Submission"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    sessions: Mapped[List["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    study_metrics: Mapped[List["StudyMetric"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"
