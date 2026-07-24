from __future__ import annotations

"""update_cycle 状态限制 / add_participants HRBP scope / CycleBrief exclusion_rules 测试。"""

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from pms.database.models import User
from pms.database.session import engine


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _login(client: TestClient, wecom_userid: str) -> str:
    resp = client.post("/api/v1/auth/mock-login", json={"wecom_userid": wecom_userid})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _user_id(wecom_userid: str) -> int:
    with Session(engine) as session:
        user = session.exec(select(User).where(User.wecom_userid == wecom_userid)).first()
        assert user and user.id
        return user.id


def _create_draft_cycle(client: TestClient, headers: dict, name: str) -> int:
    resp = client.post(
        "/api/v1/cycles",
        headers=headers,
        json={"name": name, "start_date": "2025-07-01", "end_date": "2025-12-31"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


class TestUpdateCycleStatusGuard:
    def test_draft_cycle_fully_editable(self, client: TestClient, hr_token: str) -> None:
        """draft 状态可改开关和起止日期。"""
        headers = _headers(hr_token)
        cycle_id = _create_draft_cycle(client, headers, "draft 全可改")

        resp = client.put(
            f"/api/v1/cycles/{cycle_id}",
            headers=headers,
            json={
                "enable_calibration": False,
                "enable_peer_eval": False,
                "start_date": "2025-08-01",
                "end_date": "2025-11-30",
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["enable_calibration"] is False
        assert body["enable_peer_eval"] is False
        assert body["start_date"] == "2025-08-01"
        assert body["end_date"] == "2025-11-30"

    def test_draft_cycle_single_date_revalidated(self, client: TestClient, hr_token: str) -> None:
        """只传单日期时，用更新后的生效值校验 start < end。"""
        headers = _headers(hr_token)
        cycle_id = _create_draft_cycle(client, headers, "draft 单日期校验")

        # 新 start 晚于已有 end（2025-12-31）→ 400
        resp = client.put(
            f"/api/v1/cycles/{cycle_id}",
            headers=headers,
            json={"start_date": "2026-01-01"},
        )
        assert resp.status_code == 400, resp.text

        # 合法的单日期更新 → 200
        resp = client.put(
            f"/api/v1/cycles/{cycle_id}",
            headers=headers,
            json={"end_date": "2025-10-31"},
        )
        assert resp.status_code == 200, resp.text

    def test_non_draft_cycle_freezes_switches_and_dates(
        self, client: TestClient, hr_token: str
    ) -> None:
        """in_progress 周期：开关和起止日期冻结（防绕过审批），名称仍可改。"""
        headers = _headers(hr_token)
        cycle_id = _create_draft_cycle(client, headers, "in_progress 冻结")

        # 加人并启动
        alice_id = _user_id("mock-alice")
        resp = client.post(
            f"/api/v1/cycles/{cycle_id}/participants",
            headers=headers,
            json={"user_ids": [alice_id]},
        )
        assert resp.status_code == 200, resp.text
        resp = client.post(f"/api/v1/cycles/{cycle_id}/start", headers=headers)
        assert resp.status_code == 200, resp.text

        # 改开关 → 400（原本可借此绕过校准审批直接发布）
        resp = client.put(
            f"/api/v1/cycles/{cycle_id}",
            headers=headers,
            json={"enable_calibration": False},
        )
        assert resp.status_code == 400, resp.text

        # 改起止日期 → 400
        resp = client.put(
            f"/api/v1/cycles/{cycle_id}",
            headers=headers,
            json={"start_date": "2025-08-01"},
        )
        assert resp.status_code == 400, resp.text

        # 改名称等描述性字段 → 200
        resp = client.put(
            f"/api/v1/cycles/{cycle_id}",
            headers=headers,
            json={"name": "in_progress 冻结（改名）"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["name"] == "in_progress 冻结（改名）"


class TestAddParticipantsHrbpScope:
    def test_restricted_hrbp_cannot_add_out_of_scope(
        self, client: TestClient, hr_token: str
    ) -> None:
        """受限 HRBP（hrbp_scope_dept_ids 非空）越范围加人 → 403，范围内 → 200。"""
        headers = _headers(hr_token)
        cycle_id = _create_draft_cycle(client, headers, "HRBP scope 加人")

        hr_id = _user_id("mock-hr")
        alice_id = _user_id("mock-alice")   # 技术部
        carol_id = _user_id("mock-carol")   # 产品部

        with Session(engine) as session:
            hr = session.get(User, hr_id)
            tech_dept_id = session.get(User, alice_id).department_id
            original_scope = hr.hrbp_scope_dept_ids
            hr.hrbp_scope_dept_ids = [tech_dept_id]
            session.add(hr)
            session.commit()

        try:
            # 产品部 Carol 超出技术部范围 → 403
            resp = client.post(
                f"/api/v1/cycles/{cycle_id}/participants",
                headers=headers,
                json={"user_ids": [carol_id]},
            )
            assert resp.status_code == 403, resp.text

            # 技术部 Alice 在范围内 → 200
            resp = client.post(
                f"/api/v1/cycles/{cycle_id}/participants",
                headers=headers,
                json={"user_ids": [alice_id]},
            )
            assert resp.status_code == 200, resp.text
            assert len(resp.json()) == 1
        finally:
            with Session(engine) as session:
                hr = session.get(User, hr_id)
                hr.hrbp_scope_dept_ids = original_scope
                session.add(hr)
                session.commit()


class TestCycleBriefExclusionRules:
    def test_list_cycles_returns_exclusion_rules(
        self, client: TestClient, hr_token: str
    ) -> None:
        """GET /v1/cycles 响应包含 exclusion_rules（前端筛选弹窗预填依赖）。"""
        resp = client.get("/api/v1/cycles", headers=_headers(hr_token))
        assert resp.status_code == 200, resp.text
        cycles = resp.json()
        assert cycles, "没有周期数据"
        for c in cycles:
            assert "exclusion_rules" in c
        # seed 的 UAT 周期配置了排除规则，应原样返回
        assert any(c["exclusion_rules"] for c in cycles)
