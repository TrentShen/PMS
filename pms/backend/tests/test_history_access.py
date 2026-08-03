from __future__ import annotations

"""历史绩效开放范围收口测试。

口径：普通员工不可见（含自己的）历史绩效/趋势/历史目标；
Leader/HR（SUPERIOR_ROLES）可看，且受数据可见范围（scope）约束。
"""

from fastapi.testclient import TestClient


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _switch_role(client: TestClient, token: str, role: str) -> str:
    resp = client.post(
        "/api/v1/auth/switch-role",
        headers=_headers(token),
        json={"role": role},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


class TestEmployeeForbidden:
    """普通员工调 3 个历史绩效接口（含查自己）一律 403。"""

    def test_history_user_self_forbidden(
        self, client: TestClient, alice_token: str, user_ids: dict
    ) -> None:
        alice_id = user_ids["mock-alice"]
        resp = client.get(f"/api/v1/history/user/{alice_id}", headers=_headers(alice_token))
        assert resp.status_code == 403, resp.text

    def test_trend_user_self_forbidden(
        self, client: TestClient, alice_token: str, user_ids: dict
    ) -> None:
        alice_id = user_ids["mock-alice"]
        resp = client.get(f"/api/v1/trend/users/{alice_id}", headers=_headers(alice_token))
        assert resp.status_code == 403, resp.text

    def test_historical_objectives_self_forbidden(
        self, client: TestClient, alice_token: str, user_ids: dict
    ) -> None:
        alice_id = user_ids["mock-alice"]
        resp = client.get(
            f"/api/v1/import/historical-objectives?user_id={alice_id}",
            headers=_headers(alice_token),
        )
        assert resp.status_code == 403, resp.text

    def test_historical_objectives_no_param_forbidden(
        self, client: TestClient, alice_token: str
    ) -> None:
        resp = client.get("/api/v1/import/historical-objectives", headers=_headers(alice_token))
        assert resp.status_code == 403, resp.text


class TestDeptLeaderScope:
    """dept_leader（技术部王 Leader）：可查本部门下属，查其他部门员工 403。"""

    def test_history_user_subordinate_ok(
        self, client: TestClient, tech_leader_token: str, user_ids: dict
    ) -> None:
        alice_id = user_ids["mock-alice"]
        resp = client.get(f"/api/v1/history/user/{alice_id}", headers=_headers(tech_leader_token))
        assert resp.status_code == 200, resp.text

    def test_trend_user_subordinate_ok(
        self, client: TestClient, tech_leader_token: str, user_ids: dict
    ) -> None:
        alice_id = user_ids["mock-alice"]
        resp = client.get(f"/api/v1/trend/users/{alice_id}", headers=_headers(tech_leader_token))
        assert resp.status_code == 200, resp.text

    def test_historical_objectives_subordinate_ok(
        self, client: TestClient, tech_leader_token: str, user_ids: dict
    ) -> None:
        alice_id = user_ids["mock-alice"]
        resp = client.get(
            f"/api/v1/import/historical-objectives?user_id={alice_id}",
            headers=_headers(tech_leader_token),
        )
        assert resp.status_code == 200, resp.text

    def test_history_user_out_of_scope_forbidden(
        self, client: TestClient, tech_leader_token: str, user_ids: dict
    ) -> None:
        # carol 在产品部，不属于技术部 Leader 的可见范围
        carol_id = user_ids["mock-carol"]
        resp = client.get(f"/api/v1/history/user/{carol_id}", headers=_headers(tech_leader_token))
        assert resp.status_code == 403, resp.text

    def test_trend_user_out_of_scope_forbidden(
        self, client: TestClient, tech_leader_token: str, user_ids: dict
    ) -> None:
        carol_id = user_ids["mock-carol"]
        resp = client.get(f"/api/v1/trend/users/{carol_id}", headers=_headers(tech_leader_token))
        assert resp.status_code == 403, resp.text

    def test_historical_objectives_out_of_scope_forbidden(
        self, client: TestClient, tech_leader_token: str, user_ids: dict
    ) -> None:
        carol_id = user_ids["mock-carol"]
        resp = client.get(
            f"/api/v1/import/historical-objectives?user_id={carol_id}",
            headers=_headers(tech_leader_token),
        )
        assert resp.status_code == 403, resp.text


class TestDirectLeaderScope:
    """direct_leader（超管切换角色模拟）：查直属下属 200，查非下属 403。

    seed 汇报关系：mock-ceo 的直属下属是 mock-tech-leader / mock-prod-leader
    （mock-hr 按 HR 部门成员规则被剔除出可见范围）。
    """

    def test_direct_leader_subordinate_ok(
        self, client: TestClient, ceo_token: str, user_ids: dict
    ) -> None:
        token = _switch_role(client, ceo_token, "direct_leader")
        tech_leader_id = user_ids["mock-tech-leader"]
        resp = client.get(f"/api/v1/history/user/{tech_leader_id}", headers=_headers(token))
        assert resp.status_code == 200, resp.text
        resp = client.get(f"/api/v1/trend/users/{tech_leader_id}", headers=_headers(token))
        assert resp.status_code == 200, resp.text

    def test_direct_leader_non_subordinate_forbidden(
        self, client: TestClient, ceo_token: str, user_ids: dict
    ) -> None:
        token = _switch_role(client, ceo_token, "direct_leader")
        # alice 的直属上级是 mock-tech-leader，不是 mock-ceo
        alice_id = user_ids["mock-alice"]
        resp = client.get(f"/api/v1/history/user/{alice_id}", headers=_headers(token))
        assert resp.status_code == 403, resp.text
        resp = client.get(f"/api/v1/trend/users/{alice_id}", headers=_headers(token))
        assert resp.status_code == 403, resp.text
        resp = client.get(
            f"/api/v1/import/historical-objectives?user_id={alice_id}",
            headers=_headers(token),
        )
        assert resp.status_code == 403, resp.text


class TestHrbpScope:
    """hrbp 按数据可见范围可查范围内员工。"""

    def test_hrbp_can_view_in_scope(
        self, client: TestClient, hr_token: str, user_ids: dict
    ) -> None:
        alice_id = user_ids["mock-alice"]
        resp = client.get(f"/api/v1/history/user/{alice_id}", headers=_headers(hr_token))
        assert resp.status_code == 200, resp.text
        resp = client.get(f"/api/v1/trend/users/{alice_id}", headers=_headers(hr_token))
        assert resp.status_code == 200, resp.text
        resp = client.get(
            f"/api/v1/import/historical-objectives?user_id={alice_id}",
            headers=_headers(hr_token),
        )
        assert resp.status_code == 200, resp.text
