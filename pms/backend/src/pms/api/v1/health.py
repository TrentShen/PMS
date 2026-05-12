# 健康检查端点：部署后用于 Nginx/K8s 探针，以及验证应用是否启动成功
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}
