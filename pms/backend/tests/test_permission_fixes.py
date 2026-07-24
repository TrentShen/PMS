from __future__ import annotations

"""权限修复回归测试：
- admin.patch_user：hrbp 不可改他人 role，任何人不可改自己 role，super_admin 可改他人 role
- calibration.calibrate：scope 外用户 403，scope 内正常；非法评分 400（不再 500）
- calibration.submit_calibration：审批已通过后拒绝重复提交（400）
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import text

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


def _create_objective_cycle(client: TestClient, hr_token: str) -> int:
    resp = client.post(
        "/api/v1/objective-cycles",
        headers=_headers(hr_token),
        json={"name": "权限测试目标周期", "start_date": "2025-07-01", "end_date": "2025-12-31"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _create_cycle(client: TestClient, hr_token: str, objective_cycle_id: int) -> int:
    resp = client.post(
        "/api/v1/cycles",
        headers=_headers(hr_token),
        json={
            "name": "权限测试绩效周期",
            "start_date": "2025-07-01",
            "end_date": "2025-12-31",
            "objective_cycle_id": objective_cycle_id,
            "enable_self_eval": True,
            "enable_peer_eval": True,
            "enable_calibration": True,
            "enable_feedback": True,
        },
    )
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


def _setup_calibration_cycle(client: TestClient, participant_uids: list[str]) -> tuple[int, int, dict[str, int]]:
    """创建并启动一个开启校准的周期，返回 (cycle_id, objective_cycle_id, user_ids)。"""
    uids = _user_ids(client)
    hr_token = _login(client, "mock-hr")
    objective_cycle_id = _create_objective_cycle(client, hr_token)
    cycle_id = _create_cycle(client, hr_token, objective_cycle_id)
    _add_participants(client, hr_token, cycle_id, [uids[u] for u in participant_uids])
    _start_cycle(client, hr_token, cycle_id)
    return cycle_id, objective_cycle_id, uids


def _calibrate_item(user_id: int, perf_score: float | None = 4.0) -> dict:
    return {
        "user_id": user_id,
        "perf_score": perf_score,
        "value_belief_grade": None,
        "value_team_grade": None,
        "value_growth_grade": None,
        "reason": "回归测试",
    }


# ============ 修复 1：admin.patch_user 角色权限 ============

def test_hrbp_cannot_change_others_role(client: TestClient) -> None:
    uids = _user_ids(client)
    hr_token = _login(client, "mock-hr")
    resp = client.patch(
        f"/api/v1/admin/users/{uids['mock-alice']}",
        headers=_headers(hr_token),
        json={"role": "dept_leader"},
    )
    assert resp.status_code == 403, resp.text


def test_hrbp_cannot_promote_to_super_admin(client: TestClient) -> None:
    uids = _user_ids(client)
    hr_token = _login(client, "mock-hr")
    resp = client.patch(
        f"/api/v1/admin/users/{uids['mock-alice']}",
        headers=_headers(hr_token),
        json={"role": "super_admin"},
    )
    assert resp.status_code == 403, resp.text


def test_hrbp_can_still_patch_non_role_fields(client: TestClient) -> None:
    uids = _user_ids(client)
    hr_token = _login(client, "mock-hr")
    resp = client.patch(
        f"/api/v1/admin/users/{uids['mock-alice']}",
        headers=_headers(hr_token),
        json={"leader_userid": "mock-prod-leader"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["leader_userid"] == "mock-prod-leader"


def test_super_admin_can_change_others_role(client: TestClient) -> None:
    uids = _user_ids(client)
    ceo_token = _login(client, "mock-ceo")
    resp = client.patch(
        f"/api/v1/admin/users/{uids['mock-alice']}",
        headers=_headers(ceo_token),
        json={"role": "direct_leader"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "direct_leader"


def test_no_one_can_change_own_role(client: TestClient) -> None:
    uids = _user_ids(client)
    ceo_token = _login(client, "mock-ceo")
    resp = client.patch(
        f"/api/v1/admin/users/{uids['mock-ceo']}",
        headers=_headers(ceo_token),
        json={"role": "hrbp"},
    )
    assert resp.status_code == 403, resp.text


# ============ 修复 2：calibrate scope 校验 ============

def test_dept_leader_cannot_calibrate_out_of_scope(client: TestClient) -> None:
    # mock-carol 属于产品部，不在技术部 Leader 的 scope 内
    cycle_id, _, uids = _setup_calibration_cycle(client, ["mock-alice", "mock-carol"])
    leader_token = _login(client, "mock-tech-leader")
    resp = client.post(
        f"/api/v1/calibration/cycles/{cycle_id}/calibrate",
        headers=_headers(leader_token),
        json={"items": [_calibrate_item(uids["mock-carol"])]},
    )
    assert resp.status_code == 403, resp.text
    assert str(uids["mock-carol"]) in resp.json()["detail"]


def test_dept_leader_can_calibrate_in_scope(client: TestClient) -> None:
    cycle_id, _, uids = _setup_calibration_cycle(client, ["mock-alice"])
    leader_token = _login(client, "mock-tech-leader")
    resp = client.post(
        f"/api/v1/calibration/cycles/{cycle_id}/calibrate",
        headers=_headers(leader_token),
        json={"items": [_calibrate_item(uids["mock-alice"])]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["modified"] == 1


def test_calibrate_invalid_score_returns_400(client: TestClient) -> None:
    # 3.3 不是 0.25 的倍数：validate_perf_score 抛 ValueError，应转为 400 而非 500
    cycle_id, _, uids = _setup_calibration_cycle(client, ["mock-alice"])
    leader_token = _login(client, "mock-tech-leader")
    resp = client.post(
        f"/api/v1/calibration/cycles/{cycle_id}/calibrate",
        headers=_headers(leader_token),
        json={"items": [_calibrate_item(uids["mock-alice"], perf_score=3.3)]},
    )
    assert resp.status_code == 400, resp.text


# ============ 修复 3：approved 后不可重复提交 ============

def test_submit_calibration_after_approved_returns_400(client: TestClient) -> None:
    cycle_id, objective_cycle_id, uids = _setup_calibration_cycle(client, ["mock-alice"])

    # 先写目标，再自评 + 上级评估，让 final_perf_score 有值
    alice_token = _login(client, "mock-alice")
    resp = client.put(
        f"/api/v1/objective-cycles/{objective_cycle_id}/objectives",
        headers=_headers(alice_token),
        json={
            "items": [
                {"title": "核心项目交付", "description": "按期交付", "measure_criteria": "里程碑达成", "weight": 60},
                {"title": "协作与沟通", "description": "跨团队协作", "measure_criteria": "无投诉", "weight": 40},
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/self-evaluation",
        headers=_headers(alice_token),
        json=SELF_EVAL_PAYLOAD,
    )
    assert resp.status_code == 200, resp.text
    leader_token = _login(client, "mock-tech-leader")
    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/users/{uids['mock-alice']}/superior-evaluation",
        headers=_headers(leader_token),
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

    # 提交校准 → HR 批 → CEO 批 → approved
    resp = client.post(
        f"/api/v1/calibration/cycles/{cycle_id}/submit-calibration",
        headers=_headers(leader_token),
    )
    assert resp.status_code == 200, resp.text
    hr_token = _login(client, "mock-hr")
    resp = client.post(
        f"/api/v1/calibration/cycles/{cycle_id}/approval",
        headers=_headers(hr_token),
        json={"action": "approve"},
    )
    assert resp.status_code == 200, resp.text
    ceo_token = _login(client, "mock-ceo")
    resp = client.post(
        f"/api/v1/calibration/cycles/{cycle_id}/approval",
        headers=_headers(ceo_token),
        json={"action": "approve"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "approved"

    # 再次提交应被拒绝
    resp = client.post(
        f"/api/v1/calibration/cycles/{cycle_id}/submit-calibration",
        headers=_headers(leader_token),
    )
    assert resp.status_code == 400, resp.text
    assert "已通过" in resp.json()["detail"]
