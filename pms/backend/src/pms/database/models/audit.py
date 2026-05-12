# 审计日志 + 导出日志 + 消息日志
from datetime import datetime
from typing import Any

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class AuditLog(SQLModel, table=True):
    # 所有敏感写操作留痕（PRD 4.2 安全要求）
    __tablename__ = "audit_log"

    id: int | None = Field(default=None, primary_key=True)
    # 操作人的 wecom_userid
    operator_userid: str = Field(max_length=64, index=True)
    operator_name: str = Field(max_length=64)
    action: str = Field(max_length=64, index=True)  # 如 "submit_self_eval"、"publish_cycle"
    resource_type: str = Field(max_length=64)        # 如 "evaluation"、"cycle"
    resource_id: str = Field(max_length=64)
    # 前后值；JSON 存储便于兼容不同资源
    before_data: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    after_data: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    reason: str | None = Field(default=None, max_length=512)
    ip: str | None = Field(default=None, max_length=64)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class ExportLog(SQLModel, table=True):
    # HRBP 导出留痕（PRD 确认事项：允许导出但记日志）
    __tablename__ = "export_log"

    id: int | None = Field(default=None, primary_key=True)
    operator_userid: str = Field(max_length=64, index=True)
    operator_name: str = Field(max_length=64)
    export_type: str = Field(max_length=32)  # cycle_result / history
    filter_data: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    row_count: int = Field(default=0)
    file_name: str | None = Field(default=None, max_length=256)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class NotificationLog(SQLModel, table=True):
    # 消息下发记录；V0.9 仅写记录不真发（Sprint 1 对接企微应用消息）
    __tablename__ = "notification_log"

    id: int | None = Field(default=None, primary_key=True)
    target_userid: str = Field(max_length=64, index=True)
    channel: str = Field(default="wecom", max_length=16)  # wecom / email
    title: str = Field(max_length=256)
    content: str = ""
    payload: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    status: str = Field(default="pending", max_length=16, index=True)  # pending/sent/failed
    retry_count: int = Field(default=0)
    sent_at: datetime | None = None
    error_msg: str | None = Field(default=None, max_length=1024)
    created_at: datetime = Field(default_factory=datetime.utcnow)
