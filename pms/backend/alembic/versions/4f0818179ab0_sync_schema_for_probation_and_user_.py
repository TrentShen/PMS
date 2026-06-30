"""sync_schema_for_probation_and_user_fields

Revision ID: 4f0818179ab0
Revises: 40f5265b3aec
Create Date: 2026-06-26 03:27:42.372639

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '4f0818179ab0'
down_revision: Union[str, None] = '40f5265b3aec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(conn, table: str, column: str) -> bool:
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    return result.scalar() is not None


def _table_exists(conn, table: str) -> bool:
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = :table"
        ),
        {"table": table},
    )
    return result.scalar() is not None


def _index_exists(conn, table: str, index: str) -> bool:
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() AND table_name = :table AND index_name = :index"
        ),
        {"table": table, "index": index},
    )
    return result.scalar() is not None


def _fk_exists(conn, table: str, fk: str) -> bool:
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE table_schema = DATABASE() AND table_name = :table AND constraint_name = :fk"
        ),
        {"table": table, "fk": fk},
    )
    return result.scalar() is not None


def upgrade() -> None:
    conn = op.get_bind()

    # probation_plan / probation_objective 已在 40f5265b3aec 中创建
    if not _table_exists(conn, "probation_plan"):
        op.create_table(
            'probation_plan',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('start_date', sa.Date(), nullable=False),
            sa.Column('end_date', sa.Date(), nullable=False),
            sa.Column('probation_months', sa.Integer(), nullable=True),
            sa.Column('status', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
            sa.Column('objective_submitted_at', sa.DateTime(), nullable=True),
            sa.Column('objective_reviewed_by', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
            sa.Column('objective_reviewed_at', sa.DateTime(), nullable=True),
            sa.Column('evaluation_comment', sa.Text(), nullable=True),
            sa.Column('evaluation_result', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True),
            sa.Column('evaluator_userid', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
            sa.Column('evaluated_at', sa.DateTime(), nullable=True),
            sa.Column('extended_by', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
            sa.Column('extended_at', sa.DateTime(), nullable=True),
            sa.Column('extension_note', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id')
        )
    if not _index_exists(conn, "probation_plan", "ix_probation_plan_user_id"):
        op.create_index(op.f('ix_probation_plan_user_id'), 'probation_plan', ['user_id'], unique=False)

    if not _table_exists(conn, "probation_objective"):
        op.create_table(
            'probation_objective',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('plan_id', sa.Integer(), nullable=False),
            sa.Column('title', sqlmodel.sql.sqltypes.AutoString(length=256), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('measure_criteria', sa.Text(), nullable=True),
            sa.Column('order_num', sa.Integer(), nullable=False),
            sa.Column('status', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
            sa.Column('reviewed_by', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
            sa.Column('reviewed_at', sa.DateTime(), nullable=True),
            sa.Column('reject_reason', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['plan_id'], ['probation_plan.id']),
            sa.PrimaryKeyConstraint('id')
        )
    if not _index_exists(conn, "probation_objective", "ix_probation_objective_plan_id"):
        op.create_index(op.f('ix_probation_objective_plan_id'), 'probation_objective', ['plan_id'], unique=False)

    # 仅当列仍为 text 时才 alter
    col_info = conn.execute(
        sa.text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'objective' AND column_name = 'reject_reason'"
        )
    ).scalar()
    if col_info and col_info.lower() == 'text':
        op.alter_column(
            'objective', 'reject_reason',
            existing_type=mysql.TEXT(collation='utf8mb4_unicode_ci'),
            type_=sqlmodel.sql.sqltypes.AutoString(),
            existing_nullable=True
        )

    reason_type = conn.execute(
        sa.text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'objective_revision' AND column_name = 'reason'"
        )
    ).scalar()
    if reason_type and reason_type.lower() == 'text':
        op.alter_column(
            'objective_revision', 'reason',
            existing_type=mysql.TEXT(collation='utf8mb4_unicode_ci'),
            type_=sqlmodel.sql.sqltypes.AutoString(),
            existing_nullable=False
        )

    reject_type = conn.execute(
        sa.text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'objective_revision' AND column_name = 'reject_reason'"
        )
    ).scalar()
    if reject_type and reject_type.lower() == 'text':
        op.alter_column(
            'objective_revision', 'reject_reason',
            existing_type=mysql.TEXT(collation='utf8mb4_unicode_ci'),
            type_=sqlmodel.sql.sqltypes.AutoString(),
            existing_nullable=True
        )

    if not _fk_exists(conn, "objective_revision", "objective_revision_ibfk_2"):
        op.create_foreign_key(None, 'objective_revision', 'user', ['user_id'], ['id'])
    if not _fk_exists(conn, "objective_revision", "objective_revision_ibfk_3"):
        op.create_foreign_key(None, 'objective_revision', 'performance_cycle', ['cycle_id'], ['id'])

    if not _column_exists(conn, 'user', 'confirm_date'):
        op.add_column('user', sa.Column('confirm_date', sa.Date(), nullable=True))
    if not _column_exists(conn, 'user', 'probation'):
        op.add_column('user', sa.Column('probation', sa.Integer(), nullable=True))
    if not _column_exists(conn, 'user', 'employee_status'):
        op.add_column('user', sa.Column('employee_status', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column('user', 'employee_status')
    op.drop_column('user', 'probation')
    op.drop_column('user', 'confirm_date')
    op.drop_constraint(None, 'objective_revision', type_='foreignkey')
    op.drop_constraint(None, 'objective_revision', type_='foreignkey')
    op.alter_column('objective_revision', 'reject_reason',
               existing_type=sqlmodel.sql.sqltypes.AutoString(),
               type_=mysql.TEXT(collation='utf8mb4_unicode_ci'),
               existing_nullable=True)
    op.alter_column('objective_revision', 'reason',
               existing_type=sqlmodel.sql.sqltypes.AutoString(),
               type_=mysql.TEXT(collation='utf8mb4_unicode_ci'),
               existing_nullable=False)
    op.create_index(op.f('idx_objective_status'), 'objective', ['status'], unique=False)
    op.alter_column('objective', 'reject_reason',
               existing_type=sqlmodel.sql.sqltypes.AutoString(),
               type_=mysql.TEXT(collation='utf8mb4_unicode_ci'),
               existing_nullable=True)
    # probation_plan / probation_objective 属于 40f5265b3aec，不在此处删除
