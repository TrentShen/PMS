from __future__ import annotations

"""历史（线下）绩效目标留档测试。

覆盖：导入 + 幂等重复导入不翻倍、员工不可见（403）、HR 按 scope 可见、模板接口 200。
"""

import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlmodel import Session, select

from pms.database.models.historical_objective import HistoricalObjective
from pms.database.models.user import User
from pms.database.session import engine
from pms.main import app

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_historical_objectives():
    with Session(engine) as s:
        for o in s.exec(select(HistoricalObjective)).all():
            s.delete(o)
        s.commit()
    yield
    with Session(engine) as s:
        for o in s.exec(select(HistoricalObjective)).all():
            s.delete(o)
        s.commit()


def _login(client: TestClient, wecom_userid: str) -> str:
    resp = client.post("/api/v1/auth/mock-login", json={"wecom_userid": wecom_userid})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _user_id(wecom_userid: str) -> int:
    with Session(engine) as s:
        user = s.exec(select(User).where(User.wecom_userid == wecom_userid)).first()
        assert user
        return user.id


def _make_excel(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "历史目标导入"
    ws.append([
        "员工ID（wecom_userid）", "姓名（校对用）", "周期名称",
        "目标项", "目标描述", "衡量标准", "权重(%)",
    ])
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


def _upload(client: TestClient, token: str, excel: bytes):
    return client.post(
        "/api/v1/import/historical-objectives",
        headers=_headers(token),
        files={"file": ("test.xlsx", excel, XLSX_MIME)},
    )


def _count(user_id: int, cycle_name: str) -> int:
    with Session(engine) as s:
        return len(s.exec(
            select(HistoricalObjective).where(
                HistoricalObjective.user_id == user_id,
                HistoricalObjective.cycle_name == cycle_name,
            )
        ).all())


def test_import_and_idempotent_reimport(client: TestClient) -> None:
    hr_token = _login(client, "mock-hr")
    alice_id = _user_id("mock-alice")

    excel = _make_excel([
        ["mock-alice", "张 Alice", "2024H1", "目标一", "描述一", "标准一", "60"],
        ["mock-alice", "张 Alice", "2024H1", "目标二", "描述二", "标准二", "40"],
        ["mock-bob", "李 Bob", "2024H1", "Bob 目标", "Bob 描述", "Bob 标准", ""],
    ])
    resp = _upload(client, hr_token, excel)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["imported_users"] == 2
    assert data["imported_objectives"] == 3
    assert data["skipped"] == []
    assert _count(alice_id, "2024H1") == 2

    # 重复导入同一员工 + 周期：先删后插，数量不翻倍
    resp = _upload(client, hr_token, excel)
    assert resp.status_code == 200, resp.text
    assert _count(alice_id, "2024H1") == 2


def test_employee_forbidden(client: TestClient) -> None:
    hr_token = _login(client, "mock-hr")
    excel = _make_excel([
        ["mock-alice", "张 Alice", "2024H1", "目标一", "描述一", "标准一", "100"],
    ])
    resp = _upload(client, hr_token, excel)
    assert resp.status_code == 200, resp.text

    alice_token = _login(client, "mock-alice")
    alice_id = _user_id("mock-alice")

    # 普通员工不可见历史目标（含自己的）
    resp = client.get("/api/v1/import/historical-objectives", headers=_headers(alice_token))
    assert resp.status_code == 403, resp.text

    resp = client.get(
        f"/api/v1/import/historical-objectives?user_id={alice_id}",
        headers=_headers(alice_token),
    )
    assert resp.status_code == 403, resp.text


def test_hr_can_see_by_scope(client: TestClient) -> None:
    hr_token = _login(client, "mock-hr")
    excel = _make_excel([
        ["mock-alice", "张 Alice", "2024H1", "目标一", "描述一", "标准一", "100"],
        ["mock-bob", "李 Bob", "2024H1", "Bob 目标", "Bob 描述", "Bob 标准", "100"],
    ])
    resp = _upload(client, hr_token, excel)
    assert resp.status_code == 200, resp.text

    # HR 全量可见
    resp = client.get("/api/v1/import/historical-objectives", headers=_headers(hr_token))
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert len(items) == 2
    assert {i["user_name"] for i in items} == {"张 Alice", "李 Bob"}

    # HR 按 user_id 过滤
    bob_id = _user_id("mock-bob")
    resp = client.get(
        f"/api/v1/import/historical-objectives?user_id={bob_id}",
        headers=_headers(hr_token),
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert len(items) == 1
    assert items[0]["user_id"] == bob_id
    assert items[0]["cycle_name"] == "2024H1"


def test_templates_ok(client: TestClient) -> None:
    # 模板接口无需鉴权
    resp = client.get("/api/v1/import/historical-objectives/template")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith(XLSX_MIME)

    resp = client.get("/api/v1/probation/import-objectives/template")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith(XLSX_MIME)
