# 认证接口
# V0.9 提供 mock-login 走本地用户表；Sprint 1 接入企微 OAuth 后新增 /callback 真实签发
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from pms.database.models.user import User
from pms.database.session import get_session
from pms.services.auth import get_current_user, is_hr_dept_leader, sign_token

router = APIRouter(prefix="/auth", tags=["auth"])


class MockLoginRequest(BaseModel):
    wecom_userid: str  # 从前端下拉选一个身份


class TokenResponse(BaseModel):
    token: str
    user: dict


class CurrentUser(BaseModel):
    id: int
    wecom_userid: str
    name: str
    role: str
    position: str | None
    leader_userid: str | None
    # HR 部门 Leader 虽然 role=dept_leader，但享有 HR 权限；前端用这个字段决定菜单显示
    has_hr_permission: bool = False


@router.get("/mock-users")
def list_mock_users(session: Session = Depends(get_session)) -> list[dict]:
    # 登录页用：列出所有可选的"假身份"，便于切角色测试
    # 前端互评候选人选择也会复用本接口（需要 id）
    users = session.exec(select(User).where(User.status == "active")).all()
    return [
        {
            "id": u.id,
            "wecom_userid": u.wecom_userid,
            "name": u.name,
            "role": u.role,
            "position": u.position,
        }
        for u in users
    ]


@router.post("/mock-login", response_model=TokenResponse)
def mock_login(
    payload: MockLoginRequest,
    session: Session = Depends(get_session),
) -> TokenResponse:
    # 按 wecom_userid 找用户并签发 JWT
    user = session.exec(
        select(User).where(User.wecom_userid == payload.wecom_userid)
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    token = sign_token(user.wecom_userid)
    hr_perm = user.role in ("hrbp", "super_admin") or is_hr_dept_leader(user, session)
    return TokenResponse(
        token=token,
        user={
            "id": user.id,
            "wecom_userid": user.wecom_userid,
            "name": user.name,
            "role": user.role,
            "position": user.position,
            "leader_userid": user.leader_userid,
            "has_hr_permission": hr_perm,
        },
    )


@router.get("/me", response_model=CurrentUser)
def me(current: User = Depends(get_current_user), session: Session = Depends(get_session)) -> CurrentUser:
    hr_perm = current.role in ("hrbp", "super_admin") or is_hr_dept_leader(current, session)
    return CurrentUser(
        id=current.id,
        wecom_userid=current.wecom_userid,
        name=current.name,
        role=current.role,
        position=current.position,
        leader_userid=current.leader_userid,
        has_hr_permission=hr_perm,
    )


# Sprint 1 待实现：企微 OAuth 回调
@router.get("/callback")
def wecom_callback(code: str) -> dict:
    if not code:
        raise HTTPException(status_code=400, detail="missing code")
    return {"code": code, "message": "企微 OAuth 将在 Sprint 1 实现"}
