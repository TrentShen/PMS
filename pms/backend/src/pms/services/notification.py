from __future__ import annotations

# 统一消息推送服务
# 支持企微应用消息的 text / textcard / markdown 三种格式
# 所有发送记录写入 NotificationLog，便于追踪和审计
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from loguru import logger
from sqlmodel import Session, select

from pms.configs.settings import settings
from pms.database.models.audit import NotificationLog
from pms.database.models.user import User
from pms.database.session import engine
from pms.services import wecom


class NotificationChannel(StrEnum):
    WECOM_TEXT = "wecom_text"
    WECOM_TEXTCARD = "wecom_textcard"
    WECOM_MARKDOWN = "wecom_markdown"


_NOTIFICATION_CHANNEL_LABELS: dict[str, str] = {
    NotificationChannel.WECOM_TEXT: "企微文本消息",
    NotificationChannel.WECOM_TEXTCARD: "企微文本卡片",
    NotificationChannel.WECOM_MARKDOWN: "企微 Markdown",
}


def _normalize_url(url: str | None) -> str | None:
    """把相对路径补全为前端完整 URL；完整 URL 或空值原样返回。"""
    if not url:
        return None
    url = url.strip()
    if url.startswith(("http://", "https://")):
        return url
    base = settings.frontend_origin.rstrip("/")
    path = url if url.startswith("/") else f"/{url}"
    return f"{base}{path}"


def _wecom_configured() -> bool:
    """检查企微基础配置是否齐全。"""
    return bool(settings.wecom_corpid and settings.wecom_agentid and settings.wecom_secret)


def _resolve_userid(user: User | str) -> str:
    return user.wecom_userid if isinstance(user, User) else user


def send_notification(
    target_userids: list[str] | list[User],
    title: str,
    content: str,
    channel: str = NotificationChannel.WECOM_TEXTCARD,
    url: str | None = None,
    payload: dict[str, Any] | None = None,
) -> list[NotificationLog]:
    """统一消息推送入口。

    - 自动过滤空 userid 并去重
    - 为每个接收人写一条 NotificationLog
    - 调用企微 API 发送；失败记 failed 不抛异常
    - 发送与业务事务解耦：函数自己创建 Session

    Args:
        target_userids: 接收人企微 userid 列表，或 User 对象列表
        title: 消息标题，写入 NotificationLog
        content: 消息内容（textcard 的 description / markdown 的内容）
        channel: 消息通道，默认 wecom_textcard
        url: textcard 跳转链接，支持相对路径或完整 URL
        payload: 业务上下文，写入 NotificationLog.payload

    Returns:
        所有生成的 NotificationLog 记录（含成功/失败）
    """
    if channel not in _NOTIFICATION_CHANNEL_LABELS:
        logger.warning("未知的消息通道: {}", channel)
        return []

    # 解析并过滤接收人
    raw_userids = [_resolve_userid(u) for u in target_userids]
    userids = list(dict.fromkeys(uid.strip() for uid in raw_userids if uid and uid.strip()))
    if not userids:
        logger.debug("消息无有效接收人，跳过发送: title={}", title)
        return []

    full_url = _normalize_url(url)
    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        logs: list[NotificationLog] = []
        for userid in userids:
            log = NotificationLog(
                target_userid=userid,
                channel=channel,
                title=title,
                content=content,
                payload=payload,
                status="pending",
                retry_count=0,
                created_at=now,
            )
            session.add(log)
            logs.append(log)
        session.commit()
        for log in logs:
            session.refresh(log)

        # 配置缺失时统一标记失败，避免重复调企微接口
        if not _wecom_configured():
            error = "企微配置不完整（corpid/agentid/secret），消息未发送"
            for log in logs:
                log.status = "failed"
                log.error_msg = error
                log.sent_at = now
            session.commit()
            logger.warning("{}: title={}", error, title)
            return logs

        for log in logs:
            try:
                if channel == NotificationChannel.WECOM_TEXT:
                    wecom.send_text(user_ids=[log.target_userid], content=content)
                elif channel == NotificationChannel.WECOM_TEXTCARD:
                    wecom.send_textcard(
                        user_ids=[log.target_userid],
                        title=title,
                        description=content,
                        url=full_url or settings.frontend_origin,
                        btntxt="查看详情",
                    )
                elif channel == NotificationChannel.WECOM_MARKDOWN:
                    wecom.send_markdown(user_ids=[log.target_userid], content=content)

                log.status = "sent"
                log.sent_at = datetime.now(timezone.utc)
            except Exception as exc:  # noqa: BLE001
                log.status = "failed"
                log.error_msg = str(exc)[:1024]
                log.sent_at = datetime.now(timezone.utc)
                logger.warning(
                    "消息发送失败 [{} -> {}]: {} | {}",
                    channel,
                    log.target_userid,
                    title,
                    exc,
                )

        session.commit()
        return logs


def send_textcard_notification(
    target_userids: list[str] | list[User],
    title: str,
    description: str,
    url: str | None = None,
    payload: dict[str, Any] | None = None,
) -> list[NotificationLog]:
    """发送企微文本卡片消息。"""
    return send_notification(
        target_userids=target_userids,
        title=title,
        content=description,
        channel=NotificationChannel.WECOM_TEXTCARD,
        url=url,
        payload=payload,
    )


def send_markdown_notification(
    target_userids: list[str] | list[User],
    title: str,
    content: str,
    payload: dict[str, Any] | None = None,
) -> list[NotificationLog]:
    """发送企微 Markdown 消息；title 也写入日志方便查询。"""
    return send_notification(
        target_userids=target_userids,
        title=title,
        content=content,
        channel=NotificationChannel.WECOM_MARKDOWN,
        payload=payload,
    )


def send_text_notification(
    target_userids: list[str] | list[User],
    title: str,
    content: str,
    payload: dict[str, Any] | None = None,
) -> list[NotificationLog]:
    """发送企微纯文本消息。"""
    return send_notification(
        target_userids=target_userids,
        title=title,
        content=content,
        channel=NotificationChannel.WECOM_TEXT,
        payload=payload,
    )


def get_hrbp_userids(session: Session, target: User | None = None) -> list[str]:
    """返回 HRBP 的 wecom_userid 列表。

    V1.0 简化实现：返回所有 role=hrbp 且状态 active 的用户。
    后续可结合 target 的 department_id 与 hrbp_scope_dept_ids 做精确匹配。
    """
    stmt = select(User.wecom_userid).where(
        User.role == "hrbp",
        User.status == "active",
    )
    if target and target.department_id:
        # 优先取管辖范围包含该部门的 HRBP；没有则兜底所有 HRBP
        scoped = session.exec(
            stmt.where(
                User.hrbp_scope_dept_ids.isnot(None),  # type: ignore[union-attr]
            )
        ).all()
        # SQLModel 对 JSON 数组 contains 支持有限，这里内存过滤
        matched: list[str] = []
        for userid in scoped:
            user = session.exec(select(User).where(User.wecom_userid == userid)).first()
            if user and user.hrbp_scope_dept_ids and target.department_id in user.hrbp_scope_dept_ids:
                matched.append(userid)
        if matched:
            return matched
    # 单列查询在 SQLModel 中返回标量列表
    return list(session.exec(stmt).all())
