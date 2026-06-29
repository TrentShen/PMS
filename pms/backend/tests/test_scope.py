from __future__ import annotations

"""数据可见范围测试（PRD 2.2 最小可见原则）。"""

import pytest
from fastapi.testclient import TestClient


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestVisibleScope:
    def _participant_userids(self, client: TestClient, token: str) -> set[str]:
        resp = client.get("/api/v1/cycles/1/participants", headers=_headers(token))
        assert resp.status_code == 200, resp.text
        return {item["user_name"] for item in resp.json()["items"]}

    def test_employee_only_sees_self(self, client: TestClient, alice_token: str) -> None:
        names = self._participant_userids(client, alice_token)
        assert names == {"张 Alice"}

    def test_direct_leader_sees_subordinates(self, client: TestClient, tech_leader_token: str) -> None:
        names = self._participant_userids(client, tech_leader_token)
        assert "张 Alice" in names
        assert "李 Bob" in names
        assert "孙 Carol" not in names

    def test_dept_leader_sees_department_members(self, client: TestClient, prod_leader_token: str) -> None:
        names = self._participant_userids(client, prod_leader_token)
        assert "孙 Carol" in names
        assert "周 David" in names
        assert "张 Alice" not in names

    def test_hrbp_sees_all_active(self, client: TestClient, hr_token: str) -> None:
        names = self._participant_userids(client, hr_token)
        assert "张 Alice" in names
        assert "李 Bob" in names
        assert "孙 Carol" in names
        # HR 部门成员按当前规则被排除
        assert "赵 HR" not in names

    def test_super_admin_sees_all(self, client: TestClient, ceo_token: str) -> None:
        names = self._participant_userids(client, ceo_token)
        assert len(names) >= 4

    def test_history_subordinates_scope(self, client: TestClient, tech_leader_token: str) -> None:
        resp = client.get("/api/v1/history/subordinates", headers=_headers(tech_leader_token))
        assert resp.status_code == 200, resp.text

    def test_employee_cannot_access_subordinate_history(self, client: TestClient, alice_token: str) -> None:
        resp = client.get("/api/v1/history/subordinates", headers=_headers(alice_token))
        assert resp.status_code == 403, resp.text
