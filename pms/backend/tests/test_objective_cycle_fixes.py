"""目标模块逻辑修复回归测试。

覆盖：
- active 状态目标周期中员工可保存/提交目标、上级可批准（此前误判 in_progress 恒 400）
- completed 目标周期 Excel 导入返回 400
- Excel 导入跳过目标已 approved 的员工，不无差别覆盖
- direct_leader 拉取调整申请列表时只能看到自己 scope 内的
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlmodel import Session, select, text

from pms.database.models import User
from pms.database.session import engine
from pms.main import app
from pms.services.seed import seed


@pytest.fixture(autouse=True)
def setup_database():
    """每个测试前清空业务表并重新 seed。"""
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


def _user_ids(client: TestClient) -> dict[str, int]:
    token = _login(client, "mock-hr")
    resp = client.get("/api/v1/auth/mock-users", headers=_headers(token))
    assert resp.status_code == 200, resp.text
    return {u["wecom_userid"]: u["id"] for u in resp.json()}


OBJECTIVES_PAYLOAD = {
    "items": [
        {
            "title": "核心项目交付",
            "description": "按期交付",
            "measure_criteria": "里程碑达成",
            "weight": 60,
        },
        {
            "title": "协作与沟通",
            "description": "跨团队协作",
            "measure_criteria": "无投诉",
            "weight": 40,
        },
    ]
}


def _create_objective_cycle(client: TestClient, hr_token: str) -> int:
    resp = client.post(
        "/api/v1/objective-cycles",
        headers=_headers(hr_token),
        json={"name": "状态机修复测试周期", "start_date": "2025-07-01", "end_date": "2025-12-31"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _start_objective_cycle(client: TestClient, hr_token: str, objective_cycle_id: int) -> None:
    resp = client.post(
        f"/api/v1/objective-cycles/{objective_cycle_id}/start",
        headers=_headers(hr_token),
    )
    assert resp.status_code == 200, resp.text


def _save_and_submit(client: TestClient, objective_cycle_id: int, wecom_userid: str) -> None:
    token = _login(client, wecom_userid)
    resp = client.put(
        f"/api/v1/objective-cycles/{objective_cycle_id}/objectives",
        headers=_headers(token),
        json=OBJECTIVES_PAYLOAD,
    )
    assert resp.status_code == 200, resp.text
    resp = client.post(
        f"/api/v1/objective-cycles/{objective_cycle_id}/objectives/submit",
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.text


def _approve_objectives(
    client: TestClient, objective_cycle_id: int, user_id: int, leader_uid: str
) -> None:
    token = _login(client, leader_uid)
    resp = client.post(
        f"/api/v1/objective-cycles/{objective_cycle_id}/objectives/users/{user_id}/approve",
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.text


def _request_adjustment(client: TestClient, objective_cycle_id: int, wecom_userid: str) -> int:
    token = _login(client, wecom_userid)
    resp = client.post(
        f"/api/v1/objective-cycles/{objective_cycle_id}/objectives/request-adjustment",
        headers=_headers(token),
        json={
            "items": [
                {
                    "title": "调整后的目标",
                    "description": "业务方向变化",
                    "measure_criteria": "新里程碑达成",
                    "weight": 100,
                }
            ],
            "reason": "业务方向调整",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["revision_id"]


def _excel_bytes(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["员工ID（wecom_userid）", "姓名（校对用）", "目标类别", "目标项",
               "目标描述", "衡量标准", "权重(%)", "目标周期"])
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _import_excel(client: TestClient, hr_token: str, objective_cycle_id: int, data: bytes):
    return client.post(
        f"/api/v1/objective-cycles/{objective_cycle_id}/excel/import",
        headers=_headers(hr_token),
        files={
            "file": (
                "import.xlsx",
                data,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )


def _objective_row(uid: str, title: str = "导入目标", weight: int = 100) -> list:
    return [uid, "姓名", "业绩目标", title, "目标描述", "衡量标准", weight, "2025H2"]


def test_active_cycle_save_submit_approve(client: TestClient) -> None:
    """active 状态目标周期：员工可保存并提交目标，上级可批准（此前恒 400）。"""
    uids = _user_ids(client)
    hr_token = _login(client, "mock-hr")
    oc_id = _create_objective_cycle(client, hr_token)
    _start_objective_cycle(client, hr_token, oc_id)

    alice_token = _login(client, "mock-alice")
    resp = client.put(
        f"/api/v1/objective-cycles/{oc_id}/objectives",
        headers=_headers(alice_token),
        json=OBJECTIVES_PAYLOAD,
    )
    assert resp.status_code == 200, resp.text

    resp = client.post(
        f"/api/v1/objective-cycles/{oc_id}/objectives/submit",
        headers=_headers(alice_token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["submitted"] == len(OBJECTIVES_PAYLOAD["items"])

    leader_token = _login(client, "mock-tech-leader")
    resp = client.post(
        f"/api/v1/objective-cycles/{oc_id}/objectives/users/{uids['mock-alice']}/approve",
        headers=_headers(leader_token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["approved"] == len(OBJECTIVES_PAYLOAD["items"])


def test_completed_cycle_excel_import_returns_400(client: TestClient) -> None:
    """completed 状态目标周期不允许 Excel 导入。"""
    hr_token = _login(client, "mock-hr")
    oc_id = _create_objective_cycle(client, hr_token)
    _start_objective_cycle(client, hr_token, oc_id)
    resp = client.post(
        f"/api/v1/objective-cycles/{oc_id}/complete",
        headers=_headers(hr_token),
    )
    assert resp.status_code == 200, resp.text

    data = _excel_bytes([_objective_row("mock-alice")])
    resp = _import_excel(client, hr_token, oc_id, data)
    assert resp.status_code == 400
    assert "不允许导入" in resp.json()["detail"]


def test_excel_import_skips_approved_objectives(client: TestClient) -> None:
    """导入时跳过目标已 approved 的员工，不覆盖其目标。"""
    hr_token = _login(client, "mock-hr")
    oc_id = _create_objective_cycle(client, hr_token)
    _start_objective_cycle(client, hr_token, oc_id)

    # 第一次导入：alice 的目标进入 approved 状态
    data = _excel_bytes([_objective_row("mock-alice", title="alice 原始目标")])
    resp = _import_excel(client, hr_token, oc_id, data)
    assert resp.status_code == 200, resp.text
    assert resp.json()["skipped_users"] == []

    # 第二次导入：alice（已 approved）应被跳过，bob 正常导入
    data = _excel_bytes([
        _objective_row("mock-alice", title="alice 被覆盖目标"),
        _objective_row("mock-bob", title="bob 新目标"),
    ])
    resp = _import_excel(client, hr_token, oc_id, data)
    assert resp.status_code == 200, resp.text
    assert resp.json()["skipped_users"] == ["mock-alice"]
    assert resp.json()["affected_users"] == 1

    # alice 的目标未被覆盖
    alice_token = _login(client, "mock-alice")
    uids = _user_ids(client)
    resp = client.get(
        f"/api/v1/objective-cycles/{oc_id}/objectives",
        headers=_headers(alice_token),
    )
    assert resp.status_code == 200, resp.text
    titles = [o["title"] for o in resp.json()]
    assert titles == ["alice 原始目标"]

    # bob 的目标导入成功
    resp = client.get(
        f"/api/v1/objective-cycles/{oc_id}/objectives?user_id={uids['mock-bob']}",
        headers=_headers(hr_token),
    )
    assert resp.status_code == 200, resp.text
    assert [o["title"] for o in resp.json()] == ["bob 新目标"]


def test_direct_leader_adjustments_scoped(client: TestClient) -> None:
    """direct_leader 不传 user_id 拉调整申请列表时，只能看到 scope 内的申请。"""
    uids = _user_ids(client)
    hr_token = _login(client, "mock-hr")
    oc_id = _create_objective_cycle(client, hr_token)
    _start_objective_cycle(client, hr_token, oc_id)

    # alice（技术部）和 carol（产品部）各自完成目标审批并发起调整申请
    _save_and_submit(client, oc_id, "mock-alice")
    _approve_objectives(client, oc_id, uids["mock-alice"], "mock-tech-leader")
    alice_revision_id = _request_adjustment(client, oc_id, "mock-alice")

    _save_and_submit(client, oc_id, "mock-carol")
    _approve_objectives(client, oc_id, uids["mock-carol"], "mock-prod-leader")
    carol_revision_id = _request_adjustment(client, oc_id, "mock-carol")

    # 将 mock-tech-leader 临时改为 direct_leader（仍是 alice/bob 的直属上级）
    with Session(engine) as session:
        tech_leader = session.exec(
            select(User).where(User.wecom_userid == "mock-tech-leader")
        ).first()
        assert tech_leader is not None
        original_role = tech_leader.role
        tech_leader.role = "direct_leader"
        session.add(tech_leader)
        session.commit()

    try:
        leader_token = _login(client, "mock-tech-leader")
        resp = client.get(
            f"/api/v1/objective-cycles/{oc_id}/objectives/adjustments",
            headers=_headers(leader_token),
        )
        assert resp.status_code == 200, resp.text
        revision_ids = {r["id"] for r in resp.json()}
        assert alice_revision_id in revision_ids
        assert carol_revision_id not in revision_ids

        # HR 仍能看到全部
        resp = client.get(
            f"/api/v1/objective-cycles/{oc_id}/objectives/adjustments",
            headers=_headers(hr_token),
        )
        assert resp.status_code == 200, resp.text
        revision_ids = {r["id"] for r in resp.json()}
        assert {alice_revision_id, carol_revision_id} <= revision_ids
    finally:
        with Session(engine) as session:
            tech_leader = session.exec(
                select(User).where(User.wecom_userid == "mock-tech-leader")
            ).first()
            tech_leader.role = original_role
            session.add(tech_leader)
            session.commit()
