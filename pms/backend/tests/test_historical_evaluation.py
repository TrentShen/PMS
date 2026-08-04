from __future__ import annotations

"""历史绩效敏感数据：导入幂等/skip、严格权限查询、peers_json 解析测试。"""

import io
import json

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlmodel import Session, select, text

from pms.database.models.historical_evaluation import (
    HistoricalEvaluationDetail,
    HistoricalEvaluationSummary,
)
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
    # seed 无 direct_leader 角色用户，补一对直属上下级用于权限矩阵
    with Session(engine) as s:
        tech_dept_id = s.exec(
            select(User.department_id).where(User.wecom_userid == "mock-alice")
        ).first()
        s.add(User(
            wecom_userid="mock-dl", name="王 直属", role="direct_leader",
            leader_userid="mock-tech-leader", department_id=tech_dept_id,
            position="组长", employee_type="full_time", status="active",
        ))
        s.add(User(
            wecom_userid="mock-eve", name="赵 Eve", role="employee",
            leader_userid="mock-dl", department_id=tech_dept_id,
            position="工程师", employee_type="full_time", status="active",
        ))
        s.commit()
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
    with Session(engine) as s:
        user = s.exec(select(User).where(User.wecom_userid == wecom_userid)).first()
        assert user and user.id is not None
        return user.id


def _make_excel(headers: list[str], rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "导入"
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


SUMMARY_HEADERS = [
    "姓名", "工号", "周期名称", "上级绩效得分", "上级绩效等级", "上级价值观等级",
    "互评绩效得分", "互评绩效等级", "互评价值观等级",
    "自评绩效得分", "自评绩效等级", "自评价值观等级",
    "是否校准", "校准建议", "校准后绩效得分", "校准后结果", "备注",
]

DETAIL_HEADERS = [
    "姓名", "工号", "周期名称", "自评绩效得分", "自评价值观得分", "自评产出", "自评整体评价",
    "上级绩效得分", "上级价值观得分", "上级评价（汇总）",
    "互评1得分", "互评1评语", "互评2得分", "互评2评语", "互评3得分", "互评3评语",
    "互评4得分", "互评4评语", "互评5得分", "互评5评语",
]

MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _post_import(client: TestClient, url: str, token: str, excel: bytes):
    return client.post(url, headers=_headers(token), files={"file": ("test.xlsx", excel, MIME)})


def _summary_row(score: float = 3.75, userid: str = "mock-eve", name: str = "赵 Eve") -> list:
    return [name, userid, "2023H1", score, "meet", "yi", 3.5, "meet", "yi",
            3.5, "meet", "yi", "是", "建议上调", 4.0, "excellent", "备注内容"]


def _detail_row(userid: str = "mock-eve") -> list:
    return ["赵 Eve", userid, "2023H1", 3.5, "yi", "完成核心模块", "整体符合预期",
            3.75, "yi", "表现稳定",
            3.5, "协作顺畅", None, None, 4.0, "主动补位", None, None, None, None]


def test_import_summary_idempotent(client: TestClient) -> None:
    hr_token = _login(client, "mock-hr")
    url = "/api/v1/import/historical-evaluations/summary"

    excel = _make_excel(SUMMARY_HEADERS, [_summary_row(score=3.75)])
    resp = _post_import(client, url, hr_token, excel)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"imported": 1, "skipped": []}

    # 重复导入同 user+cycle：先删后插，得分被覆盖而不是报错/重复
    excel2 = _make_excel(SUMMARY_HEADERS, [_summary_row(score=4.25)])
    resp = _post_import(client, url, hr_token, excel2)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"imported": 1, "skipped": []}

    eve_id = _user_id("mock-eve")
    with Session(engine) as s:
        records = s.exec(
            select(HistoricalEvaluationSummary).where(
                HistoricalEvaluationSummary.user_id == eve_id,
                HistoricalEvaluationSummary.cycle_name == "2023H1",
            )
        ).all()
        assert len(records) == 1
        assert records[0].superior_score == 4.25
        assert records[0].is_calibrated is True
        assert records[0].calibrated_result == "excellent"


def test_import_skip_unknown_user(client: TestClient) -> None:
    hr_token = _login(client, "mock-hr")
    excel = _make_excel(SUMMARY_HEADERS, [
        _summary_row(),
        _summary_row(userid="ghost-user", name="不存在的人"),
    ])
    resp = _post_import(client, "/api/v1/import/historical-evaluations/summary", hr_token, excel)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["imported"] == 1
    assert len(data["skipped"]) == 1
    assert data["skipped"][0]["wecom_userid"] == "ghost-user"
    assert data["skipped"][0]["name"] == "不存在的人"
    assert "不存在" in data["skipped"][0]["reason"]


def test_import_detail_peers_only_nonempty(client: TestClient) -> None:
    hr_token = _login(client, "mock-hr")
    excel = _make_excel(DETAIL_HEADERS, [_detail_row()])
    resp = _post_import(client, "/api/v1/import/historical-evaluations/detail", hr_token, excel)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"imported": 1, "skipped": []}

    eve_id = _user_id("mock-eve")
    with Session(engine) as s:
        record = s.exec(
            select(HistoricalEvaluationDetail).where(
                HistoricalEvaluationDetail.user_id == eve_id,
                HistoricalEvaluationDetail.cycle_name == "2023H1",
            )
        ).first()
        assert record and record.peers_json
        peers = json.loads(record.peers_json)
        # 互评 1、3 非空，互评 2/4/5 为空被丢弃
        assert peers == [
            {"index": 1, "score": 3.5, "comment": "协作顺畅"},
            {"index": 3, "score": 4.0, "comment": "主动补位"},
        ]


def _import_both(client: TestClient, hr_token: str) -> None:
    resp = _post_import(
        client, "/api/v1/import/historical-evaluations/summary", hr_token,
        _make_excel(SUMMARY_HEADERS, [_summary_row()]),
    )
    assert resp.status_code == 200, resp.text
    resp = _post_import(
        client, "/api/v1/import/historical-evaluations/detail", hr_token,
        _make_excel(DETAIL_HEADERS, [_detail_row()]),
    )
    assert resp.status_code == 200, resp.text


def test_query_permission_matrix(client: TestClient) -> None:
    hr_token = _login(client, "mock-hr")
    _import_both(client, hr_token)

    eve_id = _user_id("mock-eve")
    alice_id = _user_id("mock-alice")
    url = f"/api/v1/history/users/{eve_id}/evaluations"

    # HR（hrbp / super_admin）→ 200
    assert client.get(url, headers=_headers(hr_token)).status_code == 200
    ceo_token = _login(client, "mock-ceo")
    assert client.get(url, headers=_headers(ceo_token)).status_code == 200

    # 直属上级（direct_leader 且 leader_userid 匹配）→ 200
    dl_token = _login(client, "mock-dl")
    assert client.get(url, headers=_headers(dl_token)).status_code == 200

    # dept_leader 非直属 → 403
    prod_leader_token = _login(client, "mock-prod-leader")
    resp = client.get(url, headers=_headers(prod_leader_token))
    assert resp.status_code == 403

    # 员工查自己 → 403
    eve_token = _login(client, "mock-eve")
    resp = client.get(url, headers=_headers(eve_token))
    assert resp.status_code == 403

    # direct_leader 查非下属 → 403
    resp = client.get(f"/api/v1/history/users/{alice_id}/evaluations", headers=_headers(dl_token))
    assert resp.status_code == 403


def test_query_merged_view_and_peers_parsed(client: TestClient) -> None:
    hr_token = _login(client, "mock-hr")
    _import_both(client, hr_token)

    eve_id = _user_id("mock-eve")
    resp = client.get(f"/api/v1/history/users/{eve_id}/evaluations", headers=_headers(hr_token))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) == 1
    item = data[0]
    assert item["cycle_name"] == "2023H1"

    summary = item["summary"]
    assert summary["superior_score"] == 3.75
    assert summary["is_calibrated"] is True
    assert summary["calibrated_score"] == 4.0

    detail = item["detail"]
    assert detail["self_output"] == "完成核心模块"
    assert detail["superior_comment"] == "表现稳定"
    assert detail["peers"] == [
        {"index": 1, "score": 3.5, "comment": "协作顺畅"},
        {"index": 3, "score": 4.0, "comment": "主动补位"},
    ]


def test_query_cycle_with_only_one_side(client: TestClient) -> None:
    hr_token = _login(client, "mock-hr")
    # 只导入 detail，无 summary：合并视图 summary 为 null
    resp = _post_import(
        client, "/api/v1/import/historical-evaluations/detail", hr_token,
        _make_excel(DETAIL_HEADERS, [_detail_row()]),
    )
    assert resp.status_code == 200, resp.text

    eve_id = _user_id("mock-eve")
    resp = client.get(f"/api/v1/history/users/{eve_id}/evaluations", headers=_headers(hr_token))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) == 1
    assert data[0]["summary"] is None
    assert data[0]["detail"] is not None


def test_import_forbidden_for_non_hr(client: TestClient) -> None:
    alice_token = _login(client, "mock-alice")
    excel = _make_excel(SUMMARY_HEADERS, [_summary_row()])
    resp = _post_import(client, "/api/v1/import/historical-evaluations/summary", alice_token, excel)
    assert resp.status_code == 403
