"""add historical_performance_result

Revision ID: b7c3d2e4f5a6
Revises: a088a1294289
Create Date: 2026-07-14 20:30:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "b7c3d2e4f5a6"
down_revision: Union[str, None] = "124515811db3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "historical_performance_result",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("cycle_name", sa.String(length=128), nullable=False),
        sa.Column("perf_score", sa.Float(), nullable=True),
        sa.Column("perf_level", sa.String(length=32), nullable=True),
        sa.Column("value_belief", sa.String(length=32), nullable=True),
        sa.Column("value_team", sa.String(length=32), nullable=True),
        sa.Column("value_growth", sa.String(length=32), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("imported_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_historical_performance_result_cycle_name", "cycle_name"),
        sa.Index("ix_historical_performance_result_created_at", "created_at"),
        sa.Index("ix_historical_performance_result_user_id", "user_id"),
    )


def downgrade() -> None:
    op.drop_table("historical_performance_result")
