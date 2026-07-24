from __future__ import annotations

"""权限口径一致性回归测试（2026-07-24）。

覆盖两处修复：
1. can_act_as_superior 与 require_role 对齐：HR 部门的 dept_leader 视同 hrbp 直通。
2. GET /import/historical-performance：所有登录用户可调，hrbp/super_admin 按
   visible_user_ids 过滤，其余角色强制只看自己。
"""

import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlmodel import Session, select, text

from pms.database.models.cycle import PerformanceCycle
from pms.database.models.user import Department, User
from pms.database.session import engine
from pms.main import app
from pms.services.scope import invalidate_scope_cache
from pms.services.seed import seed


@pytest.fixture(autouse=True)
def setup_database():
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        result = conn.execute(text("SHOW TABLES"))
        tables = [row[0] for row in result]
        for table in tables:
            if table != "alembic_version":
                conn.execute(text(f"TRUNCATE TABLE {table}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    seed()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def _login(client: TestClient, wecom_userid: str) -> str:
    resp = client.post("/api/v1/auth/mock-login", json={"wecom_userid": wecom_userid})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _user_id(wecom_userid: str) -> int:
    with Session(engine) as session:
        user = session.exec(select(User).where(User.wecom_userid == wecom_userid)).first()
        assert user and user.id
        return user.id


def _seed_cycle_id() -> int:
    with Session(engine) as session:
        cycle = session.exec(select(PerformanceCycle)).first()
        assert cycle and cycle.id
        return cycle.id


def _make_excel(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "历史绩效导入"
    ws.append([
        "员工ID（wecom_userid）",
        "姓名（校对用）",
        "周期名称",
        "业绩分（1-5，0.25分段）",
        "业绩等级",
        "价值观-信念",
        "价值观-团队",
        "价值观-成长",
        "上级评语",
    ])
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


def _create_hr_dept_leader() -> None:
    """在 HR 部门（含 hrbp 成员的部门）中新增一名 dept_leader。"""
    with Session(engine) as session:
        hr = session.exec(select(User).where(User.wecom_userid == "mock-hr")).first()
        assert hr and hr.department_id
        session.add(User(
            wecom_userid="mock-hr-leader",
            name="钱 HR Leader",
            role="dept_leader",
            leader_userid="mock-ceo",
            position="HR 负责人",
            department_id=hr.department_id,
        ))
        session.commit()


FEEDBACK_PAYLOAD = {
    "strengths": "技术扎实，执行力强",
    "improvements": "需要加强跨部门沟通",
    "next_goals": "下季度主导一个完整模块",
}


def test_hr_dept_leader_can_write_feedback_for_any_employee(client: TestClient) -> None:
    """HR 部门的 dept_leader 可对任意员工写反馈（与 hrbp 同待遇）。"""
    _create_hr_dept_leader()
    token = _login(client, "mock-hr-leader")
    cycle_id = _seed_cycle_id()
    alice_id = _user_id("mock-alice")  # 技术部员工，直属上级是 mock-tech-leader

    resp = client.post(
        f"/api/v1/feedback/cycles/{cycle_id}/users/{alice_id}",
        headers=_headers(token),
        json=FEEDBACK_PAYLOAD,
    )
    assert resp.status_code == 200, resp.text


def test_regular_dept_leader_still_limited_to_direct_reports(client: TestClient) -> None:
    """普通部门 Leader 对非直属下属仍 403（兜底不能放大权限）。"""
    token = _login(client, "mock-tech-leader")
    cycle_id = _seed_cycle_id()
    carol_id = _user_id("mock-carol")  # 产品部员工，非 tech-leader 下属

    resp = client.post(
        f"/api/v1/feedback/cycles/{cycle_id}/users/{carol_id}",
        headers=_headers(token),
        json=FEEDBACK_PAYLOAD,
    )
    assert resp.status_code == 403


def _import_records(client: TestClient) -> None:
    hr_token = _login(client, "mock-hr")
    excel = _make_excel([
        ["mock-alice", "张 Alice", "2024H1", "3.75", "meet", "yi", "jia", "yi", "表现稳定"],
        ["mock-carol", "孙 Carol", "2024H1", "4.25", "excellent", "jia", "jia", "yi", "超出预期"],
    ])
    resp = client.post(
        "/api/v1/import/historical-performance",
        headers=_headers(hr_token),
        files={"file": ("test.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] == 2


def test_employee_only_sees_own_historical_records(client: TestClient) -> None:
    """员工可调用列表接口，但只能拿到自己的记录；显式传他人 user_id 也为空。"""
    _import_records(client)
    alice_token = _login(client, "mock-alice")
    alice_id = _user_id("mock-alice")
    carol_id = _user_id("mock-carol")

    resp = client.get("/api/v1/import/historical-performance", headers=_headers(alice_token))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) == 1
    assert data[0]["user_id"] == alice_id

    resp = client.get(
        f"/api/v1/import/historical-performance?user_id={carol_id}",
        headers=_headers(alice_token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == []


def test_hrbp_sees_historical_within_scope(client: TestClient) -> None:
    """全局 hrbp 看到全部；受限 hrbp 只看到 scope 内部门员工的记录。"""
    _import_records(client)
    hr_token = _login(client, "mock-hr")
    alice_id = _user_id("mock-alice")
    carol_id = _user_id("mock-carol")

    # 全局限 hrbp：两条都可见
    resp = client.get("/api/v1/import/historical-performance", headers=_headers(hr_token))
    assert resp.status_code == 200, resp.text
    assert {r["user_id"] for r in resp.json()} == {alice_id, carol_id}

    # 受限 hrbp：scope 限定为技术部 → 只能看到 alice，看不到产品部的 carol
    with Session(engine) as session:
        hr = session.exec(select(User).where(User.wecom_userid == "mock-hr")).first()
        tech_dept = session.exec(select(Department).where(Department.name.like("%技术%"))).first()
        assert hr and tech_dept and tech_dept.id and hr.id
        hr.hrbp_scope_dept_ids = [tech_dept.id]
        session.add(hr)
        session.commit()
        # 模拟管理端修改管辖范围后的缓存失效
        invalidate_scope_cache(hr.id)

    resp = client.get("/api/v1/import/historical-performance", headers=_headers(hr_token))
    assert resp.status_code == 200, resp.text
    assert {r["user_id"] for r in resp.json()} == {alice_id}
