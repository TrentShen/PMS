from __future__ import annotations

"""绩效周期相关接口测试。"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, text

from pms.database.models import CycleParticipant, PerformanceCycle, User
from pms.database.session import engine
from pms.main import app
from pms.services.seed import seed


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """清空业务表并重新 seed，确保测试独立。"""
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


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _login(client: TestClient, wecom_userid: str) -> str:
    resp = client.post("/api/v1/auth/mock-login", json={"wecom_userid": wecom_userid})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_close_cycle_marks_unfinished_as_excluded(client: TestClient) -> None:
    """归档 published 周期时，未完成的参与人应被标记为 excluded。"""
    hr_token = _login(client, "mock-hr")
    headers = _headers(hr_token)

    # 创建周期并添加参与人
    resp = client.post(
        "/api/v1/cycles",
        headers=headers,
        json={"name": "2025 测试归档", "start_date": "2025-07-01", "end_date": "2025-12-31"},
    )
    assert resp.status_code == 200, resp.text
    cycle_id = resp.json()["id"]

    with Session(engine) as session:
        users = session.exec(
            text("SELECT id, wecom_userid FROM user WHERE wecom_userid IN ('mock-alice', 'mock-bob')")
        ).all()
        user_ids = [u.id for u in users]

    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/participants",
        headers=headers,
        json={"user_ids": user_ids},
    )
    assert resp.status_code == 200, resp.text

    # 启动周期
    resp = client.post(f"/api/v1/cycles/{cycle_id}/start", headers=headers)
    assert resp.status_code == 200, resp.text

    # 直接改数据库模拟一个已完成、一个未完成
    with Session(engine) as session:
        participants = session.exec(
            text(f"SELECT id, user_id FROM cycle_participant WHERE cycle_id = {cycle_id}")
        ).all()
        assert len(participants) == 2
        for p in participants:
            if p.user_id == user_ids[0]:
                session.exec(
                    text(
                        f"UPDATE cycle_participant SET status = 'published', "
                        f"final_perf_score = 4.0, final_perf_level = 'meet' WHERE id = {p.id}"
                    )
                )
        session.commit()

    # 先把周期改为 published（绕过正常审批流程，直接改库）
    with Session(engine) as session:
        cycle = session.get(PerformanceCycle, cycle_id)
        cycle.status = "published"
        session.add(cycle)
        session.commit()

    # 调用归档接口
    resp = client.post(f"/api/v1/cycles/{cycle_id}/close", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "closed"

    with Session(engine) as session:
        participants = session.exec(
            text(f"SELECT user_id, status FROM cycle_participant WHERE cycle_id = {cycle_id}")
        ).all()
        status_by_user = {p.user_id: p.status for p in participants}

    assert status_by_user[user_ids[0]] == "published"
    assert status_by_user[user_ids[1]] == "excluded"


def test_close_cycle_requires_published(client: TestClient) -> None:
    """只有 published 周期才能归档。"""
    hr_token = _login(client, "mock-hr")
    headers = _headers(hr_token)

    resp = client.post(
        "/api/v1/cycles",
        headers=headers,
        json={"name": "2025 测试归档状态校验", "start_date": "2025-07-01", "end_date": "2025-12-31"},
    )
    assert resp.status_code == 200, resp.text
    cycle_id = resp.json()["id"]

    resp = client.post(f"/api/v1/cycles/{cycle_id}/close", headers=headers)
    assert resp.status_code == 400
    assert "当前状态" in resp.json()["detail"]
