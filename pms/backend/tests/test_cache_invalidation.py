"""缓存失效回归测试：
- admin.patch_user 后清除该用户的 scope 缓存与 user 缓存（不影响其他用户）
- scope.invalidate_all_scope_caches 按前缀清理全部 pms:scope:*，不动 pms:user:*
"""

import json

from fastapi.testclient import TestClient

from pms.database.session import redis_client
from pms.services.scope import invalidate_all_scope_caches


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_patch_user_invalidates_scope_and_user_cache(
    client: TestClient, ceo_token: str, user_ids: dict[str, int]
):
    alice_id = user_ids["mock-alice"]
    bob_id = user_ids["mock-bob"]

    # 预置 alice 的 scope / user 缓存，以及 bob 的 scope 缓存作对照
    alice_scope_key = f"pms:scope:{alice_id}:employee"
    alice_user_key = "pms:user:mock-alice"
    bob_scope_key = f"pms:scope:{bob_id}:employee"
    redis_client.setex(alice_scope_key, 600, json.dumps([alice_id]))
    redis_client.setex(
        alice_user_key, 300, json.dumps({"id": alice_id, "status": "active", "role": "employee"})
    )
    redis_client.setex(bob_scope_key, 600, json.dumps([bob_id]))

    resp = client.patch(
        f"/api/v1/admin/users/{alice_id}",
        headers=_headers(ceo_token),
        json={"leader_userid": "mock-tech-leader"},
    )
    assert resp.status_code == 200, resp.text

    # alice 的 scope 与 user 缓存被清除
    assert redis_client.get(alice_scope_key) is None
    assert redis_client.get(alice_user_key) is None
    # 其他用户的 scope 缓存不受影响
    assert redis_client.get(bob_scope_key) is not None


def test_invalidate_all_scope_caches(user_ids: dict[str, int]):
    alice_id = user_ids["mock-alice"]
    bob_id = user_ids["mock-bob"]
    redis_client.setex(f"pms:scope:{alice_id}:employee", 600, json.dumps([alice_id]))
    redis_client.setex(f"pms:scope:{bob_id}:dept_leader", 600, "null")
    redis_client.setex(
        "pms:user:mock-alice", 300, json.dumps({"id": alice_id, "status": "active", "role": "employee"})
    )

    invalidate_all_scope_caches()

    assert redis_client.get(f"pms:scope:{alice_id}:employee") is None
    assert redis_client.get(f"pms:scope:{bob_id}:dept_leader") is None
    # user 缓存不属于 scope 前缀，不应被清理
    assert redis_client.get("pms:user:mock-alice") is not None
