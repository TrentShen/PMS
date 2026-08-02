from __future__ import annotations

"""试用期目标批量导入测试。

覆盖：正常导入覆盖、计划不存在 skip、状态不允许 skip、非 HR 403。
"""

import io
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlmodel import Session, select

from pms.database.models.enums import ProbationPlanStatus
from pms.database.models.probation import ProbationObjective, ProbationPlan
from pms.database.models.user import User
from pms.database.session import engine
from pms.main import app

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture
def client():
    return TestClient(app)


def _login(client: TestClient, wecom_userid: str) -> str:
    resp = client.post("/api/v1/auth/mock-login", json={"wecom_userid": wecom_userid})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_excel(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "试用期目标导入"
    ws.append(["员工ID（wecom_userid）", "姓名（校对用）", "目标项", "目标描述", "衡量标准"])
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


def _upload(client: TestClient, token: str, excel: bytes):
    return client.post(
        "/api/v1/probation/import-objectives",
        headers=_headers(token),
        files={"file": ("test.xlsx", excel, XLSX_MIME)},
    )


def _reset_plan(wecom_userid: str, status: str = ProbationPlanStatus.DRAFT) -> int:
    """清空该用户的试用期计划并重建一个指定状态的计划，返回 plan.id。"""
    with Session(engine) as s:
        user = s.exec(select(User).where(User.wecom_userid == wecom_userid)).first()
        assert user, f"seed 用户 {wecom_userid} 不存在"
        old_plans = s.exec(select(ProbationPlan).where(ProbationPlan.user_id == user.id)).all()
        for p in old_plans:
            for o in s.exec(select(ProbationObjective).where(ProbationObjective.plan_id == p.id)).all():
                s.delete(o)
            s.delete(p)
        plan = ProbationPlan(
            user_id=user.id,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=150),
            probation_months=6,
            status=status,
        )
        s.add(plan)
        s.commit()
        s.refresh(plan)
        return plan.id


def _objective_titles(plan_id: int) -> list[str]:
    with Session(engine) as s:
        objs = s.exec(
            select(ProbationObjective)
            .where(ProbationObjective.plan_id == plan_id)
            .order_by(ProbationObjective.order_num)
        ).all()
        return [o.title for o in objs]


def test_import_success_and_overwrite(client: TestClient) -> None:
    plan_id = _reset_plan("mock-alice")
    hr_token = _login(client, "mock-hr")

    excel = _make_excel([
        ["mock-alice", "张 Alice", "目标一", "描述一", "标准一"],
        ["mock-alice", "张 Alice", "目标二", "描述二", "标准二"],
    ])
    resp = _upload(client, hr_token, excel)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["imported_users"] == 1
    assert data["imported_objectives"] == 2
    assert data["skipped"] == []
    assert _objective_titles(plan_id) == ["目标一", "目标二"]

    # 再次导入应覆盖而不是追加
    excel2 = _make_excel([
        ["mock-alice", "张 Alice", "新目标", "新描述", "新标准"],
    ])
    resp = _upload(client, hr_token, excel2)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["imported_objectives"] == 1
    assert _objective_titles(plan_id) == ["新目标"]


def test_import_skip_when_plan_not_exists(client: TestClient) -> None:
    # mock-bob 没有试用期计划（先清掉可能残留的计划）
    with Session(engine) as s:
        bob = s.exec(select(User).where(User.wecom_userid == "mock-bob")).first()
        assert bob
        for p in s.exec(select(ProbationPlan).where(ProbationPlan.user_id == bob.id)).all():
            s.delete(p)
        s.commit()

    hr_token = _login(client, "mock-hr")
    excel = _make_excel([
        ["mock-bob", "李 Bob", "目标一", "描述一", "标准一"],
    ])
    resp = _upload(client, hr_token, excel)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["imported_users"] == 0
    assert data["imported_objectives"] == 0
    assert len(data["skipped"]) == 1
    assert data["skipped"][0]["wecom_userid"] == "mock-bob"
    assert "不存在" in data["skipped"][0]["reason"]


def test_import_skip_when_status_not_allowed(client: TestClient) -> None:
    # in_progress 状态不允许导入
    _reset_plan("mock-carol", status=ProbationPlanStatus.IN_PROGRESS)
    hr_token = _login(client, "mock-hr")
    excel = _make_excel([
        ["mock-carol", "孙 Carol", "目标一", "描述一", "标准一"],
    ])
    resp = _upload(client, hr_token, excel)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["imported_users"] == 0
    assert len(data["skipped"]) == 1
    assert data["skipped"][0]["wecom_userid"] == "mock-carol"
    assert "不允许" in data["skipped"][0]["reason"]


def test_import_forbidden_for_non_hr(client: TestClient) -> None:
    _reset_plan("mock-alice")
    alice_token = _login(client, "mock-alice")
    excel = _make_excel([
        ["mock-alice", "张 Alice", "目标一", "描述一", "标准一"],
    ])
    resp = _upload(client, alice_token, excel)
    assert resp.status_code == 403, resp.text
