"""add_potential_level_to_user

Revision ID: 728249b1d6ff
Revises: e2b8c77bfcb7
Create Date: 2026-08-27 14:35:24.529059

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '728249b1d6ff'
down_revision: Union[str, None] = 'e2b8c77bfcb7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 人工 review：已剔除 autogenerate 带入的无关表漂移（historical_* 的 alter_column），
    # 仅保留本次 user.potential_level 新增（可空，存量行即为未评定）
    op.add_column('user', sa.Column('potential_level', sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column('user', 'potential_level')
