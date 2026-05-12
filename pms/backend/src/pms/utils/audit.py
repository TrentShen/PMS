# 审计日志便捷写入
from typing import Any

from sqlmodel import Session

from pms.database.models.audit import AuditLog


def write_audit(
    session: Session,
    *,
    operator_userid: str,
    operator_name: str,
    action: str,
    resource_type: str,
    resource_id: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
    ip: str | None = None,
) -> None:
    # 不立即 commit；留给调用者的事务控制
    log = AuditLog(
        operator_userid=operator_userid,
        operator_name=operator_name,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        before_data=before,
        after_data=after,
        reason=reason,
        ip=ip,
    )
    session.add(log)
