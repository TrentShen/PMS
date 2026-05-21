# 认证接口：mock 登录（开发用）+ 企微 OAuth 免登（生产）
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from loguru import logger
from pydantic import BaseModel
from sqlmodel import Session, select

from pms.configs import settings
from pms.database.models.user import User
from pms.database.session import get_session
from pms.services.auth import get_current_user, is_hr_dept_leader, sign_token
from pms.services.wecom import get_userinfo

router = APIRouter(prefix="/auth", tags=["auth"])


class MockLoginRequest(BaseModel):
    wecom_userid: str


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
    has_hr_permission: bool = False
    has_subordinates: bool = False


def _build_user_response(user: User, session: Session) -> dict:
    hr_perm = user.role in ("hrbp", "super_admin") or is_hr_dept_leader(user, session)
    has_subs = session.exec(
        select(User.id).where(User.leader_userid == user.wecom_userid).limit(1)
    ).first() is not None
    return {
        "id": user.id,
        "wecom_userid": user.wecom_userid,
        "name": user.name,
        "role": user.role,
        "position": user.position,
        "leader_userid": user.leader_userid,
        "has_hr_permission": hr_perm,
        "has_subordinates": has_subs,
    }


# ---------- 开发用 mock 登录 ----------

@router.get("/mock-users")
def list_mock_users(session: Session = Depends(get_session)) -> list[dict]:
    users = session.exec(select(User).where(User.status == "active")).all()
    return [
        {"id": u.id, "wecom_userid": u.wecom_userid, "name": u.name, "role": u.role, "position": u.position}
        for u in users
    ]


@router.post("/mock-login", response_model=TokenResponse)
def mock_login(payload: MockLoginRequest, session: Session = Depends(get_session)) -> TokenResponse:
    user = session.exec(select(User).where(User.wecom_userid == payload.wecom_userid)).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    token = sign_token(user.wecom_userid)
    return TokenResponse(token=token, user=_build_user_response(user, session))


# ---------- 登录页入口：根据是否企微环境分流 ----------

@router.get("/entry")
def auth_entry(is_wecom: bool = Query(default=True)):
    """前端判断环境后调用：在企微内重定向到 OAuth 授权页，否则跳 mock 登录页"""
    if not is_wecom:
        return {"redirect": "/login", "note": "非企微环境，走 mock 登录"}
    params = {
        "appid": settings.wecom_corpid,
        "redirect_uri": settings.wecom_redirect_uri,
        "response_type": "code",
        "scope": "snsapi_base",
        "state": "login",
    }
    oauth_url = f"https://open.weixin.qq.com/connect/oauth2/authorize?{urlencode(params)}#wechat_redirect"
    return {"redirect": oauth_url}


# ---------- 企微 OAuth 回调 ----------

@router.get("/callback")
def wecom_callback(code: str, session: Session = Depends(get_session)):
    """企微 OAuth 回调：code 换 userid → 匹配本地用户 → 签发 JWT → 返回 token"""
    if not code:
        raise HTTPException(status_code=400, detail="missing code")

    # code 换企微 userid
    try:
        wecom_userid = get_userinfo(code)
    except Exception as e:
        logger.error("code 换 userid 失败: {}", e)
        raise HTTPException(status_code=401, detail="企微认证失败") from e

    # 匹配本地用户
    user = session.exec(select(User).where(User.wecom_userid == wecom_userid)).first()
    if not user:
        # 用户尚未同步到本地——自动注册
        logger.warning("企微用户 {} 不在本地库，自动注册", wecom_userid)
        user = User(
            wecom_userid=wecom_userid,
            name=wecom_userid,  # 临时用 userid 当名字，通讯录同步后会更新
            role="employee",
            status="active",
        )
        session.add(user)
        session.commit()
        session.refresh(user)

    if user.status != "active":
        raise HTTPException(status_code=403, detail="账号已停用")

    token = sign_token(user.wecom_userid)
    user_info = _build_user_response(user, session)
    return TokenResponse(token=token, user=user_info)


# ---------- 当前用户 ----------

@router.get("/me", response_model=CurrentUser)
def me(current: User = Depends(get_current_user), session: Session = Depends(get_session)) -> CurrentUser:
    hr_perm = current.role in ("hrbp", "super_admin") or is_hr_dept_leader(current, session)
    has_subs = session.exec(
        select(User.id).where(User.leader_userid == current.wecom_userid).limit(1)
    ).first() is not None
    return CurrentUser(
        id=current.id,
        wecom_userid=current.wecom_userid,
        name=current.name,
        role=current.role,
        position=current.position,
        leader_userid=current.leader_userid,
        has_hr_permission=hr_perm,
        has_subordinates=has_subs,
    )
