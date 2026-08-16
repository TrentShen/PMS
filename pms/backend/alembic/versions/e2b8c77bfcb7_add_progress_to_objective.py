"""add_progress_to_objective

Revision ID: e2b8c77bfcb7
Revises: f6c28915470c
Create Date: 2026-08-15 19:26:14.725909

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e2b8c77bfcb7'
down_revision: Union[str, None] = 'f6c28915470c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 人工 review：已剔除 autogenerate 带入的无关表漂移（historical_* 的 alter_column），
    # 仅保留本次 objective.progress 新增；存量行回填 0
    op.add_column(
        'objective',
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('objective', 'progress')
