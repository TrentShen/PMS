from __future__ import annotations

"""R4 修复：绩效周期开关、匿名评价可见性、发布前反馈校验。

覆盖：
- 流程开关关闭时相关接口返回 400
- 匿名主动评价仅 HR/部门 Leader/超管可见，直属上级不可见
- publish_cycle 在开启反馈时校验反馈闭环
- 关闭校准时发布不需要审批
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select, text

from pms.database.models import User
from pms.database.session import engine
from pms.main import app
from pms.services.seed import seed


@pytest.fixture(autouse=True)
def setup_database():
    """每个测试前清空业务表并重新 seed。"""
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


def _name_by_id(user_id: int) -> str:
    with Session(engine) as session:
        user = session.get(User, user_id)
    if user is None:
        raise ValueError(f"未知 user_id: {user_id}")
    name_map = {
        "mock-alice": "alice",
        "mock-bob": "bob",
        "mock-carol": "carol",
        "mock-david": "david",
    }
    return name_map.get(user.wecom_userid, user.wecom_userid.replace("mock-", ""))


SELF_EVAL_PAYLOAD = {
    "perf_score": 3.75,
    "value_belief_grade": "yi",
    "value_belief_example": None,
    "value_team_grade": "jia",
    "value_team_example": "协作良好",
    "value_growth_grade": "yi",
    "value_growth_example": None,
    "key_results": "完成目标",
    "comment": None,
}

FEEDBACK_PAYLOAD = {
    "strengths": "执行力强",
    "improvements": "加强沟通",
    "next_goals": "下季度目标",
}


def _create_cycle(client: TestClient, hr_token: str, **overrides) -> int:
    payload = {
        "name": "R4 开关测试周期",
        "start_date": "2025-07-01",
        "end_date": "2025-12-31",
        "enable_self_eval": True,
        "enable_peer_eval": True,
        "enable_calibration": True,
        "enable_feedback": True,
    }
    payload.update(overrides)
    resp = client.post("/api/v1/cycles", headers=_headers(hr_token), json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _add_participants(client: TestClient, hr_token: str, cycle_id: int, user_ids: list[int]) -> None:
    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/participants",
        headers=_headers(hr_token),
        json={"user_ids": user_ids},
    )
    assert resp.status_code == 200, resp.text


def _start_cycle(client: TestClient, hr_token: str, cycle_id: int) -> None:
    resp = client.post(f"/api/v1/cycles/{cycle_id}/start", headers=_headers(hr_token))
    assert resp.status_code == 200, resp.text


def _update_cycle(client: TestClient, hr_token: str, cycle_id: int, **kwargs) -> None:
    resp = client.put(
        f"/api/v1/cycles/{cycle_id}",
        headers=_headers(hr_token),
        json=kwargs,
    )
    assert resp.status_code == 200, resp.text


OBJECTIVES_PAYLOAD = {
    "items": [
        {
            "title": "核心项目交付",
            "description": "按期交付",
            "measure_criteria": "里程碑达成",
            "weight": 40,
        },
        {
            "title": "协作与沟通",
            "description": "跨团队协作",
            "measure_criteria": "无投诉",
            "weight": 30,
        },
        {
            "title": "能力提升",
            "description": "学习落地",
            "measure_criteria": "有案例",
            "weight": 30,
        },
    ]
}


def _write_objectives(client: TestClient, cycle_id: int, user_id: int) -> None:
    token = _login(client, f"mock-{_name_by_id(user_id)}")
    resp = client.put(
        f"/api/v1/cycles/{cycle_id}/objectives",
        headers=_headers(token),
        json=OBJECTIVES_PAYLOAD,
    )
    assert resp.status_code == 200, resp.text


def _submit_self_eval(client: TestClient, cycle_id: int, user_id: int) -> None:
    _write_objectives(client, cycle_id, user_id)
    token = _login(client, f"mock-{_name_by_id(user_id)}")
    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/self-evaluation",
        headers=_headers(token),
        json=SELF_EVAL_PAYLOAD,
    )
    assert resp.status_code == 200, resp.text


def _submit_superior_eval(client: TestClient, cycle_id: int, subordinate_id: int, leader_uid: str) -> None:
    token = _login(client, leader_uid)
    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/users/{subordinate_id}/superior-evaluation",
        headers=_headers(token),
        json={
            "perf_score": 3.5,
            "value_belief_grade": "yi",
            "value_belief_example": None,
            "value_team_grade": "yi",
            "value_team_example": None,
            "value_growth_grade": "yi",
            "value_growth_example": None,
            "key_results": "达预期",
            "comment": None,
        },
    )
    assert resp.status_code == 200, resp.text


def test_self_eval_disabled_returns_400(client: TestClient) -> None:
    uids = _user_ids(client)
    hr_token = _login(client, "mock-hr")
    cycle_id = _create_cycle(client, hr_token)
    _add_participants(client, hr_token, cycle_id, [uids["mock-alice"]])
    _start_cycle(client, hr_token, cycle_id)
    _update_cycle(client, hr_token, cycle_id, enable_self_eval=False)

    token = _login(client, "mock-alice")
    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/self-evaluation",
        headers=_headers(token),
        json=SELF_EVAL_PAYLOAD,
    )
    assert resp.status_code == 400
    assert "未开启自评" in resp.json()["detail"]


def test_peer_eval_disabled_returns_400(client: TestClient) -> None:
    uids = _user_ids(client)
    hr_token = _login(client, "mock-hr")
    cycle_id = _create_cycle(client, hr_token)
    _add_participants(client, hr_token, cycle_id, [uids["mock-alice"], uids["mock-bob"]])
    _start_cycle(client, hr_token, cycle_id)

    _submit_self_eval(client, cycle_id, uids["mock-alice"])
    _update_cycle(client, hr_token, cycle_id, enable_peer_eval=False)

    token = _login(client, "mock-alice")
    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/peer/invite",
        headers=_headers(token),
        json={"peer_user_ids": [uids["mock-bob"]]},
    )
    assert resp.status_code == 400
    assert "未开启互评" in resp.json()["detail"]


def test_calibration_disabled_returns_400(client: TestClient) -> None:
    uids = _user_ids(client)
    hr_token = _login(client, "mock-hr")
    cycle_id = _create_cycle(client, hr_token)
    _add_participants(client, hr_token, cycle_id, [uids["mock-alice"]])
    _start_cycle(client, hr_token, cycle_id)

    _submit_self_eval(client, cycle_id, uids["mock-alice"])
    _submit_superior_eval(client, cycle_id, uids["mock-alice"], "mock-tech-leader")
    _update_cycle(client, hr_token, cycle_id, enable_calibration=False)

    leader_token = _login(client, "mock-tech-leader")
    resp = client.post(
        f"/api/v1/calibration/cycles/{cycle_id}/calibrate",
        headers=_headers(leader_token),
        json={
            "items": [
                {
                    "user_id": uids["mock-alice"],
                    "perf_score": 4.0,
                    "value_belief_grade": "jia",
                    "value_team_grade": "yi",
                    "value_growth_grade": "yi",
                    "reason": "test",
                }
            ]
        },
    )
    assert resp.status_code == 400
    assert "未开启校准" in resp.json()["detail"]

    resp = client.post(
        f"/api/v1/calibration/cycles/{cycle_id}/submit-calibration",
        headers=_headers(leader_token),
    )
    assert resp.status_code == 400
    assert "未开启校准" in resp.json()["detail"]


def test_publish_without_calibration_skips_approval(client: TestClient) -> None:
    uids = _user_ids(client)
    hr_token = _login(client, "mock-hr")
    cycle_id = _create_cycle(client, hr_token, enable_calibration=False, enable_feedback=False)
    _add_participants(client, hr_token, cycle_id, [uids["mock-alice"]])
    _start_cycle(client, hr_token, cycle_id)

    _submit_self_eval(client, cycle_id, uids["mock-alice"])
    _submit_superior_eval(client, cycle_id, uids["mock-alice"], "mock-tech-leader")

    # 上级评估会写入 CycleParticipant.final_perf_score，因此关闭校准时可直接发布。
    # 验证：关闭 calibration 后 publish 不会因为缺少 CycleApproval 而 400。
    resp = client.post(f"/api/v1/cycles/{cycle_id}/publish", headers=_headers(hr_token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "published"


def test_feedback_disabled_returns_400(client: TestClient) -> None:
    uids = _user_ids(client)
    hr_token = _login(client, "mock-hr")
    cycle_id = _create_cycle(client, hr_token)
    _add_participants(client, hr_token, cycle_id, [uids["mock-alice"]])
    _start_cycle(client, hr_token, cycle_id)
    _update_cycle(client, hr_token, cycle_id, enable_feedback=False)

    leader_token = _login(client, "mock-tech-leader")
    resp = client.post(
        f"/api/v1/feedback/cycles/{cycle_id}/users/{uids['mock-alice']}",
        headers=_headers(leader_token),
        json=FEEDBACK_PAYLOAD,
    )
    assert resp.status_code == 400
    assert "未开启绩效反馈" in resp.json()["detail"]


def test_publish_requires_feedback_confirmation(client: TestClient) -> None:
    uids = _user_ids(client)
    hr_token = _login(client, "mock-hr")
    cycle_id = _create_cycle(client, hr_token)
    _add_participants(client, hr_token, cycle_id, [uids["mock-alice"]])
    _start_cycle(client, hr_token, cycle_id)

    # 完成自评、上级评估、校准、审批
    _submit_self_eval(client, cycle_id, uids["mock-alice"])
    _submit_superior_eval(client, cycle_id, uids["mock-alice"], "mock-tech-leader")

    leader_token = _login(client, "mock-tech-leader")
    client.post(
        f"/api/v1/calibration/cycles/{cycle_id}/calibrate",
        headers=_headers(leader_token),
        json={
            "items": [
                {
                    "user_id": uids["mock-alice"],
                    "perf_score": 4.0,
                    "value_belief_grade": "jia",
                    "value_team_grade": "yi",
                    "value_growth_grade": "yi",
                    "reason": "test",
                }
            ]
        },
    )
    client.post(
        f"/api/v1/calibration/cycles/{cycle_id}/submit-calibration",
        headers=_headers(leader_token),
    )
    hr_token2 = _login(client, "mock-hr")
    client.post(
        f"/api/v1/calibration/cycles/{cycle_id}/approval",
        headers=_headers(hr_token2),
        json={"action": "approve"},
    )
    ceo_token = _login(client, "mock-ceo")
    client.post(
        f"/api/v1/calibration/cycles/{cycle_id}/approval",
        headers=_headers(ceo_token),
        json={"action": "approve"},
    )

    # 填写反馈但不确认
    client.post(
        f"/api/v1/feedback/cycles/{cycle_id}/users/{uids['mock-alice']}",
        headers=_headers(leader_token),
        json=FEEDBACK_PAYLOAD,
    )

    # 发布应失败
    resp = client.post(f"/api/v1/cycles/{cycle_id}/publish", headers=_headers(hr_token2))
    assert resp.status_code == 400
    assert "未完成绩效反馈确认" in resp.json()["detail"]


def test_anonymous_feedback_not_visible_to_direct_leader(client: TestClient) -> None:
    uids = _user_ids(client)
    hr_token = _login(client, "mock-hr")
    cycle_id = _create_cycle(client, hr_token)
    _add_participants(client, hr_token, cycle_id, [uids["mock-alice"], uids["mock-bob"]])
    _start_cycle(client, hr_token, cycle_id)

    # bob 匿名评价 alice
    bob_token = _login(client, "mock-bob")
    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/anonymous-feedback",
        headers=_headers(bob_token),
        json={"target_user_id": uids["mock-alice"], "comment": "匿名评语"},
    )
    assert resp.status_code == 200, resp.text

    # 将 mock-tech-leader 临时改为 direct_leader（仍是他下属 alice 的直属上级，但不是部门 Leader）
    with Session(engine) as session:
        tech_leader = session.exec(
            select(User).where(User.wecom_userid == "mock-tech-leader")
        ).first()
        assert tech_leader is not None
        original_role = tech_leader.role
        tech_leader.role = "direct_leader"
        session.add(tech_leader)
        session.commit()

    try:
        # direct_leader 可查看下属的 peer summary，但匿名评价对直属上级不可见
        direct_leader_token = _login(client, "mock-tech-leader")
        resp = client.get(
            f"/api/v1/cycles/{cycle_id}/users/{uids['mock-alice']}/peer/summary",
            headers=_headers(direct_leader_token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["anonymous_feedback"] is None

        # HR 可以查看匿名评价
        hr_token2 = _login(client, "mock-hr")
        resp = client.get(
            f"/api/v1/cycles/{cycle_id}/users/{uids['mock-alice']}/peer/summary",
            headers=_headers(hr_token2),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["anonymous_feedback"] is not None
        assert len(resp.json()["anonymous_feedback"]) == 1
    finally:
        with Session(engine) as session:
            tech_leader = session.exec(
                select(User).where(User.wecom_userid == "mock-tech-leader")
            ).first()
            tech_leader.role = original_role
            session.add(tech_leader)
            session.commit()
