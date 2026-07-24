from __future__ import annotations

"""越权/口径收紧回归测试：

1. 受限 HRBP 目标周期加人 / Excel 导入越权 → 403
2. suggest-participants 不建议 HR 部门成员
3. dashboard 受限 HRBP 数据范围收窄
4. 非 FTE 员工访问 /cycles/mine、/peer/my-tasks 返回空数组而非 403
"""

import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlmodel import Session, select

from pms.database.models import User
from pms.database.session import engine


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _user(wecom_userid: str) -> User:
    with Session(engine) as session:
        user = session.exec(select(User).where(User.wecom_userid == wecom_userid)).first()
        assert user and user.id
        return user


@pytest.fixture
def restricted_hrbp(hr_token: str):
    """将 mock-hr 临时限制为仅管辖技术部，测试结束后恢复。"""
    hr_id = _user("mock-hr").id
    tech_dept_id = _user("mock-alice").department_id
    with Session(engine) as session:
        hr = session.get(User, hr_id)
        assert hr
        original_scope = hr.hrbp_scope_dept_ids
        hr.hrbp_scope_dept_ids = [tech_dept_id]
        session.add(hr)
        session.commit()
    yield hr_token
    with Session(engine) as session:
        hr = session.get(User, hr_id)
        assert hr
        hr.hrbp_scope_dept_ids = original_scope
        session.add(hr)
        session.commit()


@pytest.fixture
def intern_alice():
    """将 mock-alice 临时改为实习身份，测试结束后恢复。"""
    with Session(engine) as session:
        alice = session.exec(select(User).where(User.wecom_userid == "mock-alice")).first()
        assert alice
        original = alice.employee_type
        alice.employee_type = "intern"
        session.add(alice)
        session.commit()
    yield
    with Session(engine) as session:
        alice = session.exec(select(User).where(User.wecom_userid == "mock-alice")).first()
        assert alice
        alice.employee_type = original
        session.add(alice)
        session.commit()


def _create_draft_objective_cycle(client: TestClient, headers: dict, name: str) -> int:
    resp = client.post(
        "/api/v1/objective-cycles",
        headers=headers,
        json={"name": name, "start_date": "2025-07-01", "end_date": "2025-12-31"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _seed_perf_cycle_id(client: TestClient, headers: dict) -> int:
    # 必须按名称锁定 seed 的 UAT 周期：其他测试文件会创建额外的 in_progress 周期，
    # 取“第一个 in_progress”会受执行顺序污染
    resp = client.get("/api/v1/cycles", headers=headers)
    assert resp.status_code == 200, resp.text
    for c in resp.json():
        if c["status"] == "in_progress" and "UAT" in c["name"]:
            return c["id"]
    raise AssertionError("没有 in_progress 的 UAT 绩效周期")


def _build_objective_xlsx(wecom_userid: str, name: str) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append([
        "员工ID（wecom_userid）", "姓名（校对用）", "目标类别", "目标项",
        "目标描述", "衡量标准", "权重(%)", "目标周期",
    ])
    ws.append([wecom_userid, name, "业绩目标", "目标项A", "描述A", "标准A", 100, "2025H2"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestObjectiveCycleParticipantsScope:
    def test_restricted_hrbp_add_out_of_scope_403(
        self, client: TestClient, restricted_hrbp: str
    ) -> None:
        """受限 HRBP 给目标周期加管辖范围外的人 → 403，范围内 → 200。"""
        headers = _headers(restricted_hrbp)
        cycle_id = _create_draft_objective_cycle(client, headers, "scope 校验目标周期")

        carol_id = _user("mock-carol").id   # 产品部，超出技术部范围
        resp = client.post(
            f"/api/v1/objective-cycles/{cycle_id}/participants",
            headers=headers,
            json={"user_ids": [carol_id]},
        )
        assert resp.status_code == 403, resp.text

        alice_id = _user("mock-alice").id   # 技术部，范围内
        resp = client.post(
            f"/api/v1/objective-cycles/{cycle_id}/participants",
            headers=headers,
            json={"user_ids": [alice_id]},
        )
        assert resp.status_code == 200, resp.text
        assert len(resp.json()) == 1

    def test_restricted_hrbp_excel_import_out_of_scope_403(
        self, client: TestClient, restricted_hrbp: str, objective_cycle_id: int
    ) -> None:
        """受限 HRBP Excel 导入范围外员工的目标 → 403。"""
        headers = _headers(restricted_hrbp)
        content = _build_objective_xlsx("mock-carol", "孙 Carol")
        resp = client.post(
            f"/api/v1/objective-cycles/{objective_cycle_id}/excel/import",
            headers=headers,
            files={
                "file": (
                    "objectives.xlsx",
                    content,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert resp.status_code == 403, resp.text


class TestSuggestParticipantsExcludesHr:
    def test_suggest_excludes_hr_dept_members(
        self, client: TestClient, hr_token: str
    ) -> None:
        """suggest-participants 与 add_participants 口径对齐：不建议 HR 部门成员。"""
        headers = _headers(hr_token)
        cycle_id = _seed_perf_cycle_id(client, headers)

        resp = client.post(
            f"/api/v1/cycles/{cycle_id}/suggest-participants",
            headers=headers,
            json={},
        )
        assert resp.status_code == 200, resp.text
        ids = {u["id"] for u in resp.json()}
        hr_id = _user("mock-hr").id
        alice_id = _user("mock-alice").id
        assert hr_id not in ids, "HR 部门成员不应被建议"
        assert alice_id in ids, "普通员工应被建议"


class TestDashboardScope:
    def test_restricted_hrbp_dashboard_narrowed(
        self, client: TestClient, restricted_hrbp: str
    ) -> None:
        """受限 HRBP（仅技术部）看板只统计技术部参与人，返回结构不变。"""
        headers = _headers(restricted_hrbp)
        cycle_id = _seed_perf_cycle_id(client, headers)

        resp = client.get(f"/api/v1/cycles/{cycle_id}/dashboard", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # seed 周期参与人：alice/bob（技术部）+ carol/david（产品部）
        assert body["performance_participant_count"] == 2
        dept_names = {d["department_name"] for d in body["self_eval_progress_by_department"]}
        assert dept_names == {"技术部"}
        # 结构字段保持完整
        for key in (
            "self_eval_done", "self_eval_total", "peer_eval_done",
            "superior_eval_done", "superior_eval_total",
            "peer_eval_progress_by_department",
        ):
            assert key in body

    def test_global_hrbp_dashboard_unrestricted(
        self, client: TestClient, hr_token: str
    ) -> None:
        """全局 HRBP（无 scope 限制）看板不受影响。"""
        headers = _headers(hr_token)
        cycle_id = _seed_perf_cycle_id(client, headers)

        resp = client.get(f"/api/v1/cycles/{cycle_id}/dashboard", headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["performance_participant_count"] == 4


class TestNonFteListEndpoints:
    def test_cycles_mine_returns_empty_for_intern(
        self, client: TestClient, alice_token: str, intern_alice
    ) -> None:
        resp = client.get("/api/v1/cycles/mine", headers=_headers(alice_token))
        assert resp.status_code == 200, resp.text
        assert resp.json() == []

    def test_peer_my_tasks_returns_empty_for_intern(
        self, client: TestClient, alice_token: str, intern_alice
    ) -> None:
        resp = client.get("/api/v1/peer/my-tasks", headers=_headers(alice_token))
        assert resp.status_code == 200, resp.text
        assert resp.json() == []

    def test_peer_write_still_blocked_for_intern(
        self, client: TestClient, alice_token: str, intern_alice
    ) -> None:
        """写接口仍由 require_fte 拦截。"""
        resp = client.post(
            "/api/v1/cycles/1/peer/invite",
            headers=_headers(alice_token),
            json={"peer_user_ids": [1]},
        )
        assert resp.status_code == 403, resp.text
