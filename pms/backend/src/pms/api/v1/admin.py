from __future__ import annotations

# 超级管理员专属：用户与部门管理
# 仅 role=super_admin 可访问；HR 不行（HR 自己就是被管理对象）
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from pms.database.models.user import Department, User
from pms.database.session import get_session
from pms.services.auth import require_role
from pms.utils.audit import write_audit

router = APIRouter(prefix="/admin", tags=["admin"])


# ============ Schema ============

class AdminUserView(BaseModel):
    id: int
    wecom_userid: str
    name: str
    role: str
    position: str | None
    leader_userid: str | None
    department_id: int | None
    hrbp_scope_dept_ids: list[int] | None
    status: str


class AdminUserPatch(BaseModel):
    # 全字段可选；超管可单独改任一字段
    role: str | None = None
    leader_userid: str | None = None
    department_id: int | None = None
    # 注意：空列表 [] 表示"无范围=看不到任何人"；None 表示"全局"
    # 前端传值时两者必须区分
    hrbp_scope_dept_ids: list[int] | None = None
    status: str | None = None
    # 要把 hrbp_scope_dept_ids 显式清空（改为全局），用 clear_scope=true
    clear_scope: bool = False


class DepartmentView(BaseModel):
    id: int
    wecom_dept_id: int
    name: str
    parent_id: int | None
    leader_userid: str | None


ALLOWED_ROLES = {"super_admin", "hrbp", "dept_leader", "direct_leader", "employee"}


# ============ 用户 ============

@router.get("/users", response_model=list[AdminUserView])
def list_users(
    session: Session = Depends(get_session),
    _admin: User = Depends(require_role("super_admin", "hrbp")),
) -> list[AdminUserView]:
    users = session.exec(select(User).order_by(User.id)).all()
    return [AdminUserView.model_validate(u, from_attributes=True) for u in users]


@router.patch("/users/{user_id}", response_model=AdminUserView)
def patch_user(
    user_id: int,
    payload: AdminUserPatch,
    session: Session = Depends(get_session),
    admin: User = Depends(require_role("super_admin", "hrbp")),
) -> AdminUserView:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 留痕用的"改动前"快照
    before = {
        "role": user.role,
        "leader_userid": user.leader_userid,
        "department_id": user.department_id,
        "hrbp_scope_dept_ids": user.hrbp_scope_dept_ids,
        "status": user.status,
    }

    # 角色校验
    if payload.role is not None:
        if payload.role not in ALLOWED_ROLES:
            raise HTTPException(status_code=400, detail=f"非法角色：{payload.role}")
        user.role = payload.role

    if payload.leader_userid is not None:
        # 空串视为清空
        user.leader_userid = payload.leader_userid.strip() or None

    if payload.department_id is not None:
        if payload.department_id == 0:
            user.department_id = None
        else:
            dept = session.get(Department, payload.department_id)
            if not dept:
                raise HTTPException(status_code=400, detail="部门不存在")
            user.department_id = payload.department_id

    # 管辖范围：三种意图
    #   1) 传 clear_scope=true -> 设 None（全局）
    #   2) 传 hrbp_scope_dept_ids=[1,2] -> 设为这两个部门
    #   3) 什么都不传 -> 不改
    if payload.clear_scope:
        user.hrbp_scope_dept_ids = None
    elif payload.hrbp_scope_dept_ids is not None:
        # 校验部门都存在
        if payload.hrbp_scope_dept_ids:
            found = session.exec(
                select(Department.id).where(Department.id.in_(payload.hrbp_scope_dept_ids))
            ).all()
            missing = set(payload.hrbp_scope_dept_ids) - set(found)
            if missing:
                raise HTTPException(status_code=400, detail=f"部门不存在：{missing}")
        user.hrbp_scope_dept_ids = payload.hrbp_scope_dept_ids

    if payload.status is not None:
        if payload.status not in ("active", "inactive"):
            raise HTTPException(status_code=400, detail="status 只能是 active/inactive")
        user.status = payload.status

    session.add(user)

    after = {
        "role": user.role,
        "leader_userid": user.leader_userid,
        "department_id": user.department_id,
        "hrbp_scope_dept_ids": user.hrbp_scope_dept_ids,
        "status": user.status,
    }
    write_audit(
        session,
        operator_userid=admin.wecom_userid,
        operator_name=admin.name,
        action="patch_user",
        resource_type="user",
        resource_id=str(user_id),
        before=before,
        after=after,
    )
    session.commit()
    session.refresh(user)
    return AdminUserView.model_validate(user, from_attributes=True)


# ============ 部门 ============

@router.get("/departments", response_model=list[DepartmentView])
def list_departments(
    session: Session = Depends(get_session),
    _admin: User = Depends(require_role("super_admin", "hrbp")),
) -> list[DepartmentView]:
    depts = session.exec(select(Department).order_by(Department.id)).all()
    return [DepartmentView.model_validate(d, from_attributes=True) for d in depts]
