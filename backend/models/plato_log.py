"""
AdaptLab — PlatoLog ORM model (Stage 9 extended).

Extended safely with four new columns required by the Stage 9 Plato pipeline:
  - original_statement : verbatim problem text that Brain B refined
  - root_cause         : conceptual gap classified by Brain B
  - created_at         : timestamp for time-windowed dataset queries
  - topic              : denormalised topic tag for source-problem bucket queries

All new columns carry non-null server defaults so that existing rows survive;
earlier stages (Brain B logging) continue to work without modification.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, Text, Float, Boolean, JSON, DateTime, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from models.problem import Problem


class PlatoLog(Base):
    __tablename__ = "plato_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )

    # FK to the source problem that was refined
    original_problem_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("problems.id", ondelete="CASCADE"), index=True
    )

    # -----------------------------------------------------------------------
    # Core Stage 9 fields  (paper Eq. 6 training tuple: q, y_fail, root_cause, q', U)
    # -----------------------------------------------------------------------

    # q  – verbatim problem statement that was presented to the student
    original_statement: Mapped[str] = mapped_column(Text, server_default="")

    # y_fail – Brain A failure mode label (e.g. "off_by_one", "wrong_loop_bound")
    failure_mode: Mapped[str] = mapped_column(String(256))

    # root_cause – Brain B's conceptual gap string; used as WSFT input context
    root_cause: Mapped[str] = mapped_column(String(512), server_default="")

    # q' – refined problem JSON produced by Brain B's _refine()
    refined_problem: Mapped[dict[str, Any]] = mapped_column(JSON)

    # U(q') – Gaussian utility weight (μ=0.5, σ=0.2) computed at log time
    utility_score: Mapped[float] = mapped_column(Float, index=True)

    # Denormalised topic tag for fast source-bucket queries
    topic: Mapped[str] = mapped_column(String(128), server_default="", index=True)

    # -----------------------------------------------------------------------
    # Pipeline control
    # -----------------------------------------------------------------------

    # Set to True when this row has been consumed by a training run
    used_in_training: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamp; used for time-windowed dataset slicing
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        index=True,
    )

    # -----------------------------------------------------------------------
    # Relationships
    # -----------------------------------------------------------------------

    original_problem: Mapped["Problem"] = relationship(back_populates="plato_logs")

    def __repr__(self) -> str:
        return (
            f"<PlatoLog id={self.id} "
            f"original_problem_id={self.original_problem_id} "
            f"failure_mode={self.failure_mode!r} "
            f"utility={self.utility_score:.3f}>"
        )
