# 用户列表（HR 建周期时需要选人）
# HR 管辖范围生效：限定只能选到自己管辖范围内的员工
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from pms.database.models.user import User
from pms.database.session import get_session
from pms.services.auth import require_role
from pms.services.scope import visible_user_ids

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
