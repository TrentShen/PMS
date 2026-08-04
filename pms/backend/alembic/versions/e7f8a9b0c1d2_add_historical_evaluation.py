"""add historical_evaluation_summary and historical_evaluation_detail

历史绩效敏感数据两张表：
- historical_evaluation_summary：历史周期绩效汇总（上级/互评/自评 + 校准）
- historical_evaluation_detail：历史周期绩效明细（自评产出/上级评价/互评评语 JSON）
两表均有 (user_id, cycle_name) 唯一约束，配合导入的"先删后插"保证幂等。

Revision ID: e7f8a9b0c1d2
Revises: 4c3b8a3aeab0
Create Date: 2026-08-04 03:30:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, None] = "4c3b8a3aeab0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "historical_evaluation_summary",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("cycle_name", sa.String(length=128), nullable=False),
        sa.Column("superior_score", sa.Float(), nullable=True),
        sa.Column("superior_level", sa.String(length=32), nullable=True),
        sa.Column("superior_value_grade", sa.String(length=32), nullable=True),
        sa.Column("peer_avg_score", sa.Float(), nullable=True),
        sa.Column("peer_level", sa.String(length=32), nullable=True),
        sa.Column("peer_value_grade", sa.String(length=32), nullable=True),
        sa.Column("self_score", sa.Float(), nullable=True),
        sa.Column("self_level", sa.String(length=32), nullable=True),
        sa.Column("self_value_grade", sa.String(length=32), nullable=True),
        sa.Column("is_calibrated", sa.Boolean(), nullable=False),
        sa.Column("calibration_suggestion", sa.Text(), nullable=True),
        sa.Column("calibrated_score", sa.Float(), nullable=True),
        sa.Column("calibrated_result", sa.String(length=64), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "cycle_name", name="uq_historical_eval_summary_user_cycle"),
        sa.Index("ix_historical_evaluation_summary_cycle_name", "cycle_name"),
        sa.Index("ix_historical_evaluation_summary_user_id", "user_id"),
    )
    op.create_table(
        "historical_evaluation_detail",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("cycle_name", sa.String(length=128), nullable=False),
        sa.Column("self_score", sa.Float(), nullable=True),
        sa.Column("self_value_grade", sa.String(length=32), nullable=True),
        sa.Column("self_output", sa.Text(), nullable=True),
        sa.Column("self_comment", sa.Text(), nullable=True),
        sa.Column("superior_score", sa.Float(), nullable=True),
        sa.Column("superior_value_grade", sa.String(length=32), nullable=True),
        sa.Column("superior_comment", sa.Text(), nullable=True),
        sa.Column("peers_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "cycle_name", name="uq_historical_eval_detail_user_cycle"),
        sa.Index("ix_historical_evaluation_detail_cycle_name", "cycle_name"),
        sa.Index("ix_historical_evaluation_detail_user_id", "user_id"),
    )


def downgrade() -> None:
    op.drop_table("historical_evaluation_detail")
    op.drop_table("historical_evaluation_summary")
