"""add_user_base_role

Revision ID: 8fc0cf4bd137
Revises: 1fa2247f205e
Create Date: 2026-06-26 11:54:50.091957

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '8fc0cf4bd137'
down_revision: Union[str, None] = '1fa2247f205e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 该索引在部分环境不存在；其是否存在不影响应用，upgrade 中不做强制删除
    pass


def downgrade() -> None:
    op.create_index(op.f('idx_objective_status'), 'objective', ['status'], unique=False)
