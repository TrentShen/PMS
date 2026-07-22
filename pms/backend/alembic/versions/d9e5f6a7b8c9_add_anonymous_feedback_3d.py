"""add anonymous feedback 3d value grades

Revision ID: d9e5f6a7b8c9
Revises: c8d4e5f6a7b8
Create Date: 2026-07-14 21:30:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d9e5f6a7b8c9"
down_revision: Union[str, None] = "c8d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("anonymous_feedback", sa.Column("value_belief_grade", sa.String(length=8), nullable=True))
    op.add_column("anonymous_feedback", sa.Column("value_team_grade", sa.String(length=8), nullable=True))
    op.add_column("anonymous_feedback", sa.Column("value_growth_grade", sa.String(length=8), nullable=True))


def downgrade() -> None:
    op.drop_column("anonymous_feedback", "value_growth_grade")
    op.drop_column("anonymous_feedback", "value_team_grade")
    op.drop_column("anonymous_feedback", "value_belief_grade")
