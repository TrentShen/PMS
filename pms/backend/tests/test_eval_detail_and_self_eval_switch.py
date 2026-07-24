from __future__ import annotations

"""回归测试：detail 接口目标字段补全 + enable_self_eval=False 流程不卡死。

覆盖：
- GET /v1/cycles/{cid}/users/{uid}/detail 返回的目标包含 status/reviewed_by/
  reviewed_at/reject_reason/order_num 字段（修复前内嵌 ObjectiveView 缺这些字段）
- 周期 enable_self_eval=False 时，上级可直接提交上级评估（不再被
  "员工尚未完成自评" 400 卡死）
- 周期 enable_self_eval=True 时，未完成自评仍返回 400（原有前置保留）
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


SUPERIOR_EVAL_PAYLOAD = {
    "perf_score": 3.5,
    "value_belief_grade": "yi",
    "value_belief_example": None,
    "value_team_grade": "yi",
    "value_team_example": None,
    "value_growth_grade": "yi",
    "value_growth_example": None,
    "key_results": "达预期",
    "comment": None,
}

OBJECTIVES_PAYLOAD = {
    "items": [
        {
            "title": "核心项目交付",
            "description": "按期交付",
            "measure_criteria": "里程碑达成",
            "weight": 60,
        },
        {
            "title": "协作与沟通",
            "description": "跨团队协作",
            "measure_criteria": "无投诉",
            "weight": 40,
        },
    ]
}


def _create_objective_cycle(client: TestClient, hr_token: str) -> int:
    resp = client.post(
        "/api/v1/objective-cycles",
        headers=_headers(hr_token),
        json={"name": "回归测试目标周期", "start_date": "2025-07-01", "end_date": "2025-12-31"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _create_cycle(client: TestClient, hr_token: str, objective_cycle_id: int, **overrides) -> int:
    payload = {
        "name": "回归测试绩效周期",
        "start_date": "2025-07-01",
        "end_date": "2025-12-31",
        "objective_cycle_id": objective_cycle_id,
        "enable_self_eval": True,
        "enable_peer_eval": True,
        "enable_calibration": True,
        "enable_feedback": True,
    }
    payload.update(overrides)
    resp = client.post("/api/v1/cycles", headers=_headers(hr_token), json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _prepare_cycle(client: TestClient, **overrides) -> tuple[dict[str, int], str, int, int]:
    uids = _user_ids(client)
    hr_token = _login(client, "mock-hr")
    objective_cycle_id = _create_objective_cycle(client, hr_token)
    cycle_id = _create_cycle(client, hr_token, objective_cycle_id, **overrides)
    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/participants",
        headers=_headers(hr_token),
        json={"user_ids": [uids["mock-alice"]]},
    )
    assert resp.status_code == 200, resp.text
    resp = client.post(f"/api/v1/cycles/{cycle_id}/start", headers=_headers(hr_token))
    assert resp.status_code == 200, resp.text
    return uids, hr_token, cycle_id, objective_cycle_id


def test_detail_objectives_include_review_fields(client: TestClient) -> None:
    """detail 接口返回的目标必须带 status/reviewed_by/reviewed_at/reject_reason/order_num。"""
    uids, _hr_token, cycle_id, objective_cycle_id = _prepare_cycle(client)
    alice_id = uids["mock-alice"]

    # alice 写目标并提交审批
    alice_token = _login(client, "mock-alice")
    resp = client.put(
        f"/api/v1/objective-cycles/{objective_cycle_id}/objectives",
        headers=_headers(alice_token),
        json=OBJECTIVES_PAYLOAD,
    )
    assert resp.status_code == 200, resp.text
    resp = client.post(
        f"/api/v1/objective-cycles/{objective_cycle_id}/objectives/submit",
        headers=_headers(alice_token),
    )
    assert resp.status_code == 200, resp.text

    # 上级驳回，写入 reviewed_by/reviewed_at/reject_reason
    leader_token = _login(client, "mock-tech-leader")
    resp = client.post(
        f"/api/v1/objective-cycles/{objective_cycle_id}/objectives/users/{alice_id}/reject",
        headers=_headers(leader_token),
        json={"reason": "目标不够量化"},
    )
    assert resp.status_code == 200, resp.text

    # 上级查看 detail，目标应带完整审批字段
    resp = client.get(
        f"/api/v1/cycles/{cycle_id}/users/{alice_id}/detail",
        headers=_headers(leader_token),
    )
    assert resp.status_code == 200, resp.text
    objectives = resp.json()["objectives"]
    assert len(objectives) == 2
    for obj in objectives:
        assert obj["status"] == "draft"  # 驳回后打回草稿
        assert obj["reviewed_by"] == "mock-tech-leader"
        assert obj["reviewed_at"] is not None
        assert obj["reject_reason"] == "目标不够量化"
        assert isinstance(obj["order_num"], int)


def test_superior_eval_allowed_when_self_eval_disabled(client: TestClient) -> None:
    """enable_self_eval=False 时上级可直接提交上级评估，不再 400。"""
    uids, _hr_token, cycle_id, _ocid = _prepare_cycle(client, enable_self_eval=False)

    leader_token = _login(client, "mock-tech-leader")
    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/users/{uids['mock-alice']}/superior-evaluation",
        headers=_headers(leader_token),
        json=SUPERIOR_EVAL_PAYLOAD,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["eval_type"] == "superior"


def test_superior_eval_blocked_until_self_done_when_enabled(client: TestClient) -> None:
    """enable_self_eval=True 时，员工未完成自评，上级评估仍返回 400。"""
    uids, _hr_token, cycle_id, _ocid = _prepare_cycle(client)

    leader_token = _login(client, "mock-tech-leader")
    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/users/{uids['mock-alice']}/superior-evaluation",
        headers=_headers(leader_token),
        json=SUPERIOR_EVAL_PAYLOAD,
    )
    assert resp.status_code == 400
    assert "尚未完成自评" in resp.json()["detail"]
