"""add user email

Revision ID: c8d4e5f6a7b8
Revises: b7c3d2e4f5a6
Create Date: 2026-07-14 21:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c8d4e5f6a7b8"
down_revision: Union[str, None] = "b7c3d2e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("email", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "email")
