import json

from sqlmodel import Session, select

from pms.database.models.user import Department, User
from pms.database.session import redis_client

SCOPE_CACHE_TTL = 600  # 10 minutes


def _descendant_dept_ids(session: Session, root_dept_id: int) -> set[int]:
    # BFS 递归展开子部门；返回包含 root 自己的 id 集合
    visited: set[int] = {root_dept_id}
    frontier = [root_dept_id]
    while frontier:
        children = session.exec(
            select(Department.id).where(Department.parent_id.in_(frontier))
        ).all()
        new_ids = [c for c in children if c not in visited]
        if not new_ids:
            break
        visited.update(new_ids)
        frontier = new_ids
    return visited


def _get_hr_dept_ids(session: Session) -> set[int]:
    """找到所有"HR 部门"的 id（部门中有 hrbp 角色成员的部门 + 其子部门）"""
    # HR 部门 = 有 hrbp 角色用户所在的部门
    hr_dept_ids_raw = session.exec(
        select(User.department_id).where(
            User.role == "hrbp",
            User.department_id != None,  # noqa: E711
        ).distinct()
    ).all()
    if not hr_dept_ids_raw:
        return set()
    # 把子部门也算进去
    result: set[int] = set()
    for did in hr_dept_ids_raw:
        result.update(_descendant_dept_ids(session, did))
    return result


def _hr_dept_member_ids(session: Session) -> set[int]:
    """HR 部门的所有成员 user.id"""
    hr_depts = _get_hr_dept_ids(session)
    if not hr_depts:
        return set()
    members = session.exec(
        select(User.id).where(User.department_id.in_(hr_depts))
    ).all()
    return set(members)


def visible_user_ids(session: Session, current: User) -> set[int] | None:
    """返回 None 表示不做限制（全局可见）；否则返回可见 user.id 集合"""
    cache_key = f"pms:scope:{current.id}"
    cached = redis_client.get(cache_key)
    if cached:
        data = json.loads(cached)
        if data is None:
            return None
        return set(data)

    result = _compute_visible_user_ids(session, current)

    redis_client.setex(
        cache_key,
        SCOPE_CACHE_TTL,
        json.dumps(list(result) if result is not None else None),
    )
    return result


def invalidate_scope_cache(user_id: int) -> None:
    redis_client.delete(f"pms:scope:{user_id}")


def _compute_visible_user_ids(session: Session, current: User) -> set[int] | None:
    role = current.role

    if role == "super_admin":
        return None

    hr_member_ids = _hr_dept_member_ids(session)
    hr_dept_ids = _get_hr_dept_ids(session)

    is_in_hr_dept = current.department_id is not None and current.department_id in hr_dept_ids
    is_hr_dept_leader = (
        role == "dept_leader" and is_in_hr_dept
    )

    if is_hr_dept_leader:
        return None

    if role == "hrbp":
        scope = current.hrbp_scope_dept_ids
        if not scope:
            all_ids = set(session.exec(select(User.id).where(User.status == "active")).all())
            result = all_ids - hr_member_ids
            if current.id is not None:
                result.add(current.id)
            return result
        all_dept_ids: set[int] = set()
        for dept_id in scope:
            all_dept_ids.update(_descendant_dept_ids(session, dept_id))
        members = session.exec(
            select(User.id).where(User.department_id.in_(all_dept_ids))
        ).all()
        result = set(members) - hr_member_ids
        if current.id is not None:
            result.add(current.id)
        return result

    visible: set[int] = set()
    if current.id is not None:
        visible.add(current.id)

    if role == "dept_leader" and current.department_id is not None:
        dept_ids = _descendant_dept_ids(session, current.department_id)
        dept_members = session.exec(
            select(User.id).where(User.department_id.in_(dept_ids))
        ).all()
        visible.update(dept_members)
        if not is_hr_dept_leader:
            visible -= hr_member_ids
            if current.id is not None:
                visible.add(current.id)

    subordinates = session.exec(
        select(User.id).where(User.leader_userid == current.wecom_userid)
    ).all()
    sub_set = set(subordinates)
    if not is_hr_dept_leader:
        sub_set -= hr_member_ids
    visible.update(sub_set)

    return visible


def ensure_can_view_user(session: Session, current: User, target_user_id: int) -> None:
    # 快速断言：抛 HTTPException 403 表示无权限
    from fastapi import HTTPException

    ids = visible_user_ids(session, current)
    if ids is None:
        return
    if target_user_id not in ids:
        raise HTTPException(status_code=403, detail="无权查看该用户数据")
