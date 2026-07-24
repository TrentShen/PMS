from __future__ import annotations

"""GET /users/colleagues：脱敏同事列表，所有登录用户可访问。"""

from fastapi.testclient import TestClient


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_employee_can_access_colleagues(client: TestClient, alice_token: str):
    resp = client.get("/api/v1/users/colleagues", headers=_headers(alice_token))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_colleagues_only_returns_safe_fields(client: TestClient, alice_token: str):
    resp = client.get("/api/v1/users/colleagues", headers=_headers(alice_token))
    assert resp.status_code == 200, resp.text
    for u in resp.json():
        assert set(u.keys()) == {"id", "name", "position"}
        # 不得泄露敏感字段
        assert "role" not in u
        assert "department_id" not in u
        assert "wecom_userid" not in u
        assert "level" not in u
        assert "leader_userid" not in u


def test_colleagues_requires_login(client: TestClient):
    resp = client.get("/api/v1/users/colleagues")
    assert resp.status_code in (401, 403)
