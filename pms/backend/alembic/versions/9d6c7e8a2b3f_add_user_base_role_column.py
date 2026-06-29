"""add_user_base_role_column

Revision ID: 9d6c7e8a2b3f
Revises: 8fc0cf4bd137
Create Date: 2026-06-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '9d6c7e8a2b3f'
down_revision: Union[str, None] = '8fc0cf4bd137'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user', sa.Column('base_role', sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column('user', 'base_role')
