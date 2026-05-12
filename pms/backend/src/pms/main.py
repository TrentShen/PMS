# FastAPI 应用入口
# 启动方式：uvicorn pms.main:app --host 0.0.0.0 --port 8000 --reload
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from pms.api.v1 import api_v1_router
from pms.configs import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动期：打印关键配置（不打印 secret），便于排查
    logger.info(
        "PMS starting | env={} port={} mysql={}:{} redis={}:{}",
        settings.app_env,
        settings.app_port,
        settings.mysql_host,
        settings.mysql_port,
        settings.redis_host,
        settings.redis_port,
    )
    # 启动定时任务（截止提醒等）
    from pms.scheduler.jobs import start_scheduler
    start_scheduler()
    yield
    logger.info("PMS shutting down")


app = FastAPI(
    title="PMS - Performance Management System",
    version="0.9.0",
    description="企业绩效管理系统（企业微信 H5）",
    lifespan=lifespan,
)

# 本地开发允许前端跨域；生产通过同域 Nginx 不需要 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix="/api")


@app.get("/")
def root() -> dict:
    return {"app": "pms", "version": "0.9.0", "docs": "/docs"}
