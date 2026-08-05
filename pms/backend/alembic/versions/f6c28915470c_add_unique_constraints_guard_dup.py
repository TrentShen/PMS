"""add unique constraints to 4 tables (guard against duplicates)

4 张表此前只有应用层查重，并发/重试下可能写入重复行，现补数据库级唯一约束：
- cycle_participant: (cycle_id, user_id)
- objective_cycle_participant: (objective_cycle_id, user_id)
- probation_plan: (user_id)
- historical_performance_result: (user_id, cycle_name)

upgrade 前先用 SQL 查重，发现存量重复数据直接 raise 报错（列出表名与重复数），
不自动删数据，需人工清理后重跑。

Revision ID: f6c28915470c
Revises: f3fe9643b818
Create Date: 2026-08-05 10:50:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6c28915470c"
down_revision: Union[str, None] = "f3fe9643b818"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (表名, 唯一键列, 约束名)
_UNIQUE_KEYS: list[tuple[str, tuple[str, ...], str]] = [
    ("cycle_participant", ("cycle_id", "user_id"), "uq_cycle_participant_cycle_user"),
    (
        "objective_cycle_participant",
        ("objective_cycle_id", "user_id"),
        "uq_objective_cycle_participant_cycle_user",
    ),
    ("probation_plan", ("user_id",), "uq_probation_plan_user"),
    (
        "historical_performance_result",
        ("user_id", "cycle_name"),
        "uq_historical_perf_user_cycle",
    ),
]


def _check_no_duplicates() -> None:
    """upgrade 前查重：任一表存在重复唯一键则 raise，不自动删数据。"""
    conn = op.get_bind()
    errors: list[str] = []
    for table, columns, _ in _UNIQUE_KEYS:
        cols = ", ".join(columns)
        dup_count = conn.execute(
            sa.text(
                f"SELECT COUNT(*) FROM ("
                f"SELECT {cols} FROM {table} GROUP BY {cols} HAVING COUNT(*) > 1"
                f") t"
            )
        ).scalar_one()
        if dup_count:
            errors.append(f"{table}: {dup_count} 组重复 ({cols})")
    if errors:
        raise RuntimeError(
            "存在存量重复数据，请先人工清理后再执行本迁移: " + "; ".join(errors)
        )


def upgrade() -> None:
    _check_no_duplicates()
    for table, columns, name in _UNIQUE_KEYS:
        op.create_unique_constraint(name, table, list(columns))


def downgrade() -> None:
    for table, _, name in reversed(_UNIQUE_KEYS):
        op.drop_constraint(name, table, type_="unique")
