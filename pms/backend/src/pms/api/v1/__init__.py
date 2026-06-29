from __future__ import annotations

from fastapi import APIRouter

from pms.api.v1 import (
    admin,
    auth,
    calibration,
    cycles,
    evaluations,
    excel_import,
    export,
    feedback,
    health,
    history,
    notify,
    objective_cycles,
    objectives,
    peer,
    probation,
    users,
)

# v1 路由聚合器；后续模块（notify/export）在此继续挂载
api_v1_router = APIRouter(prefix="/v1")
api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(users.router)
api_v1_router.include_router(cycles.router)
api_v1_router.include_router(evaluations.router)
api_v1_router.include_router(peer.router)
api_v1_router.include_router(calibration.router)
api_v1_router.include_router(feedback.router)
api_v1_router.include_router(objective_cycles.router)
api_v1_router.include_router(objectives.router)
api_v1_router.include_router(excel_import.router)
api_v1_router.include_router(export.router)
api_v1_router.include_router(notify.router)
api_v1_router.include_router(history.router)
api_v1_router.include_router(admin.router)
api_v1_router.include_router(probation.router)
