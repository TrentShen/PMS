from __future__ import annotations

"""公共 fixtures 与测试工具。"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, text

from pms.database.session import engine, redis_client
from pms.main import app
from pms.services.seed import seed


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """全局初始化：清空业务表并重新 seed 一次。"""
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


@pytest.fixture(autouse=True)
def _flush_redis_cache():
    """每个测试前清理 pms:user / pms:scope 缓存。

    测试会频繁 TRUNCATE + reseed 或直接改 role/department，
    而缓存 TTL 10 分钟且不随 DB 重置失效，跨文件会读到脏数据。
    """
    for pattern in ("pms:user:*", "pms:scope:*"):
        keys = list(redis_client.scan_iter(match=pattern))
        if keys:
            redis_client.delete(*keys)
    yield


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


def _login(client: TestClient, wecom_userid: str) -> str:
    resp = client.post("/api/v1/auth/mock-login", json={"wecom_userid": wecom_userid})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def user_ids(client: TestClient) -> dict[str, int]:
    """获取 seed 中所有 mock 用户的数字 ID。"""
    token = _login(client, "mock-hr")
    resp = client.get("/api/v1/auth/mock-users", headers=_headers(token))
    assert resp.status_code == 200, resp.text
    return {u["wecom_userid"]: u["id"] for u in resp.json()}


@pytest.fixture(scope="session")
def alice_token(client: TestClient) -> str:
    return _login(client, "mock-alice")


@pytest.fixture(scope="session")
def bob_token(client: TestClient) -> str:
    return _login(client, "mock-bob")


@pytest.fixture(scope="session")
def carol_token(client: TestClient) -> str:
    return _login(client, "mock-carol")


@pytest.fixture(scope="session")
def tech_leader_token(client: TestClient) -> str:
    return _login(client, "mock-tech-leader")


@pytest.fixture(scope="session")
def prod_leader_token(client: TestClient) -> str:
    return _login(client, "mock-prod-leader")


@pytest.fixture(scope="session")
def hr_token(client: TestClient) -> str:
    return _login(client, "mock-hr")


@pytest.fixture(scope="session")
def ceo_token(client: TestClient) -> str:
    return _login(client, "mock-ceo")


@pytest.fixture(scope="session")
def objective_cycle_id(client: TestClient, hr_token: str) -> int:
    """返回 seed 中第一个目标周期的 ID（默认与第一个绩效周期关联）。"""
    resp = client.get("/api/v1/objective-cycles", headers=_headers(hr_token))
    assert resp.status_code == 200, resp.text
    cycles = resp.json()
    assert cycles, "没有目标周期"
    return cycles[0]["id"]
