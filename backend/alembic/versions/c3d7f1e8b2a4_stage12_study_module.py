"""stage12_study_module

Stage 12 — User Study Module schema additions.

New tables:
  study_test_sessions       — tracks pre/post test sittings per user
  study_test_submissions    — individual problem submissions within a test
  study_confidence_surveys  — Likert ratings (1-5) per session

New columns:
  problems.is_study_only    — excludes from practice/generator paths
  users.study_group         — 'control' | 'adaptlab' (null until assigned)

All additions use safe defaults; existing data is never touched.

Revision ID: c3d7f1e8b2a4
Revises: a9f3c1e2d5b7
Create Date: 2026-04-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c3d7f1e8b2a4"
down_revision: Union[str, Sequence[str], None] = "a9f3c1e2d5b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Extend existing tables ──────────────────────────────────────────────

    # problems.is_study_only: default FALSE so all existing problems remain
    # in the practice path; study problems must be explicitly marked.
    op.add_column(
        "problems",
        sa.Column(
            "is_study_only",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index("ix_problems_is_study_only", "problems", ["is_study_only"], unique=False)

    # users.study_group: null until the user starts their pre-test
    op.add_column(
        "users",
        sa.Column("study_group", sa.String(length=16), nullable=True),
    )

    # ── New tables ───────────────────────────────────────────────────────────

    # study_test_sessions
    op.create_table(
        "study_test_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "test_type",
            sa.Enum("pre", "post", name="testtype"),
            nullable=False,
        ),
        sa.Column("problem_order", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_score", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_study_test_sessions_id",        "study_test_sessions", ["id"],        unique=False)
    op.create_index("ix_study_test_sessions_user_id",   "study_test_sessions", ["user_id"],   unique=False)
    op.create_index("ix_study_test_sessions_test_type", "study_test_sessions", ["test_type"], unique=False)

    # study_test_submissions
    op.create_table(
        "study_test_submissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("session_id",            sa.Integer(),            nullable=False),
        sa.Column("problem_id",            postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code",                  sa.String(),             nullable=False, server_default=""),
        sa.Column("visible_score",         sa.Float(),              nullable=False, server_default="0.0"),
        sa.Column("hidden_score",          sa.Float(),              nullable=False, server_default="0.0"),
        sa.Column("time_to_solve_seconds", sa.Float(),              nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["session_id"], ["study_test_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["problem_id"], ["problems.id"],            ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_study_test_submissions_session_id", "study_test_submissions", ["session_id"], unique=False)

    # study_confidence_surveys
    op.create_table(
        "study_confidence_surveys",
        sa.Column("id",         sa.Integer(),               autoincrement=True, nullable=False),
        sa.Column("user_id",    postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", sa.Integer(),               nullable=False),
        sa.Column("rating",     sa.SmallInteger(),          nullable=False),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"],    ["users.id"],               ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["study_test_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_study_confidence_surveys_user_id",    "study_confidence_surveys", ["user_id"],    unique=False)
    op.create_index("ix_study_confidence_surveys_session_id", "study_confidence_surveys", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_study_confidence_surveys_session_id", table_name="study_confidence_surveys")
    op.drop_index("ix_study_confidence_surveys_user_id",    table_name="study_confidence_surveys")
    op.drop_table("study_confidence_surveys")

    op.drop_index("ix_study_test_submissions_session_id", table_name="study_test_submissions")
    op.drop_table("study_test_submissions")

    op.drop_index("ix_study_test_sessions_test_type", table_name="study_test_sessions")
    op.drop_index("ix_study_test_sessions_user_id",   table_name="study_test_sessions")
    op.drop_index("ix_study_test_sessions_id",        table_name="study_test_sessions")
    op.drop_table("study_test_sessions")
    op.execute("DROP TYPE IF EXISTS testtype")

    op.drop_column("users", "study_group")
    op.drop_index("ix_problems_is_study_only", table_name="problems")
    op.drop_column("problems", "is_study_only")
