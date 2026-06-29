from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Header, HTTPException
from sqlmodel import Session, select

from pms.configs import settings
from pms.database.models.user import User
from pms.database.session import get_session, redis_client

JWT_ALGO = "HS256"
JWT_TTL = timedelta(days=7)
USER_CACHE_TTL = 300  # 5 minutes


def sign_token(wecom_userid: str, active_role: str | None = None) -> str:
    payload = {
        "sub": wecom_userid,
        "exp": datetime.now(timezone.utc) + JWT_TTL,
        "iat": datetime.now(timezone.utc),
    }
    if active_role:
        payload["active_role"] = active_role
    return jwt.encode(payload, settings.app_secret, algorithm=JWT_ALGO)


def decode_token(token: str) -> tuple[str, str | None]:
    try:
        payload = jwt.decode(token, settings.app_secret, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status_code=401, detail="登录已过期") from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail="非法 token") from e
    userid = payload.get("sub")
    if not userid:
        raise HTTPException(status_code=401, detail="token 缺少 sub")
    return userid, payload.get("active_role")


def invalidate_user_cache(wecom_userid: str) -> None:
    redis_client.delete(f"pms:user:{wecom_userid}")


def get_current_user(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization.split(" ", 1)[1]
    wecom_userid, active_role = decode_token(token)

    # Cache stores user_id for fast PK lookup (vs. index scan on wecom_userid)
    cache_key = f"pms:user:{wecom_userid}"
    cached = redis_client.get(cache_key)
    if cached:
        data = json.loads(cached)
        if data.get("status") != "active":
            raise HTTPException(status_code=403, detail="账号已停用")
        user = session.get(User, data["id"])
        if not user:
            redis_client.delete(cache_key)
            raise HTTPException(status_code=401, detail="用户不存在")
        # 记录原始角色；super_admin 可通过 active_role 切换当前生效角色（用于测试）
        object.__setattr__(user, "base_role", user.role)
        if active_role and user.role == "super_admin":
            user.role = active_role
        return user

    user = session.exec(select(User).where(User.wecom_userid == wecom_userid)).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="账号已停用")

    # 记录原始角色；super_admin 可通过 active_role 切换当前生效角色（用于测试）
    object.__setattr__(user, "base_role", user.role)
    if active_role and user.role == "super_admin":
        user.role = active_role

    redis_client.setex(
        cache_key,
        USER_CACHE_TTL,
        json.dumps({"id": user.id, "status": user.status, "role": user.base_role}),
    )
    return user


def _effective_role(user: User) -> str:
    """返回用户当前生效角色（优先 base_role，不存在则回退 role）"""
    return getattr(user, "base_role", None) or user.role


def is_hr_dept_leader(user: User, session: Session) -> bool:
    """判断用户是否为 HR 部门的 Leader（等同于 hrbp 权限）"""
    if _effective_role(user) != "dept_leader" or user.department_id is None:
        return False
    from pms.database.models.user import Department
    dept = session.get(Department, user.department_id)
    if not dept:
        return False
    # HR 部门的判定：该部门中有 hrbp 角色的用户
    has_hrbp = session.exec(
        select(User.id).where(User.department_id == user.department_id, User.role == "hrbp").limit(1)
    ).first()
    return has_hrbp is not None


def is_fte(user: User) -> bool:
    """判断是否为全职（FTE）员工。

    以企微人事助手的 employee_type 为准；未同步到时默认放行（避免误拦截）。
    """
    return user.employee_type is None or user.employee_type == "full_time"


def require_fte(user: User = Depends(get_current_user)) -> User:
    """绩效相关接口守卫：仅允许 FTE 员工访问"""
    if not is_fte(user):
        raise HTTPException(status_code=403, detail="仅全职员工可参与绩效流程")
    return user


def has_any_role(user: User, *allowed_roles: str) -> bool:
    """判断用户当前生效角色是否命中任一允许角色。

    角色切换后，权限随当前生效角色变化，以保证测试不同角色时看到的是真实权限。
    """
    return user.role in allowed_roles


SUPERIOR_ROLES = ("direct_leader", "dept_leader", "hrbp", "super_admin")
LEADER_WRITE_ROLES = ("direct_leader", "dept_leader", "hrbp", "super_admin")


def can_act_as_superior(
    current: User,
    target: User,
    allowed_roles: tuple[str, ...] = LEADER_WRITE_ROLES,
) -> bool:
    """判断 current 是否可以对 target 执行直属上级/HR 类的写操作。

    角色切换后，current.role 为生效角色；仅当生效角色在允许列表内且满足
    汇报关系（或本身是 HR/超管）时才放行。
    """
    if current.role in ("hrbp", "super_admin"):
        return True
    if current.role not in allowed_roles:
        return False
    return target.leader_userid == current.wecom_userid


def require_superior_or_hr(
    allowed_roles: tuple[str, ...] = LEADER_WRITE_ROLES,
):
    """路由依赖：校验当前用户对目标员工拥有直属上级或 HR 写权限。

    用法：Depends(require_superior_or_hr())，然后在函数内自行查询 target 用户。
    """

    def _guard(user: User = Depends(get_current_user)) -> User:
        # 注意：target 需要调用方自行校验，这里只保证当前用户角色具备上级/HR 资质
        if user.role not in allowed_roles and user.role not in ("hrbp", "super_admin"):
            raise HTTPException(status_code=403, detail="需要直属上级或 HR 权限")
        return user

    return _guard


def require_role(*allowed_roles: str):
    # 角色守卫；用法 Depends(require_role("hrbp", "super_admin"))
    # 额外规则：HR 部门的 dept_leader 视同 hrbp 权限
    def _guard(user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> User:
        if has_any_role(user, *allowed_roles):
            return user
        # HR 部门 Leader 享有 hrbp 权限
        if "hrbp" in allowed_roles and is_hr_dept_leader(user, session):
            return user
        raise HTTPException(status_code=403, detail=f"需要角色之一：{allowed_roles}")

    return _guard
