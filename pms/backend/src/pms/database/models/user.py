from __future__ import annotations

# 用户与部门模型
# V0.9 说明：mock 模式下手工 seed 数据；Sprint 1 会从企微通讯录同步
from datetime import date, datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "user"

    id: int | None = Field(default=None, primary_key=True)
    # 企微 userid；mock 模式下用 "mock-xxx" 占位
    wecom_userid: str = Field(unique=True, index=True, max_length=64)
    name: str = Field(max_length=64)
    avatar: str | None = Field(default=None, max_length=512)
    # 所属部门：V0.9 简化为单部门，后续若需多部门再拆关系表
    department_id: int | None = Field(default=None, foreign_key="department.id", index=True)
    position: str | None = Field(default=None, max_length=64)  # 职位名
    level: str | None = Field(default=None, max_length=16)     # 职级（如 P5、M2）
    # 直属上级的 wecom_userid（而非 user.id），方便从企微同步时无 FK 依赖
    leader_userid: str | None = Field(default=None, max_length=64, index=True)
    # 角色；为简化 V0.9 存单个角色，多角色场景再拆 user_role 关系
    role: str = Field(default="employee", max_length=32, index=True)
    # HR 的管辖范围：部门 id 列表；None 或空列表 表示全局可见
    # 仅对 role=hrbp 生效；super_admin 永远全局；其他角色此字段忽略
    hrbp_scope_dept_ids: list[int] | None = Field(default=None, sa_column=Column(JSON))
    hired_at: date | None = None
    # 状态：active / inactive（离职）
    status: str = Field(default="active", max_length=16, index=True)
    synced_at: datetime = Field(default_factory=datetime.utcnow)


class Department(SQLModel, table=True):
    __tablename__ = "department"

    id: int | None = Field(default=None, primary_key=True)
    # 企微部门 id；mock 下自增即可
    wecom_dept_id: int = Field(unique=True, index=True)
    name: str = Field(max_length=128)
    parent_id: int | None = Field(default=None, foreign_key="department.id")
    # 部门负责人的 wecom_userid（PRD 3.1.2 —— 取企微的部门负责人字段）
    leader_userid: str | None = Field(default=None, max_length=64)
    order_num: int = Field(default=0)
