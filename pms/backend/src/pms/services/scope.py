# 权限范围过滤（PRD 2.2 最小可见原则）
# 核心函数：visible_user_ids(current_user) -> 当前用户能看到的 user.id 集合
# 所有查询员工绩效数据的接口必须先拿到这个集合做 WHERE IN
#
# 规则细化：
#   1) 部门 Leader：本部门 + 全部子部门（递归）
#   2) HRBP：全局或按 hrbp_scope_dept_ids 限制，**但排除自己所属部门**（利益回避）
#   3) 任何"有下属"的人（不一定是 dept_leader 角色）都能看下属
#   4) HR 部门成员的绩效数据只对 HR 部门 Leader + 超管可见
from sqlmodel import Session, select

from pms.database.models.user import Department, User


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
    """返回 None 表示不做限制（全局可见）；否则返回可见 user.id 集合

    规则：
    - super_admin: 全局（含 HR 部门）
    - hrbp: 管辖范围内所有人，**但排除 HR 部门成员**（利益回避：HR 看不到同部门绩效）
    - dept_leader:
        - 如果是 HR 部门的 Leader → 可以看 HR 部门成员
        - 如果是其他部门 Leader → 本部门+子部门，但排除 HR 部门成员
    - direct_leader/employee: 自己 + 下属（如果下属在 HR 部门，仍然看不到，除非自己是 HR 部门 Leader）
    """
    role = current.role

    # 超管：全局
    if role == "super_admin":
        return None

    hr_member_ids = _hr_dept_member_ids(session)
    hr_dept_ids = _get_hr_dept_ids(session)

    # 当前用户自己是否属于 HR 部门
    is_in_hr_dept = current.department_id is not None and current.department_id in hr_dept_ids
    # 当前用户是否是 HR 部门的 Leader（可看 HR 部门数据的唯一非超管角色）
    is_hr_dept_leader = (
        role == "dept_leader" and is_in_hr_dept
    )

    # HR 部门 Leader：全局可见（含 HR 部门自己）——等同超管的数据范围
    if is_hr_dept_leader:
        return None

    if role == "hrbp":
        scope = current.hrbp_scope_dept_ids
        if not scope:
            # 全局 HR → 看到所有人，但排除 HR 部门成员（利益回避）
            all_ids = set(session.exec(select(User.id).where(User.status == "active")).all())
            # 自己也排除在"能看别人"里（自己的数据自己通过 /mine 接口看）
            # 但保留自己的 id（用于 /mine 接口能返回数据）
            result = all_ids - hr_member_ids
            # 加回自己（HRBP 至少能看到自己的周期/结果）
            if current.id is not None:
                result.add(current.id)
            return result
        # 受限 HR → 管辖范围内的人，同样排除 HR 部门成员
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

    # 部门 Leader
    if role == "dept_leader" and current.department_id is not None:
        dept_ids = _descendant_dept_ids(session, current.department_id)
        dept_members = session.exec(
            select(User.id).where(User.department_id.in_(dept_ids))
        ).all()
        visible.update(dept_members)
        # 如果不是 HR 部门 Leader，则排除 HR 部门成员
        if not is_hr_dept_leader:
            visible -= hr_member_ids
            # 但保留自己
            if current.id is not None:
                visible.add(current.id)

    # 任何有下属的人都能看下属
    subordinates = session.exec(
        select(User.id).where(User.leader_userid == current.wecom_userid)
    ).all()
    sub_set = set(subordinates)
    # 如果不是 HR 部门 Leader/超管，则排除在 HR 部门的下属
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
