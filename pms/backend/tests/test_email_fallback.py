from __future__ import annotations

"""邮件降级通知测试。"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select, text

from pms.database.models.audit import NotificationLog
from pms.database.models.user import User
from pms.database.session import engine
from pms.main import app
from pms.services.notification import NotificationChannel, retry_failed_notifications_via_email
from pms.services.seed import seed


@pytest.fixture(autouse=True)
def setup_database():
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        result = conn.execute(text("SHOW TABLES"))
        tables = [row[0] for row in result]
        for table in tables:
            if table != "alembic_version":
                conn.execute(text(f"TRUNCATE TABLE {table}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    seed()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def _login(client: TestClient, wecom_userid: str) -> str:
    resp = client.post("/api/v1/auth/mock-login", json={"wecom_userid": wecom_userid})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_retry_failed_notifications_via_email() -> None:
    from unittest.mock import patch

    with Session(engine) as session:
        alice = session.exec(select(User).where(User.wecom_userid == "mock-alice")).first()
        assert alice
        alice.email = "alice@example.com"
        session.add(alice)

        log = NotificationLog(
            target_userid="mock-alice",
            channel=NotificationChannel.WECOM_TEXTCARD,
            title="测试通知",
            content="测试内容",
            status="failed",
            retry_count=0,
        )
        session.add(log)
        session.commit()

        with patch("pms.services.email.send_email", return_value=True):
            retried = retry_failed_notifications_via_email(session)
        assert retried == 1

        session.refresh(log)
        assert log.status == "sent"
        assert log.channel == NotificationChannel.EMAIL
        assert log.retry_count == 1


def test_retry_failed_notifications_no_email() -> None:
    with Session(engine) as session:
        bob = session.exec(select(User).where(User.wecom_userid == "mock-bob")).first()
        assert bob
        bob.email = None
        session.add(bob)

        log = NotificationLog(
            target_userid="mock-bob",
            channel=NotificationChannel.WECOM_TEXTCARD,
            title="测试通知",
            content="测试内容",
            status="failed",
            retry_count=0,
        )
        session.add(log)
        session.commit()

        retried = retry_failed_notifications_via_email(session)
        assert retried == 0

        session.refresh(log)
        assert log.status == "failed"
        assert log.retry_count == 1
