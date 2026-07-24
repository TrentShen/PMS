from __future__ import annotations

# 认证接口：mock 登录（开发用）+ 企微 OAuth 免登（生产）
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel
from sqlmodel import Session, select

from pms.configs import settings
from pms.database.models.cycle import CycleParticipant, PerformanceCycle
from pms.database.models.objective import Objective
from pms.database.models.objective_cycle import ObjectiveCycle
from pms.database.models.user import User
from pms.database.session import get_session
from pms.services.auth import get_current_user, is_hr_dept_leader, sign_token
from pms.services.wecom import get_user_detail, get_userinfo

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
    role: str  # 当前生效角色（可能通过 switch-role 切换）
    base_role: str  # 数据库原始角色，决定用户固有哪些权限
    position: str | None
    leader_userid: str | None
    has_hr_permission: bool = False
    has_subordinates: bool = False
    switchable_roles: list[str] = []  # 仅 super_admin 返回可切换角色列表


ALLOWED_ROLES = ["super_admin", "hrbp", "dept_leader", "direct_leader", "employee"]


def _build_user_response(user: User, session: Session, effective_role: str | None = None) -> dict:
    base_role = getattr(user, "base_role", None) or user.role
    role = effective_role or user.role
    hr_perm = role in ("hrbp", "super_admin") or is_hr_dept_leader(user, session)
    has_subs = session.exec(
        select(User.id).where(User.leader_userid == user.wecom_userid).limit(1)
    ).first() is not None
    result = {
        "id": user.id,
        "wecom_userid": user.wecom_userid,
        "name": user.name,
        "role": role,
        "base_role": base_role,
        "position": user.position,
        "leader_userid": user.leader_userid,
        "has_hr_permission": hr_perm,
        "has_subordinates": has_subs,
    }
    # super_admin 始终显示可切换角色（即使当前生效角色不是 super_admin）
    if base_role == "super_admin":
        result["switchable_roles"] = ALLOWED_ROLES
    return result


# ---------- 开发用 mock 登录（生产环境禁用） ----------

_PROD_ENV = settings.app_env == "prod"


@router.get("/mock-users")
def list_mock_users(session: Session = Depends(get_session)) -> list[dict]:
    if _PROD_ENV:
        raise HTTPException(status_code=404, detail="Not Found")
    users = session.exec(select(User).where(User.status == "active")).all()
    return [
        {"id": u.id, "wecom_userid": u.wecom_userid, "name": u.name, "role": u.role, "position": u.position}
        for u in users
    ]


@router.post("/mock-login", response_model=TokenResponse)
def mock_login(payload: MockLoginRequest, session: Session = Depends(get_session)) -> TokenResponse:
    if _PROD_ENV:
        raise HTTPException(status_code=404, detail="Not Found")
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
        # 用户尚未同步到本地——自动注册，并尝试从企微拉取详情
        logger.warning("企微用户 {} 不在本地库，自动注册", wecom_userid)
        user = User(
            wecom_userid=wecom_userid,
            name=wecom_userid,
            role="employee",
            status="active",
        )
        _fill_user_basic_from_wecom(session, user)
        session.add(user)
        session.commit()
        session.refresh(user)
    elif not user.name or user.name == wecom_userid:
        # 已存在但信息不完整（如之前只存了 userid），登录时顺手补齐基础信息
        _fill_user_basic_from_wecom(session, user)
        session.add(user)
        session.commit()
        session.refresh(user)

    if user.status != "active":
        raise HTTPException(status_code=403, detail="账号已停用")

    token = sign_token(user.wecom_userid)
    user_info = _build_user_response(user, session)
    return TokenResponse(token=token, user=user_info)


def _fill_user_basic_from_wecom(session: Session, user: User) -> None:
    """从企微通讯录补全用户基础信息（登录时使用，不阻塞、不调用人事助手）"""
    from pms.database.models.user import Department

    try:
        detail = get_user_detail(user.wecom_userid)
        if detail.get("errcode") in (0, None):
            user.name = detail.get("name") or user.name
            user.avatar = detail.get("avatar") or user.avatar
            user.position = detail.get("position") or user.position
            user.leader_userid = detail.get("direct_leader") or user.leader_userid
            # 绑定主部门
            dept_ids = detail.get("department", [])
            if dept_ids:
                dept = session.exec(
                    select(Department).where(Department.wecom_dept_id == dept_ids[0])
                ).first()
                if dept:
                    user.department_id = dept.id
    except Exception as e:
        logger.warning("企微用户详情获取失败 [{}]: {}", user.wecom_userid, e)


class SwitchRoleRequest(BaseModel):
    role: str


# ---------- 当前用户 ----------

@router.get("/me", response_model=CurrentUser)
def me(
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CurrentUser:
    return CurrentUser.model_validate(
        _build_user_response(current, session), from_attributes=False
    )


class TaskItem(BaseModel):
    type: str
    id: int
    name: str
    status: str
    participant_status: str | None = None
    objective_status: str | None = None


@router.get("/me/tasks")
def my_tasks(
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """返回当前用户待处理的评估任务和目标制定任务"""
    # 评估任务：当前用户作为参与人的周期
    eval_tasks = []
    participants = session.exec(
        select(CycleParticipant, PerformanceCycle)
        .join(PerformanceCycle, PerformanceCycle.id == CycleParticipant.cycle_id)
        .where(
            CycleParticipant.user_id == current.id,
            PerformanceCycle.status.in_(["draft", "in_progress"]),
        )
    ).all()
    for p, c in participants:
        eval_tasks.append(TaskItem(
            type="evaluation",
            id=c.id,
            name=c.name,
            status=c.status,
            participant_status=p.status,
        ).model_dump())

    # 目标制定任务：当前用户有待处理目标的目标周期
    objective_tasks = []
    oc_ids = session.exec(
        select(Objective.objective_cycle_id)
        .where(Objective.user_id == current.id)
        .distinct()
    ).all()
    for oc_id in oc_ids:
        oc = session.get(ObjectiveCycle, oc_id)
        if not oc or oc.status not in ("draft", "active"):
            continue
        # 取该用户在该周期下的目标状态
        objs = session.exec(
            select(Objective).where(
                Objective.objective_cycle_id == oc_id,
                Objective.user_id == current.id,
            )
        ).all()
        overall = "draft"
        if any(o.status == "pending_review" for o in objs):
            overall = "pending_review"
        elif all(o.status in ("approved", "locked") for o in objs):
            overall = "approved"
        objective_tasks.append(TaskItem(
            type="objective_setting",
            id=oc.id,
            name=oc.name,
            status=oc.status,
            objective_status=overall,
        ).model_dump())

    return {"evaluations": eval_tasks, "objective_settings": objective_tasks}


@router.post("/switch-role", response_model=TokenResponse)
def switch_role(
    payload: SwitchRoleRequest,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> TokenResponse:
    """super_admin 切换当前生效角色（用于测试不同界面）"""
    base_role = getattr(current, "base_role", None) or current.role
    if base_role != "super_admin":
        raise HTTPException(status_code=403, detail="仅超级管理员可切换角色")
    if payload.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=f"不支持的角色：{payload.role}")
    token = sign_token(current.wecom_userid, active_role=payload.role)
    # 临时修改内存对象用于构建响应
    current.role = payload.role
    return TokenResponse(token=token, user=_build_user_response(current, session))
