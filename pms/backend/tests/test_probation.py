from __future__ import annotations

"""试用期管理模块接口测试

覆盖：自动创建计划、目标保存/提交/审批/驳回、上级评估、列表/详情权限。
"""

from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from pms.database.models import Department, User
from pms.database.models.audit import NotificationLog
from pms.database.models.enums import ProbationPlanStatus, ProbationResult
from pms.database.models.probation import ProbationObjective, ProbationPlan
from pms.database.session import engine
from pms.main import app


def _add_months(d: date, months: int) -> date:
    total_months = d.month - 1 + months
    year = d.year + total_months // 12
    month = total_months % 12 + 1
    max_day = [31, 29 if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    day = min(d.day, max_day)
    return date(year, month, day)


@pytest.fixture(scope="function")
def client():
    return TestClient(app)


@pytest.fixture(scope="function", autouse=True)
def mock_wecom_send():
    """测试期间禁止真实调用企微 API。"""
    with (
        patch("pms.services.wecom.send_text") as _mock_text,
        patch("pms.services.wecom.send_textcard") as _mock_textcard,
        patch("pms.services.wecom.send_markdown") as _mock_markdown,
    ):
        _mock_text.return_value = {"errcode": 0, "errmsg": "ok"}
        _mock_textcard.return_value = {"errcode": 0, "errmsg": "ok"}
        _mock_markdown.return_value = {"errcode": 0, "errmsg": "ok"}
        yield


@pytest.fixture(scope="function")
def probation_users(client: TestClient):
    """复用 seed 中的用户做试用期测试，仅清理 probation 相关数据。"""
    with Session(engine) as s:
        employee = s.exec(select(User).where(User.wecom_userid == "mock-alice")).first()
        leader = s.exec(select(User).where(User.wecom_userid == "mock-tech-leader")).first()
        hr = s.exec(select(User).where(User.wecom_userid == "mock-hr")).first()
        dept = s.exec(select(Department).where(Department.wecom_dept_id == 1)).first()
        assert employee and leader and hr and dept, "seed 数据不完整"

        # 前置清理：其他测试文件（如导入测试）可能已为 alice 建过 plan，
        # 不清理则 /mine 不会自动创建、计划创建通知也不会触发，用例受执行顺序污染
        old_plan_ids = [p.id for p in s.exec(select(ProbationPlan).where(ProbationPlan.user_id == employee.id)).all()]
        if old_plan_ids:
            s.query(ProbationObjective).filter(ProbationObjective.plan_id.in_(old_plan_ids)).delete(synchronize_session=False)
            s.query(ProbationPlan).filter(ProbationPlan.user_id == employee.id).delete(synchronize_session=False)
        s.query(NotificationLog).filter(
            NotificationLog.target_userid.in_(
                [u.wecom_userid for u in (employee, leader, hr) if u]
            )
        ).delete(synchronize_session=False)

        # 把 alice 调整为试用期员工
        employee.hired_at = date.today() - timedelta(days=30)
        employee.probation = 6
        employee.employee_status = "probation"
        employee.leader_userid = leader.wecom_userid
        s.add(employee)
        s.commit()

        yield {
            "leader": leader,
            "employee": employee,
            "hr": hr,
            "dept": dept,
        }

        # 清理：用新会话删除 alice 的 probation 数据及相关通知日志，恢复状态
        with Session(engine) as cleanup_s:
            emp = cleanup_s.get(User, employee.id)
            if emp:
                emp.employee_status = None
                emp.probation = None
                cleanup_s.add(emp)

            plan_ids = [p.id for p in cleanup_s.exec(select(ProbationPlan).where(ProbationPlan.user_id == employee.id)).all()]
            if plan_ids:
                cleanup_s.query(ProbationObjective).filter(ProbationObjective.plan_id.in_(plan_ids)).delete(synchronize_session=False)
                cleanup_s.query(ProbationPlan).filter(ProbationPlan.user_id == employee.id).delete(synchronize_session=False)
            cleanup_s.query(NotificationLog).filter(
                NotificationLog.target_userid.in_(
                    [u.wecom_userid for u in (employee, leader, hr) if u]
                )
            ).delete(synchronize_session=False)
            cleanup_s.commit()


def _login(client: TestClient, wecom_userid: str) -> str:
    resp = client.post("/api/v1/auth/mock-login", json={"wecom_userid": wecom_userid})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _notification_titles(target_userid: str) -> list[str]:
    with Session(engine) as s:
        logs = s.exec(
            select(NotificationLog).where(NotificationLog.target_userid == target_userid)
        ).all()
        return [log.title for log in logs]


class TestProbationLifecycle:
    def test_auto_create_plan_on_mine(self, client: TestClient, probation_users: dict):
        emp = probation_users["employee"]
        token = _login(client, emp.wecom_userid)

        resp = client.get("/api/v1/probation/mine", headers=_headers(token))
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data is not None
        assert data["user_id"] == emp.id
        assert data["status"] == ProbationPlanStatus.DRAFT
        assert data["objectives"] == []

        # 验证员工收到计划创建通知
        assert "试用期计划已创建" in _notification_titles(emp.wecom_userid)

    def test_save_and_submit_objectives(self, client: TestClient, probation_users: dict):
        emp = probation_users["employee"]
        leader = probation_users["leader"]
        token = _login(client, emp.wecom_userid)

        # 先访问 /mine 自动创建计划
        client.get("/api/v1/probation/mine", headers=_headers(token))

        # 保存草稿
        resp = client.post(
            f"/api/v1/probation/{emp.id}/objectives",
            headers=_headers(token),
            json={
                "objectives": [
                    {"title": "熟悉业务", "description": "深入了解产品", "measure_criteria": "完成业务文档学习", "weight": 60, "order_num": 0},
                    {"title": "完成首个任务", "description": "独立交付一个功能", "measure_criteria": "代码合并并通过测试", "weight": 40, "order_num": 1},
                ],
                "submit": False,
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["saved"] == 2

        # 提交审批
        resp = client.post(
            f"/api/v1/probation/{emp.id}/objectives",
            headers=_headers(token),
            json={
                "objectives": [
                    {"title": "熟悉业务", "description": "深入了解产品", "measure_criteria": "完成业务文档学习", "weight": 60, "order_num": 0},
                    {"title": "完成首个任务", "description": "独立交付一个功能", "measure_criteria": "代码合并并通过测试", "weight": 40, "order_num": 1},
                ],
                "submit": True,
            },
        )
        assert resp.status_code == 200, resp.text

        # 验证状态
        resp = client.get("/api/v1/probation/mine", headers=_headers(token))
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == ProbationPlanStatus.OBJECTIVE_PENDING_REVIEW

        # 验证上级收到待审批通知
        assert "试用期目标待审批" in _notification_titles(leader.wecom_userid)

    def test_save_objectives_weight_sum_must_be_100(self, client: TestClient, probation_users: dict):
        emp = probation_users["employee"]
        token = _login(client, emp.wecom_userid)

        client.get("/api/v1/probation/mine", headers=_headers(token))

        # 权重合计 != 100 时拒绝保存
        resp = client.post(
            f"/api/v1/probation/{emp.id}/objectives",
            headers=_headers(token),
            json={
                "objectives": [
                    {"title": "熟悉业务", "description": "深入了解产品", "measure_criteria": "完成业务文档学习", "weight": 50, "order_num": 0},
                    {"title": "完成首个任务", "description": "独立交付一个功能", "measure_criteria": "代码合并并通过测试", "weight": 30, "order_num": 1},
                ],
                "submit": False,
            },
        )
        assert resp.status_code == 400
        assert "权重总和必须为 100" in resp.json()["detail"]

        # 缺省 weight（视为 0）同样被拦截
        resp = client.post(
            f"/api/v1/probation/{emp.id}/objectives",
            headers=_headers(token),
            json={
                "objectives": [
                    {"title": "熟悉业务", "description": "深入了解产品", "measure_criteria": "完成业务文档学习", "order_num": 0},
                ],
                "submit": False,
            },
        )
        assert resp.status_code == 400

    def test_leader_approve_and_evaluate(self, client: TestClient, probation_users: dict):
        emp = probation_users["employee"]
        leader = probation_users["leader"]
        hr = probation_users["hr"]

        # 员工先访问 /mine 自动创建计划，再提交目标
        emp_token = _login(client, emp.wecom_userid)
        client.get("/api/v1/probation/mine", headers=_headers(emp_token))
        client.post(
            f"/api/v1/probation/{emp.id}/objectives",
            headers=_headers(emp_token),
            json={
                "objectives": [
                    {"title": "熟悉业务", "description": "深入了解产品", "measure_criteria": "完成业务文档学习", "weight": 100, "order_num": 0},
                ],
                "submit": True,
            },
        )

        # 上级批准
        leader_token = _login(client, leader.wecom_userid)
        resp = client.post(
            f"/api/v1/probation/{emp.id}/objectives/approve",
            headers=_headers(leader_token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["approved"] == 1

        # 修改计划状态为待评估（模拟临转正）
        hr_token = _login(client, probation_users["hr"].wecom_userid)
        resp = client.patch(
            f"/api/v1/probation/{emp.id}",
            headers=_headers(hr_token),
            json={"status": ProbationPlanStatus.PENDING_EVALUATION},
        )
        assert resp.status_code == 200, resp.text

        # 上级提交评估
        resp = client.post(
            f"/api/v1/probation/{emp.id}/evaluate",
            headers=_headers(leader_token),
            json={"result": ProbationResult.REGULAR, "comment": "表现优秀，建议转正。"},
        )
        assert resp.status_code == 200, resp.text

        # 验证详情
        resp = client.get(f"/api/v1/probation/{emp.id}", headers=_headers(leader_token))
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == ProbationPlanStatus.COMPLETED
        assert data["evaluation"]["result"] == ProbationResult.REGULAR
        assert data["evaluation"]["comment"] == "表现优秀，建议转正。"

        # 验证通知：员工收到目标确认 + 评估完成；HRBP 收到评估完成
        emp_titles = _notification_titles(emp.wecom_userid)
        assert "试用期目标已确认" in emp_titles
        assert "试用期评估已完成" in emp_titles
        assert "试用期评估已完成" in _notification_titles(hr.wecom_userid)

    def test_leader_reject_objectives(self, client: TestClient, probation_users: dict):
        emp = probation_users["employee"]
        leader = probation_users["leader"]

        emp_token = _login(client, emp.wecom_userid)
        client.get("/api/v1/probation/mine", headers=_headers(emp_token))
        client.post(
            f"/api/v1/probation/{emp.id}/objectives",
            headers=_headers(emp_token),
            json={
                "objectives": [{"title": "测试目标", "description": "描述", "measure_criteria": "标准", "weight": 100, "order_num": 0}],
                "submit": True,
            },
        )

        leader_token = _login(client, leader.wecom_userid)
        resp = client.post(
            f"/api/v1/probation/{emp.id}/objectives/reject",
            headers=_headers(leader_token),
            json={"reject_reason": "目标不够具体，请补充衡量标准。"},
        )
        assert resp.status_code == 200, resp.text

        resp = client.get("/api/v1/probation/mine", headers=_headers(emp_token))
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == ProbationPlanStatus.OBJECTIVE_DRAFT

        # 验证员工收到目标被驳回通知
        assert "试用期目标被驳回" in _notification_titles(emp.wecom_userid)

    def test_list_and_permission(self, client: TestClient, probation_users: dict):
        emp = probation_users["employee"]
        leader = probation_users["leader"]
        hr = probation_users["hr"]

        # 先让员工有 plan
        emp_token = _login(client, emp.wecom_userid)
        client.get("/api/v1/probation/mine", headers=_headers(emp_token))

        # 员工列表只能看到自己
        resp = client.get("/api/v1/probation", headers=_headers(emp_token))
        assert resp.status_code == 200, resp.text
        items = resp.json()
        assert all(i["user_id"] == emp.id for i in items)

        # 上级列表能看到下属
        leader_token = _login(client, leader.wecom_userid)
        resp = client.get("/api/v1/probation", headers=_headers(leader_token))
        assert resp.status_code == 200, resp.text
        assert any(i["user_id"] == emp.id for i in resp.json())

        # HR 能看到
        hr_token = _login(client, hr.wecom_userid)
        resp = client.get("/api/v1/probation", headers=_headers(hr_token))
        assert resp.status_code == 200, resp.text
        assert any(i["user_id"] == emp.id for i in resp.json())


class TestProbationPlanUpdate:
    """HR PATCH 试用期计划：status 白名单校验（仅允许前进态/正常态）。"""

    def _create_plan(self, client: TestClient, emp) -> None:
        emp_token = _login(client, emp.wecom_userid)
        resp = client.get("/api/v1/probation/mine", headers=_headers(emp_token))
        assert resp.status_code == 200, resp.text
        assert resp.json() is not None

    def test_patch_rollback_status_rejected(self, client: TestClient, probation_users: dict):
        emp = probation_users["employee"]
        self._create_plan(client, emp)
        hr_token = _login(client, probation_users["hr"].wecom_userid)

        # 回退态（目标流程驱动，不允许 HR 直接设置）
        for status in (
            ProbationPlanStatus.DRAFT,
            ProbationPlanStatus.OBJECTIVE_DRAFT,
            ProbationPlanStatus.OBJECTIVE_PENDING_REVIEW,
        ):
            resp = client.patch(
                f"/api/v1/probation/{emp.id}",
                headers=_headers(hr_token),
                json={"status": status},
            )
            assert resp.status_code == 400, resp.text
            assert "不允许将计划状态修改" in resp.json()["detail"]

    def test_patch_unknown_status_rejected(self, client: TestClient, probation_users: dict):
        emp = probation_users["employee"]
        self._create_plan(client, emp)
        hr_token = _login(client, probation_users["hr"].wecom_userid)

        resp = client.patch(
            f"/api/v1/probation/{emp.id}",
            headers=_headers(hr_token),
            json={"status": "not_a_status"},
        )
        assert resp.status_code == 400, resp.text
        assert "不允许将计划状态修改" in resp.json()["detail"]

    def test_patch_allowed_status_accepted(self, client: TestClient, probation_users: dict):
        emp = probation_users["employee"]
        self._create_plan(client, emp)
        hr_token = _login(client, probation_users["hr"].wecom_userid)

        resp = client.patch(
            f"/api/v1/probation/{emp.id}",
            headers=_headers(hr_token),
            json={"status": ProbationPlanStatus.EXTENDED, "extension_note": "业务需要，延期 1 个月"},
        )
        assert resp.status_code == 200, resp.text

        with Session(engine) as s:
            plan = s.exec(select(ProbationPlan).where(ProbationPlan.user_id == emp.id)).first()
            assert plan.status == ProbationPlanStatus.EXTENDED
            assert plan.extension_note == "业务需要，延期 1 个月"
            assert plan.extended_by == probation_users["hr"].wecom_userid
