from __future__ import annotations

"""匿名评价三维度测试。"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select, text

from pms.database.models.peer import AnonymousFeedback
from pms.database.models.user import User
from pms.database.session import engine
from pms.main import app
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


def _user_ids(client: TestClient) -> dict[str, int]:
    token = _login(client, "mock-hr")
    resp = client.get("/api/v1/auth/mock-users", headers=_headers(token))
    assert resp.status_code == 200, resp.text
    return {u["wecom_userid"]: u["id"] for u in resp.json()}


def _create_cycle(client: TestClient, hr_token: str) -> int:
    resp = client.post(
        "/api/v1/cycles",
        headers=_headers(hr_token),
        json={
            "name": "匿名评价三维度测试",
            "start_date": "2025-07-01",
            "end_date": "2025-12-31",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def test_anonymous_feedback_3d_submit_and_summary(client: TestClient) -> None:
    uids = _user_ids(client)
    hr_token = _login(client, "mock-hr")
    cycle_id = _create_cycle(client, hr_token)

    # 添加参与人并启动周期
    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/participants",
        headers=_headers(hr_token),
        json={"user_ids": [uids["mock-alice"], uids["mock-bob"]]},
    )
    assert resp.status_code == 200, resp.text
    resp = client.post(f"/api/v1/cycles/{cycle_id}/start", headers=_headers(hr_token))
    assert resp.status_code == 200, resp.text

    # bob 匿名评价 alice（三维度）
    bob_token = _login(client, "mock-bob")
    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/anonymous-feedback",
        headers=_headers(bob_token),
        json={
            "target_user_id": uids["mock-alice"],
            "perf_score": 4.25,
            "value_belief_grade": "jia",
            "value_team_grade": "yi",
            "value_growth_grade": "bing",
            "comment": "表现优秀",
        },
    )
    assert resp.status_code == 200, resp.text

    # HR 查看 summary 应看到三维度
    resp = client.get(
        f"/api/v1/cycles/{cycle_id}/users/{uids['mock-alice']}/peer/summary",
        headers=_headers(hr_token),
    )
    assert resp.status_code == 200, resp.text
    anon = resp.json()["anonymous_feedback"]
    assert anon is not None
    assert len(anon) == 1
    assert anon[0]["perf_score"] == 4.25
    assert anon[0]["value_belief_grade"] == "jia"
    assert anon[0]["value_team_grade"] == "yi"
    assert anon[0]["value_growth_grade"] == "bing"

    # 数据库验证
    with Session(engine) as session:
        fb = session.exec(
            select(AnonymousFeedback).where(
                AnonymousFeedback.cycle_id == cycle_id,
                AnonymousFeedback.target_user_id == uids["mock-alice"],
            )
        ).first()
        assert fb is not None
        assert fb.value_belief_grade == "jia"
        assert fb.value_team_grade == "yi"
        assert fb.value_growth_grade == "bing"


def test_anonymous_feedback_legacy_value_grade(client: TestClient) -> None:
    """兼容旧单维度 value_grade 字段。"""
    uids = _user_ids(client)
    hr_token = _login(client, "mock-hr")
    cycle_id = _create_cycle(client, hr_token)

    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/participants",
        headers=_headers(hr_token),
        json={"user_ids": [uids["mock-alice"], uids["mock-bob"]]},
    )
    assert resp.status_code == 200, resp.text
    resp = client.post(f"/api/v1/cycles/{cycle_id}/start", headers=_headers(hr_token))
    assert resp.status_code == 200, resp.text

    bob_token = _login(client, "mock-bob")
    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/anonymous-feedback",
        headers=_headers(bob_token),
        json={
            "target_user_id": uids["mock-alice"],
            "value_grade": "jia",  # 旧单维度字段
            "comment": "兼容测试",
        },
    )
    assert resp.status_code == 200, resp.text

    with Session(engine) as session:
        fb = session.exec(
            select(AnonymousFeedback).where(
                AnonymousFeedback.cycle_id == cycle_id,
                AnonymousFeedback.target_user_id == uids["mock-alice"],
            )
        ).first()
        assert fb is not None
        assert fb.value_grade == "jia"
