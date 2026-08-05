from __future__ import annotations

"""dept_leader 可见范围放宽回归测试（2026-08-05）。

1. GET /cycles/{id}/users/{uid}/peer/summary：
   dept_leader 可看本部门（含隔级）成员的互评汇总，非本部门成员仍 403。
2. GET /cycles：
   Leader 可看到有直系下属参与的周期（即使自己不是参与人）。
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select, text

from pms.database.models.cycle import PerformanceCycle
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


def _user_id(wecom_userid: str) -> int:
    with Session(engine) as session:
        user = session.exec(select(User).where(User.wecom_userid == wecom_userid)).first()
        assert user and user.id
        return user.id


def _seed_cycle_id() -> int:
    with Session(engine) as session:
        cycle = session.exec(select(PerformanceCycle)).first()
        assert cycle and cycle.id
        return cycle.id


def test_dept_leader_sees_indirect_report_peer_summary(client: TestClient) -> None:
    """dept_leader 可看本部门隔级成员（非直属下属）的互评汇总。"""
    cycle_id = _seed_cycle_id()
    bob_id = _user_id("mock-bob")

    # 把 bob 的直属上级改为 alice，使 bob 成为 tech-leader 的隔级成员
    with Session(engine) as session:
        bob = session.get(User, bob_id)
        assert bob
        bob.leader_userid = "mock-alice"
        session.add(bob)
        session.commit()

    tech_leader_token = _login(client, "mock-tech-leader")
    resp = client.get(
        f"/api/v1/cycles/{cycle_id}/users/{bob_id}/peer/summary",
        headers=_headers(tech_leader_token),
    )
    assert resp.status_code == 200, resp.text


def test_dept_leader_still_403_for_other_dept_peer_summary(client: TestClient) -> None:
    """dept_leader 看非本部门成员的互评汇总仍 403（口径与校准视图一致）。"""
    cycle_id = _seed_cycle_id()
    carol_id = _user_id("mock-carol")  # 产品部员工

    tech_leader_token = _login(client, "mock-tech-leader")
    resp = client.get(
        f"/api/v1/cycles/{cycle_id}/users/{carol_id}/peer/summary",
        headers=_headers(tech_leader_token),
    )
    assert resp.status_code == 403, resp.text


def test_leader_sees_cycle_with_participating_subordinate(client: TestClient) -> None:
    """Leader 的周期列表包含有直系下属参与的周期；无关员工看不到。"""
    hr_token = _login(client, "mock-hr")
    resp = client.post(
        "/api/v1/cycles",
        headers=_headers(hr_token),
        json={"name": "Leader可见性回归周期", "start_date": "2025-07-01", "end_date": "2025-12-31"},
    )
    assert resp.status_code == 200, resp.text
    cycle_id = resp.json()["id"]

    # alice（tech-leader 的直系下属）加入该周期
    alice_id = _user_id("mock-alice")
    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/participants",
        headers=_headers(hr_token),
        json={"user_ids": [alice_id]},
    )
    assert resp.status_code == 200, resp.text

    # tech-leader 自己不是参与人，但因 alice 是参与人，应看到该周期
    tech_leader_token = _login(client, "mock-tech-leader")
    resp = client.get("/api/v1/cycles", headers=_headers(tech_leader_token))
    assert resp.status_code == 200, resp.text
    assert cycle_id in [c["id"] for c in resp.json()]

    # david（产品部员工）与该周期无关，不应看到
    david_token = _login(client, "mock-david")
    resp = client.get("/api/v1/cycles", headers=_headers(david_token))
    assert resp.status_code == 200, resp.text
    assert cycle_id not in [c["id"] for c in resp.json()]
