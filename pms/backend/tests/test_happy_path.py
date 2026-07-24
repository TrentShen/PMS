from __future__ import annotations

"""Happy path 接口自动化测试

覆盖完整绩效周期：
HR 创建/启动周期 → 员工写目标+自评 → 互评邀请/审批/提交 →
Leader 上级评估 → 校准 → HR/CEO 审批 → 面谈 → 员工确认 →
HR 发布 → 导出 Excel

用法：
    cd pms/backend
    source .venv/bin/activate
    pytest tests/test_happy_path.py -v

注意：该测试会清空业务表并重新 seed 数据，请在独立测试数据库运行。
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, text

from pms.database.models import User
from pms.database.session import engine
from pms.main import app
from pms.services.seed import seed


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """清空业务表并重新 seed，确保测试独立。"""
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
    # 测试结束后保留数据，方便人工查验；如需清理请手动 truncate。


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _login(client: TestClient, wecom_userid: str) -> str:
    """mock 登录并返回 JWT token。"""
    resp = client.post("/api/v1/auth/mock-login", json={"wecom_userid": wecom_userid})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _user_ids(client: TestClient) -> dict[str, int]:
    """获取 seed 中所有 mock 用户的数字 ID。"""
    # 任意用户登录都能拿到 mock-users 列表
    token = _login(client, "mock-hr")
    resp = client.get("/api/v1/auth/mock-users", headers=_headers(token))
    assert resp.status_code == 200, resp.text
    return {u["wecom_userid"]: u["id"] for u in resp.json()}


def test_full_performance_cycle(client: TestClient) -> None:
    # ========== 0. 准备用户 ID ==========
    uids = _user_ids(client)
    alice_id = uids["mock-alice"]
    bob_id = uids["mock-bob"]
    carol_id = uids["mock-carol"]
    david_id = uids["mock-david"]
    employee_ids = [alice_id, bob_id, carol_id, david_id]

    # ========== 1. HR 创建目标周期 + 绩效周期 ==========
    hr_token = _login(client, "mock-hr")
    resp = client.post(
        "/api/v1/objective-cycles",
        headers=_headers(hr_token),
        json={
            "name": "2025 下半年度目标（自动化测试）",
            "start_date": "2025-07-01",
            "end_date": "2025-12-31",
        },
    )
    assert resp.status_code == 200, resp.text
    objective_cycle_id = resp.json()["id"]

    resp = client.post(
        "/api/v1/cycles",
        headers=_headers(hr_token),
        json={
            "name": "2025 下半年度绩效考核（自动化测试）",
            "start_date": "2025-07-01",
            "end_date": "2025-12-31",
            "objective_cycle_id": objective_cycle_id,
            "enable_self_eval": True,
            "enable_peer_eval": True,
            "enable_calibration": True,
            "enable_feedback": True,
            "exclusion_rules": {
                "exclude_dept_ids": [],
                "exclude_positions": [],
                "exclude_levels": [],
                "exclude_entry_after": None,
                "exclude_status": ["resigned"],
            },
        },
    )
    assert resp.status_code == 200, resp.text
    cycle_id = resp.json()["id"]
    assert resp.json()["status"] == "draft"

    # ========== 2. HR 添加参与人 ==========
    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/participants",
        headers=_headers(hr_token),
        json={"user_ids": employee_ids},
    )
    assert resp.status_code == 200, resp.text

    # ========== 3. HR 启动周期 ==========
    resp = client.post(f"/api/v1/cycles/{cycle_id}/start", headers=_headers(hr_token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "in_progress"

    # ========== 4. 每位员工写目标并提交自评 ==========
    objectives_payload = {
        "items": [
            {
                "title": "核心项目交付",
                "description": "按期高质量完成负责模块",
                "measure_criteria": "里程碑全部达成",
                "weight": 40,
            },
            {
                "title": "协作与沟通",
                "description": "跨团队协作效率",
                "measure_criteria": "无重大协作投诉",
                "weight": 30,
            },
            {
                "title": "能力提升",
                "description": "学习新技术/方法并落地",
                "measure_criteria": "有具体落地案例",
                "weight": 30,
            },
        ]
    }
    self_eval_payload = {
        "perf_score": 3.75,
        "value_belief_grade": "yi",
        "value_belief_example": None,
        "value_team_grade": "jia",
        "value_team_example": "主动协助同事解决阻塞问题",
        "value_growth_grade": "yi",
        "value_growth_example": None,
        "key_results": "完成 MVP 上线，用户反馈良好",
        "comment": None,
    }

    for uid in employee_ids:
        token = _login(client, f"mock-{_name_by_id(uid)}")
        # 写目标
        resp = client.put(
            f"/api/v1/objective-cycles/{objective_cycle_id}/objectives",
            headers=_headers(token),
            json=objectives_payload,
        )
        assert resp.status_code == 200, f"写目标失败 uid={uid}: {resp.text}"
        # 自评
        resp = client.post(
            f"/api/v1/cycles/{cycle_id}/self-evaluation",
            headers=_headers(token),
            json=self_eval_payload,
        )
        assert resp.status_code == 200, f"自评失败 uid={uid}: {resp.text}"

    # ========== 5. 员工邀请互评人 ==========
    # alice -> carol, bob -> david, carol -> alice, david -> bob
    peer_pairs = [
        (alice_id, carol_id),
        (bob_id, david_id),
        (carol_id, alice_id),
        (david_id, bob_id),
    ]
    for inviter_id, peer_id in peer_pairs:
        token = _login(client, f"mock-{_name_by_id(inviter_id)}")
        resp = client.post(
            f"/api/v1/cycles/{cycle_id}/peer/invite",
            headers=_headers(token),
            json={"peer_user_ids": [peer_id]},
        )
        assert resp.status_code == 200, f"邀请互评失败 {inviter_id}->{peer_id}: {resp.text}"

    # ========== 6. Leader 审核互评名单 ==========
    for leader_uid, subordinate_ids in [
        ("mock-tech-leader", [alice_id, bob_id]),
        ("mock-prod-leader", [carol_id, david_id]),
    ]:
        token = _login(client, leader_uid)
        for sub_id in subordinate_ids:
            resp = client.post(
                f"/api/v1/cycles/{cycle_id}/users/{sub_id}/peer/approve",
                headers=_headers(token),
                json={"add_user_ids": [], "remove_user_ids": []},
            )
            assert resp.status_code == 200, f"审核互评名单失败 {leader_uid}/{sub_id}: {resp.text}"

    # ========== 7. 互评人提交互评 ==========
    peer_submit_payload = {
        "perf_score": 3.5,
        "value_belief_grade": "yi",
        "value_belief_example": None,
        "value_team_grade": "yi",
        "value_team_example": None,
        "value_growth_grade": "jia",
        "value_growth_example": "主动分享新技术方案",
        "comment": "协作顺畅",
    }
    for evaluator_id in [carol_id, david_id, alice_id, bob_id]:
        token = _login(client, f"mock-{_name_by_id(evaluator_id)}")
        resp = client.get("/api/v1/peer/my-tasks", headers=_headers(token))
        assert resp.status_code == 200, resp.text
        data = resp.json()
        tasks = data if isinstance(data, list) else data.get("items", [])
        for task in tasks:
            resp = client.post(
                f"/api/v1/peer/tasks/{task['id']}/submit",
                headers=_headers(token),
                json=peer_submit_payload,
            )
            assert resp.status_code == 200, f"互评提交失败 task={task['id']}: {resp.text}"

    # ========== 8. Leader 提交上级评估 ==========
    superior_eval_payload = {
        "perf_score": 3.5,
        "value_belief_grade": "yi",
        "value_belief_example": None,
        "value_team_grade": "yi",
        "value_team_example": None,
        "value_growth_grade": "yi",
        "value_growth_example": None,
        "key_results": "整体达预期",
        "comment": "继续保持",
    }
    for leader_uid, subordinate_ids in [
        ("mock-tech-leader", [alice_id, bob_id]),
        ("mock-prod-leader", [carol_id, david_id]),
    ]:
        token = _login(client, leader_uid)
        for sub_id in subordinate_ids:
            resp = client.post(
                f"/api/v1/cycles/{cycle_id}/users/{sub_id}/superior-evaluation",
                headers=_headers(token),
                json=superior_eval_payload,
            )
            assert resp.status_code == 200, f"上级评估失败 {leader_uid}/{sub_id}: {resp.text}"

    # ========== 9. 校准 ==========
    leader_token = _login(client, "mock-tech-leader")
    resp = client.get(f"/api/v1/calibration/cycles/{cycle_id}/view", headers=_headers(leader_token))
    assert resp.status_code == 200, resp.text
    calibrate_items = [
        {
            "user_id": uid,
            "perf_score": 4.0,
            "value_belief_grade": "jia",
            "value_team_grade": "yi",
            "value_growth_grade": "yi",
            "reason": "项目贡献突出，给予上调",
        }
        for uid in employee_ids
    ]
    # calibrate 接口已加 scope 校验：dept_leader 只能校准管辖内员工，
    # 跨部门（employee_ids 含产品部）必须由 HR/超管操作
    hr_token = _login(client, "mock-hr")
    resp = client.post(
        f"/api/v1/calibration/cycles/{cycle_id}/calibrate",
        headers=_headers(hr_token),
        json={"items": calibrate_items},
    )
    assert resp.status_code == 200, resp.text

    # 提交校准结果进入审批
    resp = client.post(
        f"/api/v1/calibration/cycles/{cycle_id}/submit-calibration",
        headers=_headers(leader_token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "pending_hr"

    # ========== 10. HR 审批 -> CEO 审批 ==========
    hr_token = _login(client, "mock-hr")
    resp = client.post(
        f"/api/v1/calibration/cycles/{cycle_id}/approval",
        headers=_headers(hr_token),
        json={"action": "approve", "comment": "同意"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "pending_ceo"

    ceo_token = _login(client, "mock-ceo")
    resp = client.post(
        f"/api/v1/calibration/cycles/{cycle_id}/approval",
        headers=_headers(ceo_token),
        json={"action": "approve", "comment": "批准"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "approved"

    # ========== 11. Leader 填写反馈面谈 ==========
    feedback_payload = {
        "strengths": "技术扎实，执行力强",
        "improvements": "需要加强跨部门沟通",
        "next_goals": "下季度主导一个完整模块",
    }
    for leader_uid, subordinate_ids in [
        ("mock-tech-leader", [alice_id, bob_id]),
        ("mock-prod-leader", [carol_id, david_id]),
    ]:
        token = _login(client, leader_uid)
        for sub_id in subordinate_ids:
            resp = client.post(
                f"/api/v1/feedback/cycles/{cycle_id}/users/{sub_id}",
                headers=_headers(token),
                json=feedback_payload,
            )
            assert resp.status_code == 200, f"面谈提交失败 {leader_uid}/{sub_id}: {resp.text}"

    # ========== 12. 员工确认反馈 ==========
    for uid in employee_ids:
        token = _login(client, f"mock-{_name_by_id(uid)}")
        resp = client.post(
            f"/api/v1/feedback/cycles/{cycle_id}/confirm",
            headers=_headers(token),
            json={"action": "confirmed"},
        )
        assert resp.status_code == 200, f"确认反馈失败 uid={uid}: {resp.text}"

    # ========== 13. HR 发布周期 ==========
    hr_token = _login(client, "mock-hr")
    resp = client.post(f"/api/v1/cycles/{cycle_id}/publish", headers=_headers(hr_token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "published"

    # ========== 14. HR 导出 Excel ==========
    resp = client.get(f"/api/v1/export/cycles/{cycle_id}", headers=_headers(hr_token))
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _name_by_id(user_id: int) -> str:
    """根据 seed 中的 user_id 返回用户名前缀。"""
    with Session(engine) as session:
        user = session.get(User, user_id)
    if user is None:
        raise ValueError(f"未知 user_id: {user_id}")
    name_map = {
        "mock-alice": "alice",
        "mock-bob": "bob",
        "mock-carol": "carol",
        "mock-david": "david",
    }
    return name_map.get(user.wecom_userid, user.wecom_userid.replace("mock-", ""))
