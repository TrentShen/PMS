"""add_weight_to_probation_objective

Revision ID: f3fe9643b818
Revises: e7f8a9b0c1d2
Create Date: 2026-08-04 14:49:42.248707

人工 review：autogenerate 还检出了 historical_* 表的无关漂移（历史遗留，与本次无关），
已剔除，只保留 probation_objective.weight 一列；存量行默认 0。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f3fe9643b818'
down_revision: Union[str, None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'probation_objective',
        sa.Column('weight', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('probation_objective', 'weight')
