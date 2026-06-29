"""decouple objective cycle from performance cycle

Revision ID: 1b1a7e062625
Revises: 9d6c7e8a2b3f
Create Date: 2026-06-29 18:31:33.598532

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '1b1a7e062625'
down_revision: Union[str, None] = '9d6c7e8a2b3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. 创建 objective_cycle 表
    op.create_table(
        'objective_cycle',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column('created_by', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_objective_cycle_status'), 'objective_cycle', ['status'], unique=False)

    # 2. 添加 objective_cycle_id 列（先 nullable，数据迁移后再设为非空）
    op.add_column('objective', sa.Column('objective_cycle_id', sa.Integer(), nullable=True))
    op.add_column('objective_revision', sa.Column('objective_cycle_id', sa.Integer(), nullable=True))
    op.add_column('performance_cycle', sa.Column('objective_cycle_id', sa.Integer(), nullable=True))

    # 3. 为每个现有 performance_cycle 生成 objective_cycle
    #    状态映射：draft -> draft, in_progress -> active, published/closed -> completed
    conn.execute(sa.text("""
        INSERT INTO objective_cycle (name, start_date, end_date, status, created_by, created_at, completed_at)
        SELECT
            REPLACE(REPLACE(name, '绩效考核', '目标'), '绩效评估', '目标') AS name,
            start_date,
            end_date,
            CASE status
                WHEN 'draft' THEN 'draft'
                WHEN 'in_progress' THEN 'active'
                ELSE 'completed'
            END AS status,
            created_by,
            created_at,
            CASE WHEN status IN ('published', 'closed') THEN published_at ELSE NULL END AS completed_at
        FROM performance_cycle
    """))

    # 4. 建立 performance_cycle ↔ objective_cycle 的映射关系
    conn.execute(sa.text("""
        UPDATE performance_cycle pc
        JOIN objective_cycle oc ON oc.name = REPLACE(REPLACE(pc.name, '绩效考核', '目标'), '绩效评估', '目标')
        SET pc.objective_cycle_id = oc.id
    """))

    # 5. 迁移 objective.cycle_id -> objective.objective_cycle_id
    conn.execute(sa.text("""
        UPDATE objective o
        JOIN performance_cycle pc ON pc.id = o.cycle_id
        JOIN objective_cycle oc ON oc.name = REPLACE(REPLACE(pc.name, '绩效考核', '目标'), '绩效评估', '目标')
        SET o.objective_cycle_id = oc.id
    """))

    # 6. 迁移 objective_revision.cycle_id -> objective_revision.objective_cycle_id
    conn.execute(sa.text("""
        UPDATE objective_revision r
        JOIN performance_cycle pc ON pc.id = r.cycle_id
        JOIN objective_cycle oc ON oc.name = REPLACE(REPLACE(pc.name, '绩效考核', '目标'), '绩效评估', '目标')
        SET r.objective_cycle_id = oc.id
    """))

    # 7. 删除旧的 cycle_id 列、外键、索引
    op.drop_constraint(op.f('objective_ibfk_1'), 'objective', type_='foreignkey')
    op.drop_index(op.f('ix_objective_cycle_id'), table_name='objective')
    op.drop_column('objective', 'cycle_id')

    op.drop_constraint(op.f('objective_revision_ibfk_1'), 'objective_revision', type_='foreignkey')
    op.drop_index(op.f('ix_objective_revision_cycle_id'), table_name='objective_revision')
    op.drop_column('objective_revision', 'cycle_id')

    # 8. 设置 objective_cycle_id 为非空
    op.alter_column('objective', 'objective_cycle_id', existing_type=sa.Integer(), nullable=False)
    op.alter_column('objective_revision', 'objective_cycle_id', existing_type=sa.Integer(), nullable=False)

    # 9. 创建新的外键和索引
    op.create_index(op.f('ix_objective_objective_cycle_id'), 'objective', ['objective_cycle_id'], unique=False)
    op.create_foreign_key(None, 'objective', 'objective_cycle', ['objective_cycle_id'], ['id'])

    op.create_index(op.f('ix_objective_revision_objective_cycle_id'), 'objective_revision', ['objective_cycle_id'], unique=False)
    op.create_foreign_key(None, 'objective_revision', 'objective_cycle', ['objective_cycle_id'], ['id'])

    op.create_index(op.f('ix_performance_cycle_objective_cycle_id'), 'performance_cycle', ['objective_cycle_id'], unique=False)
    op.create_foreign_key(None, 'performance_cycle', 'objective_cycle', ['objective_cycle_id'], ['id'])


def downgrade() -> None:
    # 注意：downgrade 会丢失 objective_cycle 信息，仅保留结构回退
    op.drop_constraint(None, 'performance_cycle', type_='foreignkey')
    op.drop_index(op.f('ix_performance_cycle_objective_cycle_id'), table_name='performance_cycle')
    op.drop_column('performance_cycle', 'objective_cycle_id')

    op.add_column('objective_revision', sa.Column('cycle_id', mysql.INTEGER(), autoincrement=False, nullable=False))
    op.drop_constraint(None, 'objective_revision', type_='foreignkey')
    op.create_foreign_key(op.f('objective_revision_ibfk_1'), 'objective_revision', 'performance_cycle', ['cycle_id'], ['id'])
    op.drop_index(op.f('ix_objective_revision_objective_cycle_id'), table_name='objective_revision')
    op.create_index(op.f('ix_objective_revision_cycle_id'), 'objective_revision', ['cycle_id'], unique=False)
    op.drop_column('objective_revision', 'objective_cycle_id')

    op.add_column('objective', sa.Column('cycle_id', mysql.INTEGER(), autoincrement=False, nullable=False))
    op.drop_constraint(None, 'objective', type_='foreignkey')
    op.create_foreign_key(op.f('objective_ibfk_1'), 'objective', 'performance_cycle', ['cycle_id'], ['id'])
    op.drop_index(op.f('ix_objective_objective_cycle_id'), table_name='objective')
    op.create_index(op.f('ix_objective_cycle_id'), 'objective', ['cycle_id'], unique=False)
    op.drop_column('objective', 'objective_cycle_id')

    op.drop_index(op.f('ix_objective_cycle_status'), table_name='objective_cycle')
    op.drop_table('objective_cycle')
