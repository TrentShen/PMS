from __future__ import annotations

# 用户列表 + 通讯录同步
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlmodel import Session, select

from pms.database.models.user import Department, User
from pms.database.session import get_session
from pms.services.auth import require_role
from pms.services.scope import visible_user_ids
from pms.services.wecom import (
    batch_get_hr_staff_info,
    list_departments,
    list_users_detail_by_dept,
)

router = APIRouter(prefix="/users", tags=["users"])


class UserBrief(BaseModel):
    id: int
    wecom_userid: str
    name: str
    role: str
    position: str | None
    leader_userid: str | None
    department_id: int | None
    employee_type: str | None


class UserHRInfo(BaseModel):
    """HR 专用：员工人事信息，包含敏感字段，需严格权限控制"""
    id: int
    wecom_userid: str
    name: str
    hired_at: date | None
    confirm_date: date | None
    probation: int | None
    employee_status: str | None
    employee_type: str | None


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

    # 按树深度（BFS）排序，确保父部门先于子部门插入
    dept_map = {d["id"]: d for d in depts}
    children_map: dict[int, list[int]] = {}
    roots: list[int] = []
    for d in depts:
        parent = d.get("parentid") or 0
        if parent in (0, 1):
            roots.append(d["id"])
        else:
            children_map.setdefault(parent, []).append(d["id"])

    ordered_ids: list[int] = []
    queue = list(roots)
    while queue:
        dept_id = queue.pop(0)
        if dept_id not in dept_map:
            continue
        ordered_ids.append(dept_id)
        for child_id in children_map.get(dept_id, []):
            queue.append(child_id)

    # 如果企微返回的部门有循环或孤立节点，追加到末尾
    seen = set(ordered_ids)
    for d in depts:
        if d["id"] not in seen:
            ordered_ids.append(d["id"])
            seen.add(d["id"])

    # wecom_dept_id -> 本地 id 映射（用于转换 parent_id）
    wecom_to_local: dict[int, int] = {}
    skipped = 0
    for dept_id in ordered_ids:
        d = dept_map[dept_id]
        existing = session.exec(
            select(Department).where(Department.wecom_dept_id == d["id"])
        ).first()
        parent_wecom = d.get("parentid")
        # 根部门 parentid 为 0 或 1，本地存 None
        local_parent_id = None
        if parent_wecom and parent_wecom not in (0, 1):
            local_parent_id = wecom_to_local.get(parent_wecom)
            if local_parent_id is None:
                logger.warning("部门 {} 的父部门 {} 尚未同步，跳过", d["id"], parent_wecom)
                skipped += 1
                continue

        if existing:
            existing.name = d["name"]
            existing.parent_id = local_parent_id
            existing.order_num = d.get("order", 0)
            session.add(existing)
            wecom_to_local[d["id"]] = existing.id
        else:
            dept = Department(
                wecom_dept_id=d["id"],
                name=d["name"],
                parent_id=local_parent_id,
                order_num=d.get("order", 0),
            )
            session.add(dept)
            session.flush()  # 立即获取自增 id
            wecom_to_local[d["id"]] = dept.id

    session.commit()
    logger.info("部门同步完成: {} 个部门, 跳过 {} 个", len(depts), skipped)


def _map_dept_path(dept_ids: list[int], session: Session) -> str | None:
    """将企微部门 id 列表映射到本地部门 id"""
    if not dept_ids:
        return None
    # 取第一个（主部门），V0.9 简化处理
    local = session.exec(
        select(Department).where(Department.wecom_dept_id == dept_ids[0])
    ).first()
    return str(local.id) if local else None


def _enrich_users_hr_info(session: Session, user_ids: list[int] | None = None) -> int:
    """批量从人事助手补充员工人事字段（用于后台同步任务，避免请求链路阻塞）"""
    q = select(User).where(User.status == "active")
    if user_ids:
        q = q.where(User.id.in_(user_ids))
    users = session.exec(q).all()
    if not users:
        return 0

    userid_to_user = {u.wecom_userid: u for u in users}
    results = batch_get_hr_staff_info(list(userid_to_user.keys()))

    updated = 0
    for userid, info in results.items():
        user = userid_to_user.get(userid)
        if not user:
            continue
        if info.get("hired_at"):
            user.hired_at = info["hired_at"]
        if info.get("confirm_date"):
            user.confirm_date = info["confirm_date"]
        if info.get("probation") is not None:
            user.probation = info["probation"]
        if info.get("employee_status"):
            user.employee_status = info["employee_status"]
        if info.get("employee_type"):
            user.employee_type = info["employee_type"]
        updated += 1

    session.commit()
    logger.info("人事字段补充完成: {} 人", updated)
    return updated


def _normalize_leader(value: str | list[str] | None) -> str | None:
    """把企微 direct_leader（可能是字符串或列表）归一化为单个字符串"""
    if not value:
        return None
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _assign_leader_roles(session: Session) -> int:
    """根据 direct_leader 关系自动给有下属的用户分配 direct_leader 角色。

    只升级当前 role=employee 的用户；已有的 super_admin/hrbp/dept_leader/direct_leader 不降级。
    """
    leader_ids = session.exec(
        select(User.leader_userid).where(User.leader_userid.isnot(None)).distinct()
    ).all()
    assigned = 0
    for leader_id in leader_ids:
        if not leader_id:
            continue
        leader = session.exec(select(User).where(User.wecom_userid == leader_id)).first()
        if not leader:
            continue
        if leader.role in ("super_admin", "hrbp", "dept_leader", "direct_leader"):
            continue
        leader.role = "direct_leader"
        session.add(leader)
        assigned += 1
    if assigned:
        logger.info("自动分配 direct_leader 角色: {} 人", assigned)
    return assigned


def _sync_users(session: Session) -> int:
    """全量同步用户基础信息（从根部门拉取），不调用人事助手

    注意：部门/姓名/职位/上级均以企微通讯录为准，本地会被覆盖。
    """
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
        leader_userid = _normalize_leader(u.get("direct_leader"))
        if local:
            local.name = u.get("name") or local.name
            local.avatar = u.get("avatar")
            local.position = u.get("position")
            local.leader_userid = leader_userid
            # 始终以企微主部门覆盖本地部门（修复历史错误绑定）
            local.department_id = int(dept_path) if dept_path and dept_path.isdigit() else None
            local.status = status
            local.synced_at = datetime.now(timezone.utc)
        else:
            session.add(User(
                wecom_userid=wecom_userid,
                name=u.get("name") or wecom_userid,
                avatar=u.get("avatar"),
                department_id=int(dept_path) if dept_path and dept_path.isdigit() else None,
                position=u.get("position"),
                leader_userid=leader_userid,
                role="employee",
                status=status,
            ))
        count += 1

    # 企微通讯录中已不存在的本地用户标记为 inactive
    synced_userids = {u.get("userid") for u in userlist if u.get("userid")}
    stale_users = session.exec(
        select(User).where(User.status == "active", User.wecom_userid.not_in(synced_userids))
    ).all()
    for stale in stale_users:
        stale.status = "inactive"
        stale.synced_at = datetime.now(timezone.utc)
        session.add(stale)
        logger.warning("企微通讯录中已无用户 {}, 标记为 inactive", stale.wecom_userid)

    # 根据 direct_leader 关系自动给有下属的用户分配 direct_leader 角色
    _assign_leader_roles(session)

    session.commit()
    return count


@router.post("/sync")
def sync_contacts(
    session: Session = Depends(get_session),
    hr: User = Depends(require_role("hrbp", "super_admin")),
):
    """手动触发通讯录全量同步（基础信息 + 人事字段）"""
    try:
        _sync_departments(session)
        user_count = _sync_users(session)
        hr_count = _enrich_users_hr_info(session)
        logger.info("通讯录手动同步完成: {} 个用户, {} 个人事字段补充", user_count, hr_count)
        return {
            "status": "ok",
            "departments_synced": True,
            "users_synced": user_count,
            "hr_enriched": hr_count,
        }
    except Exception as e:
        logger.error("通讯录同步失败: {}", e)
        raise HTTPException(status_code=500, detail=f"同步失败: {e}") from e


@router.post("/sync/hr-info")
def sync_hr_info(
    session: Session = Depends(get_session),
    hr: User = Depends(require_role("hrbp", "super_admin")),
):
    """手动触发人事字段补充（不重新同步通讯录基础信息）"""
    try:
        count = _enrich_users_hr_info(session)
        return {"status": "ok", "hr_enriched": count}
    except Exception as e:
        logger.error("人事字段补充失败: {}", e)
        raise HTTPException(status_code=500, detail=f"同步失败: {e}") from e


@router.get("/{user_id}/hr", response_model=UserHRInfo)
def get_user_hr_info(
    user_id: int,
    session: Session = Depends(get_session),
    hr: User = Depends(require_role("hrbp", "super_admin")),
):
    """获取员工人事信息（HR/超管专用）"""
    user = session.exec(select(User).where(User.id == user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return UserHRInfo.model_validate(user, from_attributes=True)
