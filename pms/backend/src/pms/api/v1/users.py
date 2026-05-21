# 用户列表 + 通讯录同步
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlmodel import Session, select

from pms.database.models.user import Department, User
from pms.database.session import get_session
from pms.services.auth import require_role
from pms.services.scope import visible_user_ids
from pms.services.wecom import list_departments, list_users_detail_by_dept

router = APIRouter(prefix="/users", tags=["users"])


class UserBrief(BaseModel):
    id: int
    wecom_userid: str
    name: str
    role: str
    position: str | None
    leader_userid: str | None
    department_id: int | None


@router.get("", response_model=list[UserBrief])
def list_users(
    session: Session = Depends(get_session),
    hr: User = Depends(require_role("hrbp", "super_admin")),
) -> list[UserBrief]:
    q = select(User).where(User.status == "active")
    scope = visible_user_ids(session, hr)
    if scope is not None:
        q = q.where(User.id.in_(scope))
    users = session.exec(q).all()
    return [UserBrief.model_validate(u, from_attributes=True) for u in users]


# ---------- 通讯录同步 ----------

def _sync_departments(session: Session) -> None:
    """同步部门树到本地 department 表"""
    depts = list_departments()
    for d in depts:
        existing = session.exec(
            select(Department).where(Department.wecom_dept_id == d["id"])
        ).first()
        if existing:
            existing.name = d["name"]
            existing.parent_id = d.get("parentid")
            existing.order_num = d.get("order", 0)
        else:
            session.add(Department(
                wecom_dept_id=d["id"],
                name=d["name"],
                parent_id=d.get("parentid"),
                order_num=d.get("order", 0),
            ))
    session.commit()
    logger.info("部门同步完成: {} 个部门", len(depts))


def _map_dept_path(dept_ids: list[int], session: Session) -> str | None:
    """将企微部门 id 列表映射到本地部门 id"""
    if not dept_ids:
        return None
    # 取第一个（主部门），V0.9 简化处理
    local = session.exec(
        select(Department).where(Department.wecom_dept_id == dept_ids[0])
    ).first()
    return str(local.id) if local else None


def _sync_users(session: Session) -> int:
    """全量同步用户（从根部门拉取）"""
    userlist = list_users_detail_by_dept(1, fetch_child=True)
    count = 0
    for u in userlist:
        wecom_userid = u.get("userid")
        if not wecom_userid:
            continue
        local = session.exec(
            select(User).where(User.wecom_userid == wecom_userid)
        ).first()
        dept_ids = u.get("department", [])
        dept_path = _map_dept_path(dept_ids, session)
        status = "active" if u.get("status") == 1 else "inactive"
        if local:
            local.name = u.get("name") or local.name
            local.avatar = u.get("avatar")
            local.position = u.get("position")
            local.leader_userid = u.get("direct_leader")
            if dept_path and not local.department_id:
                local.department_id = int(dept_path) if dept_path.isdigit() else None
            local.status = status
            local.synced_at = datetime.utcnow()
        else:
            session.add(User(
                wecom_userid=wecom_userid,
                name=u.get("name") or wecom_userid,
                avatar=u.get("avatar"),
                department_id=int(dept_path) if dept_path and dept_path.isdigit() else None,
                position=u.get("position"),
                leader_userid=u.get("direct_leader"),
                role="employee",
                status=status,
            ))
        count += 1
    session.commit()
    return count


@router.post("/sync")
def sync_contacts(
    session: Session = Depends(get_session),
    hr: User = Depends(require_role("hrbp", "super_admin")),
):
    """手动触发通讯录全量同步"""
    try:
        _sync_departments(session)
        user_count = _sync_users(session)
        logger.info("通讯录手动同步完成: {} 个用户", user_count)
        return {"status": "ok", "departments_synced": True, "users_synced": user_count}
    except Exception as e:
        logger.error("通讯录同步失败: {}", e)
        raise HTTPException(status_code=500, detail=f"同步失败: {e}")
