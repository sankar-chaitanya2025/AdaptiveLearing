"""stage13_fatigue_detection

Stage 13 — Fatigue Detection schema additions.

New table:
  fatigue_events — audit log of every fatigue-detection event per session

New columns on `sessions`:
  fatigued              BOOLEAN  NOT NULL DEFAULT false
  consecutive_successes INTEGER  NOT NULL DEFAULT 0
  fatigue_detected_at   TIMESTAMPTZ       NULL

All additions use safe server_defaults; zero existing data is altered.
Downgrade cleanly reverses every change.

Revision ID: d4e8f2a1c6b9
Revises: c3d7f1e8b2a4
Create Date: 2026-04-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d4e8f2a1c6b9"
down_revision: Union[str, Sequence[str], None] = "c3d7f1e8b2a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Extend sessions table ─────────────────────────────────────────────────

    op.add_column(
        "sessions",
        sa.Column(
            "fatigued",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "sessions",
        sa.Column(
            "consecutive_successes",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "sessions",
        sa.Column(
            "fatigue_detected_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # ── New fatigue_events table ──────────────────────────────────────────────

    op.create_table(
        "fatigue_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("avg_score_window", sa.Float(), nullable=False),
        sa.Column("trend_score",      sa.Float(), nullable=False),
        sa.Column(
            "recommendation",
            sa.String(length=64),
            nullable=False,
            server_default="reduce_difficulty",
        ),
        sa.Column(
            "message",
            sa.String(length=512),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "target_mu",
            sa.Float(),
            nullable=False,
            server_default="0.35",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fatigue_events_session_id",
        "fatigue_events",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "ix_fatigue_events_detected_at",
        "fatigue_events",
        ["detected_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_fatigue_events_detected_at", table_name="fatigue_events")
    op.drop_index("ix_fatigue_events_session_id",  table_name="fatigue_events")
    op.drop_table("fatigue_events")

    op.drop_column("sessions", "fatigue_detected_at")
    op.drop_column("sessions", "consecutive_successes")
    op.drop_column("sessions", "fatigued")
