from __future__ import annotations

"""FTE 守卫测试：非全职员工被拦截在绩效流程外，试用期管理除外。"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from pms.database.models.cycle import PerformanceCycle
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


@pytest.fixture
def make_intern_leader():
    """将 mock-tech-leader 临时改为实习身份（非 FTE 的 Leader 场景），测试结束后恢复。"""
    with Session(engine) as s:
        leader = s.exec(select(User).where(User.wecom_userid == "mock-tech-leader")).first()
        original = leader.employee_type
        leader.employee_type = "intern"
        s.add(leader)
        s.commit()
    yield
    with Session(engine) as s:
        leader = s.exec(select(User).where(User.wecom_userid == "mock-tech-leader")).first()
        leader.employee_type = original
        s.add(leader)
        s.commit()


def _seed_cycle_id() -> int:
    with Session(engine) as s:
        cycle = s.exec(select(PerformanceCycle)).first()
        assert cycle and cycle.id
        return cycle.id


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

    def test_intern_blocked_from_objectives(self, client: TestClient, alice_token: str, make_intern, objective_cycle_id: int) -> None:
        resp = client.put(
            f"/api/v1/objective-cycles/{objective_cycle_id}/objectives",
            headers=_headers(alice_token),
            json={
                "items": [
                    {"title": "t", "description": "d", "measure_criteria": "m", "weight": 100}
                ]
            },
        )
        assert resp.status_code == 403, resp.text

    def test_intern_probation_mine_returns_none(self, client: TestClient, alice_token: str, make_intern) -> None:
        # 非 FTE 访问 /probation/mine 返回 None 而非 403（避免初始化页面报错）
        resp = client.get("/api/v1/probation/mine", headers=_headers(alice_token))
        assert resp.status_code == 200, resp.text
        assert resp.json() is None

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

    def test_intern_leader_probation_list_returns_empty(
        self, client: TestClient, tech_leader_token: str, make_intern_leader
    ) -> None:
        # 非 FTE 的 Leader 访问试用期列表返回 200 空列表而非 403（对齐 cycles 口径）
        resp = client.get("/api/v1/probation", headers=_headers(tech_leader_token))
        assert resp.status_code == 200, resp.text
        assert resp.json() == []

    def test_intern_calibration_view_returns_empty(
        self, client: TestClient, tech_leader_token: str, make_intern_leader
    ) -> None:
        # 非 FTE 访问校准视图返回 200 空数据而非 403，前端显示空态
        cycle_id = _seed_cycle_id()
        resp = client.get(
            f"/api/v1/calibration/cycles/{cycle_id}/view",
            headers=_headers(tech_leader_token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["distribution"] == []

    def test_intern_calibration_history_returns_empty(
        self, client: TestClient, tech_leader_token: str, make_intern_leader
    ) -> None:
        cycle_id = _seed_cycle_id()
        resp = client.get(
            f"/api/v1/calibration/cycles/{cycle_id}/history",
            headers=_headers(tech_leader_token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json() == []

    def test_intern_blocked_from_calibration_write(
        self, client: TestClient, tech_leader_token: str, make_intern_leader
    ) -> None:
        # 校准写接口仍由 require_fte 拦截
        cycle_id = _seed_cycle_id()
        resp = client.post(
            f"/api/v1/calibration/cycles/{cycle_id}/calibrate",
            headers=_headers(tech_leader_token),
            json={"items": [{"user_id": 1, "perf_score": 3.5, "reason": "test"}]},
        )
        assert resp.status_code == 403, resp.text
        assert "全职" in resp.json()["detail"]
