from __future__ import annotations

"""绩效周期相关接口测试。"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select, text

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


def test_delete_draft_cycle_success(client: TestClient) -> None:
    """空草稿周期可被删除。"""
    hr_token = _login(client, "mock-hr")
    headers = _headers(hr_token)

    resp = client.post(
        "/api/v1/cycles",
        headers=headers,
        json={"name": "待删除草稿", "start_date": "2025-07-01", "end_date": "2025-12-31"},
    )
    assert resp.status_code == 200, resp.text
    cycle_id = resp.json()["id"]

    resp = client.delete(f"/api/v1/cycles/{cycle_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ok"

    with Session(engine) as session:
        assert session.get(PerformanceCycle, cycle_id) is None


def test_delete_cycle_rejects_non_draft(client: TestClient) -> None:
    """只有草稿状态可删除。"""
    hr_token = _login(client, "mock-hr")
    headers = _headers(hr_token)

    resp = client.post(
        "/api/v1/cycles",
        headers=headers,
        json={"name": "已启动周期", "start_date": "2025-07-01", "end_date": "2025-12-31"},
    )
    assert resp.status_code == 200, resp.text
    cycle_id = resp.json()["id"]

    with Session(engine) as session:
        user = session.exec(select(User).where(User.wecom_userid == "mock-alice")).first()
        session.add(CycleParticipant(cycle_id=cycle_id, user_id=user.id, status="pending"))
        session.commit()

    resp = client.post(f"/api/v1/cycles/{cycle_id}/start", headers=headers)
    assert resp.status_code == 200, resp.text

    resp = client.delete(f"/api/v1/cycles/{cycle_id}", headers=headers)
    assert resp.status_code == 400
    assert "草稿" in resp.json()["detail"]


def test_delete_cycle_preserves_perf_data(client: TestClient) -> None:
    """周期内存在绩效数据时禁止删除，确保数据可找回。"""
    hr_token = _login(client, "mock-hr")
    headers = _headers(hr_token)

    resp = client.post(
        "/api/v1/cycles",
        headers=headers,
        json={"name": "有数据周期", "start_date": "2025-07-01", "end_date": "2025-12-31"},
    )
    assert resp.status_code == 200, resp.text
    cycle_id = resp.json()["id"]

    with Session(engine) as session:
        user = session.exec(select(User).where(User.wecom_userid == "mock-alice")).first()
        assert user
        cp = CycleParticipant(cycle_id=cycle_id, user_id=user.id, status="pending")
        session.add(cp)
        session.commit()
        session.refresh(cp)

        # 模拟产生一条评估记录
        from pms.database.models.evaluation import Evaluation
        session.add(
            Evaluation(
                cycle_id=cycle_id,
                user_id=user.id,
                evaluator_userid=user.wecom_userid,
                eval_type="self",
                perf_score=3.5,
            )
        )
        session.commit()

    resp = client.delete(f"/api/v1/cycles/{cycle_id}", headers=headers)
    assert resp.status_code == 400, resp.text
    assert "绩效数据" in resp.json()["detail"]
    assert "评估" in resp.json()["detail"]

    # 周期和评估记录都应保留
    with Session(engine) as session:
        assert session.get(PerformanceCycle, cycle_id) is not None
        from pms.database.models.evaluation import Evaluation
        assert session.exec(
            select(Evaluation).where(Evaluation.cycle_id == cycle_id)
        ).first() is not None


def test_add_participants_strict_full_time_only(client: TestClient) -> None:
    """仅正式员工可被加入绩效周期；实习生/未同步 employee_type 被跳过。"""
    hr_token = _login(client, "mock-hr")
    headers = _headers(hr_token)

    resp = client.post(
        "/api/v1/cycles",
        headers=headers,
        json={"name": "FTE 过滤", "start_date": "2025-07-01", "end_date": "2025-12-31"},
    )
    assert resp.status_code == 200, resp.text
    cycle_id = resp.json()["id"]

    with Session(engine) as session:
        alice = session.exec(select(User).where(User.wecom_userid == "mock-alice")).first()
        bob = session.exec(select(User).where(User.wecom_userid == "mock-bob")).first()
        alice_id, bob_id = alice.id, bob.id
        # 把 bob 改为实习生；把 alice 的 employee_type 置空模拟未同步
        bob.employee_type = "intern"
        alice.employee_type = None
        session.add(bob)
        session.add(alice)
        session.commit()

    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/participants",
        headers=headers,
        json={"user_ids": [alice_id, bob_id]},
    )
    assert resp.status_code == 200, resp.text
    # 两人都被跳过
    assert resp.json() == []

    with Session(engine) as session:
        alice = session.get(User, alice_id)
        alice.employee_type = "full_time"
        session.add(alice)
        session.commit()

    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/participants",
        headers=headers,
        json={"user_ids": [alice_id]},
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 1


def test_suggest_participants_strict_full_time_only(client: TestClient) -> None:
    """建议参与人列表只返回 full_time 员工。"""
    hr_token = _login(client, "mock-hr")
    headers = _headers(hr_token)

    with Session(engine) as session:
        alice = session.exec(select(User).where(User.wecom_userid == "mock-alice")).first()
        alice_id = alice.id
        original_type = alice.employee_type
        alice.employee_type = None
        session.add(alice)
        session.commit()

    try:
        resp = client.post(
            "/api/v1/cycles/1/suggest-participants",
            headers=headers,
            json={},
        )
        assert resp.status_code == 200, resp.text
        assert all(u["id"] != alice_id for u in resp.json())
    finally:
        with Session(engine) as session:
            alice = session.get(User, alice_id)
            alice.employee_type = original_type
            session.add(alice)
            session.commit()


def test_delete_participant_success(client: TestClient) -> None:
    """无绩效数据的草稿参与人可被删除。"""
    hr_token = _login(client, "mock-hr")
    headers = _headers(hr_token)

    resp = client.post(
        "/api/v1/cycles",
        headers=headers,
        json={"name": "删参与人", "start_date": "2025-07-01", "end_date": "2025-12-31"},
    )
    assert resp.status_code == 200, resp.text
    cycle_id = resp.json()["id"]

    with Session(engine) as session:
        user = session.exec(select(User).where(User.wecom_userid == "mock-alice")).first()
        assert user
        cp = CycleParticipant(cycle_id=cycle_id, user_id=user.id, status="pending")
        session.add(cp)
        session.commit()
        session.refresh(cp)
        participant_id = cp.id

    resp = client.delete(f"/api/v1/cycles/{cycle_id}/participants/{participant_id}", headers=headers)
    assert resp.status_code == 200, resp.text

    with Session(engine) as session:
        assert session.get(CycleParticipant, participant_id) is None


def test_delete_participant_rejects_non_draft(client: TestClient) -> None:
    """只有草稿状态可删除参与人。"""
    hr_token = _login(client, "mock-hr")
    headers = _headers(hr_token)

    resp = client.post(
        "/api/v1/cycles",
        headers=headers,
        json={"name": "已启动删人", "start_date": "2025-07-01", "end_date": "2025-12-31"},
    )
    assert resp.status_code == 200, resp.text
    cycle_id = resp.json()["id"]

    with Session(engine) as session:
        user = session.exec(select(User).where(User.wecom_userid == "mock-alice")).first()
        cp = CycleParticipant(cycle_id=cycle_id, user_id=user.id, status="pending")
        session.add(cp)
        session.commit()
        session.refresh(cp)
        participant_id = cp.id

    resp = client.post(f"/api/v1/cycles/{cycle_id}/start", headers=headers)
    assert resp.status_code == 200, resp.text

    resp = client.delete(f"/api/v1/cycles/{cycle_id}/participants/{participant_id}", headers=headers)
    assert resp.status_code == 400
    assert "草稿" in resp.json()["detail"]


def test_delete_participant_preserves_perf_data(client: TestClient) -> None:
    """参与人已产生绩效数据时禁止删除。"""
    hr_token = _login(client, "mock-hr")
    headers = _headers(hr_token)

    resp = client.post(
        "/api/v1/cycles",
        headers=headers,
        json={"name": "有数据删人", "start_date": "2025-07-01", "end_date": "2025-12-31"},
    )
    assert resp.status_code == 200, resp.text
    cycle_id = resp.json()["id"]

    with Session(engine) as session:
        user = session.exec(select(User).where(User.wecom_userid == "mock-alice")).first()
        cp = CycleParticipant(cycle_id=cycle_id, user_id=user.id, status="pending")
        session.add(cp)
        session.commit()
        session.refresh(cp)
        participant_id = cp.id

        from pms.database.models.evaluation import Evaluation
        session.add(
            Evaluation(
                cycle_id=cycle_id,
                user_id=user.id,
                evaluator_userid=user.wecom_userid,
                eval_type="self",
                perf_score=3.5,
            )
        )
        session.commit()

    resp = client.delete(f"/api/v1/cycles/{cycle_id}/participants/{participant_id}", headers=headers)
    assert resp.status_code == 400, resp.text
    assert "绩效数据" in resp.json()["detail"]

    with Session(engine) as session:
        assert session.get(CycleParticipant, participant_id) is not None
