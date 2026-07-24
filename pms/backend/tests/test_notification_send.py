from __future__ import annotations

"""通知发送链路回归测试：企微假成功、EMAIL 通道、反馈列表批量加载。"""

from collections.abc import Callable
from datetime import date
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from pms.database.models.audit import NotificationLog
from pms.database.models.cycle import CycleParticipant, PerformanceCycle
from pms.database.models.feedback import FeedbackRecord
from pms.database.models.user import User
from pms.database.session import engine
from pms.services import wecom
from pms.services.notification import NotificationChannel, send_notification


def _login(client: TestClient, wecom_userid: str) -> str:
    resp = client.post("/api/v1/auth/mock-login", json={"wecom_userid": wecom_userid})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _delete_logs_by_title(title: str) -> None:
    with Session(engine) as session:
        rows = session.exec(select(NotificationLog).where(NotificationLog.title == title)).all()
        for row in rows:
            session.delete(row)
        session.commit()


# ---------- 修复1：企微 errcode != 0 时发送函数必须 raise ----------

def test_wecom_send_raises_on_errcode(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(
        url: str,
        json_body: dict,
        params: dict | None = None,
        *,
        use_contact_token: bool = False,
    ) -> dict:
        return {"errcode": 40014, "errmsg": "invalid access_token"}

    monkeypatch.setattr(wecom, "_post", fake_post)

    sends: list[Callable[[], Any]] = [
        lambda: wecom.send_text(["u1"], "hi"),
        lambda: wecom.send_textcard(["u1"], "t", "d", "https://example.com"),
        lambda: wecom.send_markdown(["u1"], "hi"),
    ]
    for send in sends:
        with pytest.raises(wecom.WecomSendError) as exc_info:
            send()
        assert exc_info.value.errcode == 40014
        assert "invalid access_token" in str(exc_info.value)


def test_wecom_send_ok_on_errcode_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wecom, "_post", lambda *args, **kwargs: {"errcode": 0, "errmsg": "ok"})
    data = wecom.send_text(["u1"], "hi")
    assert data["errcode"] == 0


# ---------- 修复2：EMAIL 通道不受企微配置影响，SMTP 失败标 failed ----------

@pytest.fixture
def alice_with_email():
    with Session(engine) as session:
        alice = session.exec(select(User).where(User.wecom_userid == "mock-alice")).first()
        assert alice
        original_email = alice.email
        alice.email = "alice-notify-test@example.com"
        session.add(alice)
        session.commit()
    yield
    with Session(engine) as session:
        alice = session.exec(select(User).where(User.wecom_userid == "mock-alice")).first()
        if alice:
            alice.email = original_email
            session.add(alice)
            session.commit()


def test_email_channel_marks_failed_when_send_email_false(alice_with_email: None) -> None:
    title = "邮件失败回归"
    try:
        with patch("pms.services.email.send_email", return_value=False):
            send_notification(
                target_userids=["mock-alice"],
                title=title,
                content="内容",
                channel=NotificationChannel.EMAIL,
            )
        with Session(engine) as session:
            rows = session.exec(select(NotificationLog).where(NotificationLog.title == title)).all()
        assert len(rows) == 1
        assert rows[0].status == "failed"
        assert rows[0].error_msg
    finally:
        _delete_logs_by_title(title)


def test_email_channel_not_blocked_by_wecom_config(alice_with_email: None) -> None:
    """企微配置缺失不应影响 EMAIL 通道发送。"""
    title = "邮件不受企微配置影响回归"
    try:
        with (
            patch("pms.services.notification._wecom_configured", return_value=False),
            patch("pms.services.email.send_email", return_value=True),
        ):
            send_notification(
                target_userids=["mock-alice"],
                title=title,
                content="内容",
                channel=NotificationChannel.EMAIL,
            )
        with Session(engine) as session:
            rows = session.exec(select(NotificationLog).where(NotificationLog.title == title)).all()
        assert len(rows) == 1
        assert rows[0].status == "sent"
    finally:
        _delete_logs_by_title(title)


# ---------- 修复4：list_feedback_status 批量加载后结果保持正确 ----------

def test_list_feedback_status(client: TestClient) -> None:
    token = _login(client, "mock-hr")

    with Session(engine) as session:
        alice = session.exec(select(User).where(User.wecom_userid == "mock-alice")).first()
        bob = session.exec(select(User).where(User.wecom_userid == "mock-bob")).first()
        assert alice and bob
        alice_id, bob_id = alice.id, bob.id

        cycle = PerformanceCycle(
            name="反馈列表N+1回归周期",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            status="in_progress",
            created_by="mock-hr",
        )
        session.add(cycle)
        session.commit()
        session.refresh(cycle)
        cycle_id = cycle.id

        session.add_all([
            CycleParticipant(cycle_id=cycle_id, user_id=alice_id),
            CycleParticipant(cycle_id=cycle_id, user_id=bob_id),
        ])
        session.add(FeedbackRecord(
            cycle_id=cycle_id,
            user_id=alice_id,
            interviewer_userid="mock-tech-leader",
            interviewer_name="王 Leader",
            strengths="优势",
            improvements="待改进",
            next_goals="下阶段目标",
            confirm_status="confirmed",
        ))
        session.commit()

    try:
        resp = client.get(f"/api/v1/feedback/cycles/{cycle_id}/list", headers=_headers(token))
        assert resp.status_code == 200, resp.text
        rows = {r["user_id"]: r for r in resp.json()}
        assert rows[alice_id]["has_feedback"] is True
        assert rows[alice_id]["confirm_status"] == "confirmed"
        assert rows[bob_id]["has_feedback"] is False
        assert rows[bob_id]["confirm_status"] is None
    finally:
        with Session(engine) as session:
            for row in session.exec(select(FeedbackRecord).where(FeedbackRecord.cycle_id == cycle_id)).all():
                session.delete(row)
            for row in session.exec(select(CycleParticipant).where(CycleParticipant.cycle_id == cycle_id)).all():
                session.delete(row)
            cycle = session.get(PerformanceCycle, cycle_id)
            if cycle:
                session.delete(cycle)
            session.commit()
