from __future__ import annotations

"""FTE 守卫测试：非全职员工被拦截在绩效流程外，试用期管理除外。"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from pms.database.models.user import User
from pms.database.session import engine


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def make_intern():
    """将 mock-alice 临时改为实习身份，测试结束后恢复。"""
    with Session(engine) as s:
        alice = s.exec(select(User).where(User.wecom_userid == "mock-alice")).first()
        original = alice.employee_type
        alice.employee_type = "intern"
        s.add(alice)
        s.commit()
    yield
    with Session(engine) as s:
        alice = s.exec(select(User).where(User.wecom_userid == "mock-alice")).first()
        alice.employee_type = original
        s.add(alice)
        s.commit()


class TestFteGuard:
    def test_intern_blocked_from_self_eval(self, client: TestClient, alice_token: str, make_intern) -> None:
        resp = client.post(
            "/api/v1/cycles/1/self-evaluation",
            headers=_headers(alice_token),
            json={
                "perf_score": 3.75,
                "value_belief_grade": "yi",
                "value_team_grade": "jia",
                "value_growth_grade": "yi",
                "key_results": "test",
            },
        )
        assert resp.status_code == 403, resp.text
        assert "全职" in resp.json()["detail"]

    def test_intern_blocked_from_objectives(self, client: TestClient, alice_token: str, make_intern) -> None:
        resp = client.put(
            "/api/v1/cycles/1/objectives",
            headers=_headers(alice_token),
            json={
                "items": [
                    {"title": "t", "description": "d", "measure_criteria": "m", "weight": 100}
                ]
            },
        )
        assert resp.status_code == 403, resp.text

    def test_intern_blocked_from_probation(self, client: TestClient, alice_token: str, make_intern) -> None:
        resp = client.get("/api/v1/probation/mine", headers=_headers(alice_token))
        assert resp.status_code == 403, resp.text
        assert "全职" in resp.json()["detail"]

    def test_full_time_can_self_eval(self, client: TestClient, alice_token: str) -> None:
        resp = client.post(
            "/api/v1/cycles/1/self-evaluation",
            headers=_headers(alice_token),
            json={
                "perf_score": 3.75,
                "value_belief_grade": "yi",
                "value_team_grade": "jia",
                "value_growth_grade": "yi",
                "key_results": "test",
            },
        )
        # 不应被 FTE 拦截
        assert resp.status_code != 403 or "全职" not in resp.json().get("detail", "")
