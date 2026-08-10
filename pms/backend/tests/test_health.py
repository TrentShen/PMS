"""/health 探针测试：正常 200；MySQL 失败 503；Redis 失败 503。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from pms.api.v1 import health as health_module


class _BrokenEngine:
    """connect 即抛错的假 engine，模拟 MySQL 不可用。"""

    def connect(self):
        raise ConnectionError("mysql down")


class _BrokenRedis:
    """ping 即抛错的假客户端，模拟 Redis 不可用。"""

    def ping(self):
        raise ConnectionError("redis down")


def test_health_ok(client: TestClient):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_mysql_down(client: TestClient, monkeypatch):
    monkeypatch.setattr(health_module, "engine", _BrokenEngine())
    resp = client.get("/api/v1/health")
    assert resp.status_code == 503
    assert resp.json() == {"status": "error", "detail": "mysql"}


def test_health_redis_down(client: TestClient, monkeypatch):
    monkeypatch.setattr(health_module, "redis_client", _BrokenRedis())
    resp = client.get("/api/v1/health")
    assert resp.status_code == 503
    assert resp.json() == {"status": "error", "detail": "redis"}
