from __future__ import annotations

"""历史绩效结果导入测试。"""

import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlmodel import Session, select, text

from pms.database.models.historical_performance import HistoricalPerformanceResult
from pms.database.models.user import User
from pms.database.session import engine
from pms.main import app
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


def test_import_historical_performance_success(client: TestClient) -> None:
    hr_token = _login(client, "mock-hr")
    excel = _make_excel([
        ["mock-alice", "张 Alice", "2024H1", "3.75", "meet", "yi", "jia", "yi", "表现稳定"],
        ["mock-bob", "张 Bob", "2024H1", "4.25", "excellent", "jia", "jia", "yi", "超出预期"],
    ])

    resp = client.post(
        "/api/v1/import/historical-performance",
        headers=_headers(hr_token),
        files={"file": ("test.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] == 2
    assert data["failed"] == 0

    with Session(engine) as session:
        alice = session.exec(select(User).where(User.wecom_userid == "mock-alice")).first()
        assert alice
        records = session.exec(
            select(HistoricalPerformanceResult).where(
                HistoricalPerformanceResult.user_id == alice.id,
                HistoricalPerformanceResult.cycle_name == "2024H1",
            )
        ).all()
        assert len(records) == 1
        assert records[0].perf_score == 3.75
        assert records[0].perf_level == "meet"


def test_import_historical_performance_invalid_score(client: TestClient) -> None:
    hr_token = _login(client, "mock-hr")
    excel = _make_excel([
        ["mock-alice", "张 Alice", "2024H1", "3.33", "meet", "yi", "jia", "yi", "表现稳定"],
    ])

    resp = client.post(
        "/api/v1/import/historical-performance",
        headers=_headers(hr_token),
        files={"file": ("test.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] == 0
    assert data["failed"] == 1
    assert "0.25 分段" in data["errors"][0]


def test_import_historical_performance_duplicate(client: TestClient) -> None:
    hr_token = _login(client, "mock-hr")
    excel = _make_excel([
        ["mock-alice", "张 Alice", "2024H1", "3.75", "meet", "yi", "jia", "yi", "表现稳定"],
    ])

    resp = client.post(
        "/api/v1/import/historical-performance",
        headers=_headers(hr_token),
        files={"file": ("test.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] == 1

    # 重复导入
    resp = client.post(
        "/api/v1/import/historical-performance",
        headers=_headers(hr_token),
        files={"file": ("test.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] == 0
    assert data["failed"] == 1
    assert "已存在" in data["errors"][0]
