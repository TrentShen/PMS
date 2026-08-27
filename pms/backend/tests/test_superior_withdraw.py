from __future__ import annotations

"""上级评估撤回（withdraw）接口测试。

口径（2026-08-16 owner 决策）：评估窗口内直属上级/HR 可撤回；窗口外仅超管；
已发布不可撤回；已校准/已提交审批不可撤回。撤回后评估退回草稿、参与人 final_* 清空。
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from pms.database.models.cycle import PerformanceCycle
from pms.database.session import engine


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


SUPERIOR_EVAL_PAYLOAD = {
    "perf_score": 4.0,
    "value_belief_grade": "jia",
    "value_belief_example": "担当事例",
    "value_team_grade": "yi",
    "value_team_example": None,
    "value_growth_grade": "yi",
    "value_growth_example": None,
    "key_results": "整体达预期",
    "comment": None,
}


def _make_cycle(client: TestClient, hr_token: str, alice_id: int, name: str) -> int:
    resp = client.post(
        "/api/v1/cycles",
        headers=_headers(hr_token),
        json={
            "name": name,
            "start_date": "2026-07-01",
            "end_date": "2026-12-31",
            "objective_cycle_id": None,
            "enable_self_eval": False,
            "enable_peer_eval": False,
            "enable_calibration": False,
            "enable_feedback": False,
        },
    )
    assert resp.status_code == 200, resp.text
    cycle_id = resp.json()["id"]
    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/participants",
        headers=_headers(hr_token),
        json={"user_ids": [alice_id]},
    )
    assert resp.status_code == 200, resp.text
    resp = client.post(f"/api/v1/cycles/{cycle_id}/start", headers=_headers(hr_token))
    assert resp.status_code == 200, resp.text
    return cycle_id


def _submit_eval(client: TestClient, token: str, cycle_id: int, alice_id: int) -> None:
    resp = client.post(
        f"/api/v1/cycles/{cycle_id}/users/{alice_id}/superior-evaluation",
        headers=_headers(token),
        json=SUPERIOR_EVAL_PAYLOAD,
    )
    assert resp.status_code == 200, resp.text


def _withdraw(client: TestClient, token: str, cycle_id: int, alice_id: int):
    return client.post(
        f"/api/v1/cycles/{cycle_id}/users/{alice_id}/superior-evaluation/withdraw",
        headers=_headers(token),
    )


def _participant_status(client: TestClient, token: str, cycle_id: int, alice_id: int) -> dict:
    resp = client.get(
        f"/api/v1/cycles/{cycle_id}/users/{alice_id}/detail",
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture(scope="module")
def scenario(
    client: TestClient,
    user_ids: dict[str, int],
    hr_token: str,
    tech_leader_token: str,
) -> dict:
    """周期 + alice 已被上级评估提交（窗口内）。"""
    alice_id = user_ids["mock-alice"]
    cycle_id = _make_cycle(client, hr_token, alice_id, "撤回测试周期A")
    _submit_eval(client, tech_leader_token, cycle_id, alice_id)
    return {"cycle_id": cycle_id, "alice_id": alice_id}


def test_withdraw_by_unrelated_user_forbidden(
    client: TestClient, scenario: dict, carol_token: str
) -> None:
    resp = _withdraw(client, carol_token, scenario["cycle_id"], scenario["alice_id"])
    assert resp.status_code == 403, resp.text


def test_withdraw_ok_reverts_to_draft(
    client: TestClient, scenario: dict, tech_leader_token: str
) -> None:
    resp = _withdraw(client, tech_leader_token, scenario["cycle_id"], scenario["alice_id"])
    assert resp.status_code == 200, resp.text
    assert resp.json()["window_open"] is True

    detail = _participant_status(client, tech_leader_token, scenario["cycle_id"], scenario["alice_id"])
    # 评估退回草稿（内容保留）、参与人状态回退、final_* 清空
    assert detail["superior_evaluation"]["status"] == "draft"
    assert detail["superior_evaluation"]["perf_score"] == 4.0
    assert detail["participant_status"] == "pending"  # 未开自评 → 回退到 pending
    assert detail["final_perf_score"] is None


def test_withdraw_again_400(
    client: TestClient, scenario: dict, tech_leader_token: str
) -> None:
    resp = _withdraw(client, tech_leader_token, scenario["cycle_id"], scenario["alice_id"])
    assert resp.status_code == 400, resp.text
    assert "没有已提交" in resp.json()["detail"]


def test_withdraw_after_window_closed(
    client: TestClient,
    user_ids: dict[str, int],
    hr_token: str,
    tech_leader_token: str,
) -> None:
    """窗口关闭后：上级 403、超管 200。"""
    alice_id = user_ids["mock-alice"]
    cycle_id = _make_cycle(client, hr_token, alice_id, "撤回测试周期B")
    _submit_eval(client, tech_leader_token, cycle_id, alice_id)

    # 直接把 superior_eval 截止日改到昨天（窗口关闭）
    with Session(engine) as s:
        cycle = s.get(PerformanceCycle, cycle_id)
        cycle.stage_json = {"superior_eval_end": (date.today() - timedelta(days=1)).isoformat()}
        s.add(cycle)
        s.commit()

    resp = _withdraw(client, tech_leader_token, cycle_id, alice_id)
    assert resp.status_code == 403, resp.text
    assert "仅超管" in resp.json()["detail"]

    resp = _withdraw(client, _login_ceo(client), cycle_id, alice_id)
    assert resp.status_code == 200, resp.text
    assert resp.json()["window_open"] is False


def test_withdraw_blocked_after_calibration(
    client: TestClient,
    user_ids: dict[str, int],
    hr_token: str,
    tech_leader_token: str,
) -> None:
    """已进校准（有校准改分记录）后不可撤回。"""
    alice_id = user_ids["mock-alice"]
    cycle_id = _make_cycle(client, hr_token, alice_id, "撤回测试周期C")
    # 该校准场景需要开启校准环节
    with Session(engine) as s:
        cycle = s.get(PerformanceCycle, cycle_id)
        cycle.enable_calibration = True
        s.add(cycle)
        s.commit()
    _submit_eval(client, tech_leader_token, cycle_id, alice_id)

    # 校准改分一次（产生 CalibrationRecord）
    resp = client.post(
        f"/api/v1/calibration/cycles/{cycle_id}/calibrate",
        headers=_headers(tech_leader_token),
        json={
            "items": [
                {
                    "user_id": alice_id,
                    "perf_score": 3.75,
                    "value_belief_grade": None,
                    "value_team_grade": None,
                    "value_growth_grade": None,
                    "reason": "校准下调",
                }
            ]
        },
    )
    assert resp.status_code == 200, resp.text

    resp = _withdraw(client, tech_leader_token, cycle_id, alice_id)
    assert resp.status_code == 400, resp.text
    assert "已进入校准" in resp.json()["detail"]


def _login_ceo(client: TestClient) -> str:
    resp = client.post("/api/v1/auth/mock-login", json={"wecom_userid": "mock-ceo"})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]
