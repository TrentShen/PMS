from __future__ import annotations

"""互评人拒绝评估任务（decline）接口测试。

覆盖：
- 拒绝自己的 pending 任务 → 200，my-tasks 可见 declined + reason
- 拒绝别人的任务 → 403
- 重复拒绝 → 400；拒绝已 submitted 任务 → 400
- 回归：declined 不再计入 evaluations.py 的 pending 前置阻塞
"""

import pytest
from fastapi.testclient import TestClient


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


PEER_SUBMIT_PAYLOAD = {
    "perf_score": 3.5,
    "value_belief_grade": "yi",
    "value_belief_example": None,
    "value_team_grade": "yi",
    "value_team_example": None,
    "value_growth_grade": "yi",
    "value_growth_example": None,
    "comment": None,
}

SUPERIOR_EVAL_PAYLOAD = {
    "perf_score": 3.5,
    "value_belief_grade": "yi",
    "value_belief_example": None,
    "value_team_grade": "yi",
    "value_team_example": None,
    "value_growth_grade": "yi",
    "value_growth_example": None,
    "key_results": "整体达预期",
    "comment": None,
}


@pytest.fixture(scope="module")
def scenario(
    client: TestClient,
    user_ids: dict[str, int],
    hr_token: str,
    alice_token: str,
    tech_leader_token: str,
) -> dict:
    """搭建场景：alice 为被评人，bob / carol 为互评人（各 1 条 pending 任务）。"""
    alice_id = user_ids["mock-alice"]
    bob_id = user_ids["mock-bob"]
    carol_id = user_ids["mock-carol"]

    # HR 创建绩效周期（不开自评，跳过"先自评再选互评人"前置）
    resp = client.post(
        "/api/v1/cycles",
        headers=_headers(hr_token),
        json={
            "name": "互评拒绝测试周期",
            "start_date": "2026-07-01",
            "end_date": "2026-12-31",
            "objective_cycle_id": None,
            "enable_self_eval": False,
            "enable_peer_eval": True,
            "enable_calibration": False,
            "enable_feedback": False,
            "exclusion_rules": {
                "exclude_dept_ids": [],
                "exclude_positions": [],
                "exclude_levels": [],
                "exclude_entry_after": None,
                "exclude_status": ["resigned"],
            },
        },
    )
    assert resp.status_code == 200, resp.text
    cycle_id = resp.json()["id"]

    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/participants",
        headers=_headers(hr_token),
        json={"user_ids": [alice_id, bob_id, carol_id]},
    )
    assert resp.status_code == 200, resp.text

    resp = client.post(f"/api/v1/cycles/{cycle_id}/start", headers=_headers(hr_token))
    assert resp.status_code == 200, resp.text

    # alice 邀请 bob 和 carol
    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/peer/invite",
        headers=_headers(alice_token),
        json={"peer_user_ids": [bob_id, carol_id]},
    )
    assert resp.status_code == 200, resp.text

    # tech-leader（alice 直属上级）审核并发起正式互评
    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/users/{alice_id}/peer/approve",
        headers=_headers(tech_leader_token),
        json={"add_user_ids": [], "remove_user_ids": []},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["approved_tasks"] == 2

    return {"cycle_id": cycle_id, "alice_id": alice_id}


def _my_task_id(client: TestClient, token: str, cycle_id: int) -> int:
    resp = client.get("/api/v1/peer/my-tasks", headers=_headers(token))
    assert resp.status_code == 200, resp.text
    tasks = [t for t in resp.json() if t["cycle_id"] == cycle_id]
    assert len(tasks) == 1, f"应只有 1 条任务: {tasks}"
    return tasks[0]["id"]


def test_decline_others_task_forbidden(
    client: TestClient,
    scenario: dict,
    bob_token: str,
    carol_token: str,
) -> None:
    bob_task_id = _my_task_id(client, bob_token, scenario["cycle_id"])
    resp = client.post(
        f"/api/v1/peer/tasks/{bob_task_id}/decline",
        headers=_headers(carol_token),
        json={"reason": None},
    )
    assert resp.status_code == 403, resp.text


def test_decline_pending_ok(
    client: TestClient,
    scenario: dict,
    bob_token: str,
) -> None:
    bob_task_id = _my_task_id(client, bob_token, scenario["cycle_id"])
    resp = client.post(
        f"/api/v1/peer/tasks/{bob_task_id}/decline",
        headers=_headers(bob_token),
        json={"reason": "与该同事合作较少，无法客观评价"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"status": "declined", "task_id": bob_task_id}

    # my-tasks 可见 declined 状态与原因
    resp = client.get("/api/v1/peer/my-tasks", headers=_headers(bob_token))
    assert resp.status_code == 200, resp.text
    task = next(t for t in resp.json() if t["id"] == bob_task_id)
    assert task["status"] == "declined"
    assert task["decline_reason"] == "与该同事合作较少，无法客观评价"


def test_decline_again_400(
    client: TestClient,
    scenario: dict,
    bob_token: str,
) -> None:
    bob_task_id = _my_task_id(client, bob_token, scenario["cycle_id"])
    resp = client.post(
        f"/api/v1/peer/tasks/{bob_task_id}/decline",
        headers=_headers(bob_token),
        json={"reason": None},
    )
    assert resp.status_code == 400, resp.text


def test_superior_eval_still_blocked_by_remaining_pending(
    client: TestClient,
    scenario: dict,
    tech_leader_token: str,
) -> None:
    # bob 已拒绝（不计入），carol 仍 pending → 阻塞，且数量只算 pending 的 1 条
    resp = client.post(
        f"/api/v1/cycles/{scenario['cycle_id']}/users/{scenario['alice_id']}/superior-evaluation",
        headers=_headers(tech_leader_token),
        json=SUPERIOR_EVAL_PAYLOAD,
    )
    assert resp.status_code == 400, resp.text
    assert "还有 1 位互评人未提交" in resp.json()["detail"]


def test_decline_submitted_task_400(
    client: TestClient,
    scenario: dict,
    carol_token: str,
) -> None:
    carol_task_id = _my_task_id(client, carol_token, scenario["cycle_id"])
    resp = client.post(
        f"/api/v1/peer/tasks/{carol_task_id}/submit",
        headers=_headers(carol_token),
        json=PEER_SUBMIT_PAYLOAD,
    )
    assert resp.status_code == 200, resp.text

    resp = client.post(
        f"/api/v1/peer/tasks/{carol_task_id}/decline",
        headers=_headers(carol_token),
        json={"reason": None},
    )
    assert resp.status_code == 400, resp.text


def test_superior_eval_unblocked_after_decline(
    client: TestClient,
    scenario: dict,
    tech_leader_token: str,
) -> None:
    # bob declined + carol submitted → 无 pending，上级评估不再被互评前置阻塞
    resp = client.post(
        f"/api/v1/cycles/{scenario['cycle_id']}/users/{scenario['alice_id']}/superior-evaluation",
        headers=_headers(tech_leader_token),
        json=SUPERIOR_EVAL_PAYLOAD,
    )
    assert resp.status_code == 200, resp.text
