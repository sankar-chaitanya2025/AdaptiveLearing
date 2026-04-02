"""stage9_plato_log_extensions

Adds missing columns to plato_logs that Stage 9 Plato pipeline requires:
- original_statement: the raw problem text Brain B refined
- root_cause: the conceptual gap Brain B identified (drives WSFT input)
- created_at: timestamp for filtering by recency
- topic: denormalised topic tag for fast source-problem queries

These columns are new; existing rows get safe non-null defaults so that
no data is destroyed and earlier stages continue to work.

Revision ID: a9f3c1e2d5b7
Revises: b21ff5c1a08b
Create Date: 2026-04-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a9f3c1e2d5b7"
down_revision: Union[str, Sequence[str], None] = "b21ff5c1a08b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add original_statement – the problem text that was refined.
    op.add_column(
        "plato_logs",
        sa.Column(
            "original_statement",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
    )

    # Add root_cause – the conceptual gap string from Brain B's classification.
    op.add_column(
        "plato_logs",
        sa.Column(
            "root_cause",
            sa.String(length=512),
            nullable=False,
            server_default="",
        ),
    )

    # Add created_at – makes time-windowed queries possible.
    op.add_column(
        "plato_logs",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Add topic – denormalised for fast source-problem bucket queries.
    op.add_column(
        "plato_logs",
        sa.Column(
            "topic",
            sa.String(length=128),
            nullable=False,
            server_default="",
        ),
    )

    # Index for common Stage 9 queries.
    op.create_index("ix_plato_logs_topic", "plato_logs", ["topic"], unique=False)
    op.create_index("ix_plato_logs_created_at", "plato_logs", ["created_at"], unique=False)
    op.create_index("ix_plato_logs_utility_score", "plato_logs", ["utility_score"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_plato_logs_utility_score", table_name="plato_logs")
    op.drop_index("ix_plato_logs_created_at", table_name="plato_logs")
    op.drop_index("ix_plato_logs_topic", table_name="plato_logs")
    op.drop_column("plato_logs", "topic")
    op.drop_column("plato_logs", "created_at")
    op.drop_column("plato_logs", "root_cause")
    op.drop_column("plato_logs", "original_statement")
