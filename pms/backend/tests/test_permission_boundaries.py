from __future__ import annotations

"""权限边界测试：非允许角色无法执行直属上级/HR 写操作。"""

import pytest
from fastapi.testclient import TestClient


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestPermissionBoundaries:
    def test_employee_cannot_approve_objectives(self, client: TestClient, carol_token: str, user_ids: dict) -> None:
        alice_id = user_ids["mock-alice"]
        resp = client.post(
            f"/api/v1/cycles/1/objectives/users/{alice_id}/approve",
            headers=_headers(carol_token),
        )
        assert resp.status_code == 403, resp.text

    def test_non_superior_leader_cannot_approve_objectives(self, client: TestClient, tech_leader_token: str, user_ids: dict) -> None:
        carol_id = user_ids["mock-carol"]
        resp = client.post(
            f"/api/v1/cycles/1/objectives/users/{carol_id}/approve",
            headers=_headers(tech_leader_token),
        )
        assert resp.status_code == 403, resp.text

    def test_switched_super_admin_cannot_do_superior_eval(self, client: TestClient, ceo_token: str, user_ids: dict) -> None:
        alice_id = user_ids["mock-alice"]
        resp = client.post(
            "/api/v1/auth/switch-role",
            headers=_headers(ceo_token),
            json={"role": "employee"},
        )
        employee_token = resp.json()["token"]
        resp = client.post(
            f"/api/v1/cycles/1/users/{alice_id}/superior-evaluation",
            headers=_headers(employee_token),
            json={
                "perf_score": 3.75,
                "value_belief_grade": "yi",
                "value_team_grade": "jia",
                "value_growth_grade": "yi",
                "key_results": "test",
            },
        )
        assert resp.status_code == 403, resp.text

    def test_employee_cannot_approve_peer_list(self, client: TestClient, carol_token: str, user_ids: dict) -> None:
        alice_id = user_ids["mock-alice"]
        resp = client.post(
            f"/api/v1/cycles/1/users/{alice_id}/peer/approve",
            headers=_headers(carol_token),
            json={"add_user_ids": [], "remove_user_ids": []},
        )
        assert resp.status_code == 403, resp.text

    def test_employee_cannot_write_feedback_for_others(self, client: TestClient, carol_token: str, user_ids: dict) -> None:
        alice_id = user_ids["mock-alice"]
        resp = client.post(
            f"/api/v1/feedback/cycles/1/users/{alice_id}",
            headers=_headers(carol_token),
            json={
                "strengths": "strengths",
                "improvements": "improvements",
                "next_goals": "next goals",
            },
        )
        assert resp.status_code == 403, resp.text

    def test_hrbp_can_still_write_feedback(self, client: TestClient, hr_token: str, user_ids: dict) -> None:
        alice_id = user_ids["mock-alice"]
        resp = client.post(
            f"/api/v1/feedback/cycles/1/users/{alice_id}",
            headers=_headers(hr_token),
            json={
                "strengths": "strengths",
                "improvements": "improvements",
                "next_goals": "next goals",
            },
        )
        assert resp.status_code in (200, 404), resp.text

    def test_employee_cannot_access_calibration_view(self, client: TestClient, alice_token: str) -> None:
        resp = client.get("/api/v1/calibration/cycles/1/view", headers=_headers(alice_token))
        assert resp.status_code == 403, resp.text
