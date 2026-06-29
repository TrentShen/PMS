from __future__ import annotations

"""角色切换与生效角色隔离测试。"""

import pytest
from fastapi.testclient import TestClient


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestRoleSwitch:
    def test_super_admin_can_switch_role(self, client: TestClient, ceo_token: str) -> None:
        resp = client.post(
            "/api/v1/auth/switch-role",
            headers=_headers(ceo_token),
            json={"role": "employee"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["user"]["role"] == "employee"
        assert data["user"]["base_role"] == "super_admin"
        assert "token" in data

    def test_non_admin_cannot_switch_role(self, client: TestClient, alice_token: str) -> None:
        resp = client.post(
            "/api/v1/auth/switch-role",
            headers=_headers(alice_token),
            json={"role": "hrbp"},
        )
        assert resp.status_code == 403, resp.text

    def test_switched_role_rejects_admin_routes(self, client: TestClient, ceo_token: str) -> None:
        resp = client.post(
            "/api/v1/auth/switch-role",
            headers=_headers(ceo_token),
            json={"role": "employee"},
        )
        employee_token = resp.json()["token"]

        resp = client.post(
            "/api/v1/cycles",
            headers=_headers(employee_token),
            json={
                "name": "test",
                "start_date": "2025-07-01",
                "end_date": "2025-12-31",
            },
        )
        assert resp.status_code == 403, resp.text

        resp = client.get("/api/v1/admin/users", headers=_headers(employee_token))
        assert resp.status_code == 403, resp.text

    def test_switched_role_loses_data_scope(self, client: TestClient, ceo_token: str, user_ids: dict) -> None:
        alice_id = user_ids["mock-alice"]

        # 切换前：超管可以查看 alice 的历史绩效（无已发布周期，但权限应通过）
        resp = client.get(f"/api/v1/history/user/{alice_id}", headers=_headers(ceo_token))
        assert resp.status_code == 200, resp.text

        resp = client.post(
            "/api/v1/auth/switch-role",
            headers=_headers(ceo_token),
            json={"role": "employee"},
        )
        employee_token = resp.json()["token"]

        # 切换为 employee 后：CEO 不再是 alice 的数据可见范围，应 403
        resp = client.get(f"/api/v1/history/user/{alice_id}", headers=_headers(employee_token))
        assert resp.status_code == 403, resp.text

    def test_switch_role_response_has_switchable_roles(self, client: TestClient, ceo_token: str) -> None:
        resp = client.get("/api/v1/auth/me", headers=_headers(ceo_token))
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["base_role"] == "super_admin"
        assert set(data["switchable_roles"]) == {
            "super_admin", "hrbp", "dept_leader", "direct_leader", "employee"
        }
