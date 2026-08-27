from __future__ import annotations

"""九宫格人才盘点接口（GET /cycles/:id/nine-grid）测试。

覆盖：
- 普通员工 403
- 绩效档 × 潜力正确落格（含 9 格全返回、空格给空列表）
- 潜力未评定的已定级员工进 unrated_potential
- 未定绩效等级不计入格子（unset_count）
"""

import pytest
from fastapi.testclient import TestClient


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


SUPERIOR_EVAL = {
    "perf_score": 4.5,
    "value_belief_grade": "jia",
    "value_belief_example": "主动担当的事例",
    "value_team_grade": "yi",
    "value_team_example": None,
    "value_growth_grade": "yi",
    "value_growth_example": None,
    "key_results": "超预期完成",
    "comment": None,
}


@pytest.fixture(scope="module")
def grid_cycle(
    client: TestClient,
    user_ids: dict[str, int],
    hr_token: str,
    tech_leader_token: str,
) -> dict:
    """周期：alice 被上级评 4.5（exceed_part → A 档），bob 未定级。"""
    alice_id = user_ids["mock-alice"]
    bob_id = user_ids["mock-bob"]
    resp = client.post(
        "/api/v1/cycles",
        headers=_headers(hr_token),
        json={
            "name": "九宫格测试周期",
            "start_date": "2026-07-01",
            "end_date": "2026-12-31",
            "objective_cycle_id": None,
            "enable_self_eval": False,
            "enable_peer_eval": False,
            "enable_calibration": False,
            "enable_feedback": False,
        },
    )
    assert resp.status_code == 200, resp.text
    cycle_id = resp.json()["id"]
    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/participants",
        headers=_headers(hr_token),
        json={"user_ids": [alice_id, bob_id]},
    )
    assert resp.status_code == 200, resp.text
    resp = client.post(f"/api/v1/cycles/{cycle_id}/start", headers=_headers(hr_token))
    assert resp.status_code == 200, resp.text

    # 上级评估 alice（4.5 → exceed_part → A 档）
    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/users/{alice_id}/superior-evaluation",
        headers=_headers(tech_leader_token),
        json=SUPERIOR_EVAL,
    )
    assert resp.status_code == 200, resp.text

    # HR 给 alice 评潜力 high；bob 不评
    resp = client.patch(
        f"/api/v1/admin/users/{alice_id}",
        headers=_headers(hr_token),
        json={"potential_level": "high"},
    )
    assert resp.status_code == 200, resp.text

    return {"cycle_id": cycle_id, "alice_id": alice_id, "bob_id": bob_id}


def test_nine_grid_employee_forbidden(client: TestClient, grid_cycle: dict, carol_token: str) -> None:
    resp = client.get(
        f"/api/v1/cycles/{grid_cycle['cycle_id']}/nine-grid",
        headers=_headers(carol_token),
    )
    assert resp.status_code == 403, resp.text


def test_nine_grid_placement(client: TestClient, grid_cycle: dict, tech_leader_token: str) -> None:
    resp = client.get(
        f"/api/v1/cycles/{grid_cycle['cycle_id']}/nine-grid",
        headers=_headers(tech_leader_token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # 9 格全部返回
    assert len(data["cells"]) == 9
    # alice：A 档 × 高潜力
    cell_a_high = next(
        c for c in data["cells"] if c["perf_band"] == "A" and c["potential"] == "high"
    )
    assert [m["user_id"] for m in cell_a_high["members"]] == [grid_cycle["alice_id"]]
    # bob：未定级 → 不在任何格子，计入 unset_count
    assert data["unset_count"] == 1
    all_member_ids = [m["user_id"] for c in data["cells"] for m in c["members"]]
    assert grid_cycle["bob_id"] not in all_member_ids
    assert data["unrated_potential"] == []


def test_nine_grid_unrated_potential(
    client: TestClient, grid_cycle: dict, tech_leader_token: str, hr_token: str
) -> None:
    """清掉 alice 的潜力后，她应落入 unrated_potential 而非格子。"""
    resp = client.patch(
        f"/api/v1/admin/users/{grid_cycle['alice_id']}",
        headers=_headers(hr_token),
        json={"potential_level": ""},  # 空串清除为未评定
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["potential_level"] is None

    resp = client.get(
        f"/api/v1/cycles/{grid_cycle['cycle_id']}/nine-grid",
        headers=_headers(tech_leader_token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert [m["user_id"] for m in data["unrated_potential"]] == [grid_cycle["alice_id"]]
    all_member_ids = [m["user_id"] for c in data["cells"] for m in c["members"]]
    assert grid_cycle["alice_id"] not in all_member_ids


def test_admin_patch_potential_validation(client: TestClient, hr_token: str, user_ids: dict[str, int]) -> None:
    resp = client.patch(
        f"/api/v1/admin/users/{user_ids['mock-bob']}",
        headers=_headers(hr_token),
        json={"potential_level": "super"},
    )
    assert resp.status_code == 400, resp.text
