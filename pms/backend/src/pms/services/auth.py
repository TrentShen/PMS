# JWT 签发与校验 + 依赖函数 get_current_user
# V0.9 先用 mock 登录；Sprint 1 企微 OAuth 接入后，签发 JWT 的入口换成 /auth/callback，JWT 机制复用
from datetime import datetime, timedelta

import jwt
from fastapi import Depends, Header, HTTPException
from sqlmodel import Session, select

from pms.configs import settings
from pms.database.models.user import User
from pms.database.session import get_session

JWT_ALGO = "HS256"
JWT_TTL = timedelta(days=7)


def sign_token(wecom_userid: str) -> str:
    # 只放 userid，其他信息实时查库，避免缓存不一致
    payload = {
        "sub": wecom_userid,
        "exp": datetime.utcnow() + JWT_TTL,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.app_secret, algorithm=JWT_ALGO)


def decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.app_secret, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status_code=401, detail="登录已过期") from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail="非法 token") from e
    userid = payload.get("sub")
    if not userid:
        raise HTTPException(status_code=401, detail="token 缺少 sub")
    return userid


def get_current_user(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> User:
    # 标准姿势：Authorization: Bearer <token>
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization.split(" ", 1)[1]
    wecom_userid = decode_token(token)
    user = session.exec(select(User).where(User.wecom_userid == wecom_userid)).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="账号已停用")
    return user


def is_hr_dept_leader(user: User, session: Session) -> bool:
    """判断用户是否为 HR 部门的 Leader（等同于 hrbp 权限）"""
    if user.role != "dept_leader" or user.department_id is None:
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


def require_role(*allowed_roles: str):
    # 角色守卫；用法 Depends(require_role("hrbp", "super_admin"))
    # 额外规则：HR 部门的 dept_leader 视同 hrbp 权限
    def _guard(user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> User:
        if user.role in allowed_roles:
            return user
        # HR 部门 Leader 享有 hrbp 权限
        if "hrbp" in allowed_roles and is_hr_dept_leader(user, session):
            return user
        raise HTTPException(status_code=403, detail=f"需要角色之一：{allowed_roles}")

    return _guard
