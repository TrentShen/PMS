"""add peer_evaluation decline_reason

Revision ID: c5ecc433a069
Revises: d9e5f6a7b8c9
Create Date: 2026-07-24 17:54:33.550333

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'c5ecc433a069'
down_revision: Union[str, None] = 'd9e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('peer_evaluation', sa.Column('decline_reason', sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    op.drop_column('peer_evaluation', 'decline_reason')
