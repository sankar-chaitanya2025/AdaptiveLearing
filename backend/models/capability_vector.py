import uuid
from datetime import datetime
from sqlalchemy import ForeignKey, text, DateTime, String, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.user import User

class CapabilityVector(Base):
    __tablename__ = "capability_vectors"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    topic: Mapped[str] = mapped_column(String, index=True) 
    score: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="capability_vectors")

    def __repr__(self) -> str:
        return f"<CapabilityVector id={self.id} user_id={self.user_id} topic={self.topic} score={self.score}>"
