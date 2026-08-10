from __future__ import annotations

# 健康检查端点：部署后用于 Nginx/K8s 探针，以及验证应用是否启动成功
# 探针保持轻量：MySQL SELECT 1 + Redis PING，单次尝试不重试（由部署侧健康检查负责重试）
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from loguru import logger
from sqlmodel import text

from pms.database.session import engine, redis_client

router = APIRouter(tags=["health"])


@router.get("/health", response_model=None)
def health() -> dict | JSONResponse:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("health check failed: mysql | {}", exc)
        return JSONResponse(status_code=503, content={"status": "error", "detail": "mysql"})
    try:
        redis_client.ping()
    except Exception as exc:
        logger.warning("health check failed: redis | {}", exc)
        return JSONResponse(status_code=503, content={"status": "error", "detail": "redis"})
    return {"status": "ok"}
