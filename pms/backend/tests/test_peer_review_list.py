from __future__ import annotations

"""互评名单待审汇总接口（GET /cycles/:id/peer/review-list）测试。

覆盖：
- Leader 视角：直属下属的 pending/approved 计数，不含自己
- 普通员工 403
- 审核发起后 pending 转为 approved
- HR 视角：看到全部参与人
"""

import pytest
from fastapi.testclient import TestClient


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def review_cycle(
    client: TestClient,
    user_ids: dict[str, int],
    hr_token: str,
    alice_token: str,
) -> dict:
    """搭建场景：alice（技术部）邀请 bob、carol 为互评人，名单待审。"""
    alice_id = user_ids["mock-alice"]
    bob_id = user_ids["mock-bob"]
    carol_id = user_ids["mock-carol"]

    resp = client.post(
        "/api/v1/cycles",
        headers=_headers(hr_token),
        json={
            "name": "互评名单汇总测试周期",
            "start_date": "2026-07-01",
            "end_date": "2026-12-31",
            "objective_cycle_id": None,
            "enable_self_eval": False,
            "enable_peer_eval": True,
            "enable_calibration": False,
            "enable_feedback": False,
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

    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/peer/invite",
        headers=_headers(alice_token),
        json={"peer_user_ids": [bob_id, carol_id]},
    )
    assert resp.status_code == 200, resp.text

    return {"cycle_id": cycle_id, "alice_id": alice_id}


def test_review_list_leader_view(
    client: TestClient,
    review_cycle: dict,
    tech_leader_token: str,
    user_ids: dict[str, int],
) -> None:
    resp = client.get(
        f"/api/v1/cycles/{review_cycle['cycle_id']}/peer/review-list",
        headers=_headers(tech_leader_token),
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()
    # 不含 Leader 自己
    assert all(i["user_id"] != user_ids["mock-tech-leader"] for i in items)
    alice_item = next(i for i in items if i["user_id"] == review_cycle["alice_id"])
    assert alice_item["pending_count"] == 2
    assert alice_item["approved_count"] == 0
    # 有待审的排最前
    assert items[0]["user_id"] == review_cycle["alice_id"]


def test_review_list_employee_forbidden(client: TestClient, review_cycle: dict, bob_token: str) -> None:
    resp = client.get(
        f"/api/v1/cycles/{review_cycle['cycle_id']}/peer/review-list",
        headers=_headers(bob_token),
    )
    assert resp.status_code == 403, resp.text


def test_review_list_hr_sees_all(
    client: TestClient,
    review_cycle: dict,
    hr_token: str,
) -> None:
    resp = client.get(
        f"/api/v1/cycles/{review_cycle['cycle_id']}/peer/review-list",
        headers=_headers(hr_token),
    )
    assert resp.status_code == 200, resp.text
    # HR 看到全部 3 名参与人
    assert len(resp.json()) == 3


def test_review_list_counts_after_approve(
    client: TestClient,
    review_cycle: dict,
    tech_leader_token: str,
) -> None:
    resp = client.post(
        f"/api/v1/cycles/{review_cycle['cycle_id']}/users/{review_cycle['alice_id']}/peer/approve",
        headers=_headers(tech_leader_token),
        json={"add_user_ids": [], "remove_user_ids": []},
    )
    assert resp.status_code == 200, resp.text

    resp = client.get(
        f"/api/v1/cycles/{review_cycle['cycle_id']}/peer/review-list",
        headers=_headers(tech_leader_token),
    )
    assert resp.status_code == 200, resp.text
    alice_item = next(i for i in resp.json() if i["user_id"] == review_cycle["alice_id"])
    assert alice_item["pending_count"] == 0
    assert alice_item["approved_count"] == 2
