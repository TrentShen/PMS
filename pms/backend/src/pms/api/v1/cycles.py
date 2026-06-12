from __future__ import annotations

# 绩效周期管理
# HR 端：创建周期、加参与人、发布结果、总览
# 员工端：列出自己参与的周期、我的待办
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from pms.database.models.cycle import CycleParticipant, PerformanceCycle
from pms.database.models.enums import ParticipantStatus
from pms.database.models.user import Department, User
from pms.database.session import get_session
from pms.services.auth import get_current_user, require_role
from pms.utils.audit import write_audit

router = APIRouter(prefix="/cycles", tags=["cycles"])


# ============ 请求/响应 Schema ============

class CycleCreate(BaseModel):
    name: str
    start_date: date
    end_date: date
    # 考核模式开关（PRD 3.2.1）
    enable_self_eval: bool = True
    enable_peer_eval: bool = True
    enable_calibration: bool = True
    enable_feedback: bool = True
    # 考核对象排除规则（PRD 3.2.2）
    exclusion_rules: dict[str, Any] | None = None


class CycleUpdate(BaseModel):
    name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    enable_self_eval: bool | None = None
    enable_peer_eval: bool | None = None
    enable_calibration: bool | None = None
    enable_feedback: bool | None = None
    exclusion_rules: dict[str, Any] | None = None


class ParticipantAdd(BaseModel):
    user_ids: list[int]


class ParticipantFilter(BaseModel):
    # 考核对象自动过滤规则（PRD 3.2.2）
    # 所有字段可选；不传=不过滤
    exclude_roles: list[str] | None = None       # 排除角色（如 ["super_admin"]）
    exclude_user_ids: list[int] | None = None    # 排除指定人员
    exclude_dept_ids: list[int] | None = None    # 排除整个部门
    exclude_levels: list[str] | None = None      # 排除职级（如 ["M4","M5"] 排除高管）
    min_hired_before: date | None = None         # 入职日期门槛：不晚于此日期


class CycleBrief(BaseModel):
    id: int
    name: str
    start_date: date
    end_date: date
    status: str
    created_by: str
    created_at: datetime
    published_at: datetime | None


class ParticipantDetail(BaseModel):
    id: int
    cycle_id: int
    user_id: int
    user_name: str
    user_position: str | None
    leader_userid_snapshot: str | None
    dept_name_snapshot: str | None
    status: str
    final_perf_score: float | None
    final_perf_level: str | None
    final_value_belief: str | None
    final_value_team: str | None
    final_value_growth: str | None


# ============ HR：列出/创建/发布 周期 ============

@router.get("", response_model=list[CycleBrief])
def list_cycles(
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
) -> list[CycleBrief]:
    # 可见规则：
    #   - 有 HR 权限（hrbp/super_admin/HR 部门 Leader）：看到所有周期（含草稿）
    #   - 其他人：只看自己作为参与人的周期
    from pms.services.auth import is_hr_dept_leader

    q = select(PerformanceCycle).order_by(PerformanceCycle.id.desc())

    has_hr = current.role in ("hrbp", "super_admin") or is_hr_dept_leader(current, session)
    if not has_hr:
        # 普通员工/Leader：只看有自己参与的周期
        my_cycle_ids = session.exec(
            select(CycleParticipant.cycle_id).where(CycleParticipant.user_id == current.id).distinct()
        ).all()
        if not my_cycle_ids:
            return []
        q = q.where(PerformanceCycle.id.in_(my_cycle_ids))

    cycles = session.exec(q).all()
    return [CycleBrief.model_validate(c, from_attributes=True) for c in cycles]


@router.post("", response_model=CycleBrief)
def create_cycle(
    payload: CycleCreate,
    session: Session = Depends(get_session),
    hr: User = Depends(require_role("hrbp", "super_admin")),
) -> CycleBrief:
    if payload.end_date <= payload.start_date:
        raise HTTPException(status_code=400, detail="结束日期必须晚于开始日期")
    cycle = PerformanceCycle(
        name=payload.name,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status="draft",
        enable_self_eval=payload.enable_self_eval,
        enable_peer_eval=payload.enable_peer_eval,
        enable_calibration=payload.enable_calibration,
        enable_feedback=payload.enable_feedback,
        created_by=hr.wecom_userid,
    )
    session.add(cycle)
    session.commit()
    session.refresh(cycle)
    write_audit(
        session,
        operator_userid=hr.wecom_userid,
        operator_name=hr.name,
        action="create_cycle",
        resource_type="performance_cycle",
        resource_id=str(cycle.id),
        after={"name": cycle.name, "status": cycle.status},
    )
    session.commit()
    return CycleBrief.model_validate(cycle, from_attributes=True)


@router.post("/{cycle_id}/start", response_model=CycleBrief)
def start_cycle(
    cycle_id: int,
    session: Session = Depends(get_session),
    hr: User = Depends(require_role("hrbp", "super_admin")),
) -> CycleBrief:
    # draft -> in_progress：启动后员工可以开始自评
    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="周期不存在")
    if cycle.status != "draft":
        raise HTTPException(status_code=400, detail=f"当前状态 {cycle.status}，不能启动")
    # 至少有 1 位参与人才能启动
    count = session.exec(
        select(CycleParticipant).where(CycleParticipant.cycle_id == cycle_id)
    ).all()
    if not count:
        raise HTTPException(status_code=400, detail="请先添加参与人")
    before = {"status": cycle.status}
    cycle.status = "in_progress"
    session.add(cycle)
    write_audit(
        session,
        operator_userid=hr.wecom_userid,
        operator_name=hr.name,
        action="start_cycle",
        resource_type="performance_cycle",
        resource_id=str(cycle.id),
        before=before,
        after={"status": cycle.status},
    )
    session.commit()
    session.refresh(cycle)
    return CycleBrief.model_validate(cycle, from_attributes=True)


@router.post("/{cycle_id}/publish", response_model=CycleBrief)
def publish_cycle(
    cycle_id: int,
    session: Session = Depends(get_session),
    hr: User = Depends(require_role("hrbp", "super_admin")),
) -> CycleBrief:
    # in_progress -> published：校准审批通过后才能发布
    from pms.database.models.calibration import CycleApproval

    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="周期不存在")
    if cycle.status != "in_progress":
        raise HTTPException(status_code=400, detail=f"当前状态 {cycle.status}，不能发布")

    # 必须通过校准审批流程才能发布
    approval = session.exec(
        select(CycleApproval).where(CycleApproval.cycle_id == cycle_id)
    ).first()
    if not approval or approval.status != "approved":
        raise HTTPException(
            status_code=400,
            detail="必须完成校准审批（HR→CEO 批准）后才能发布结果",
        )

    participants = session.exec(
        select(CycleParticipant).where(CycleParticipant.cycle_id == cycle_id)
    ).all()
    unfinished = [p for p in participants if p.final_perf_score is None]
    if unfinished:
        names = [session.get(User, p.user_id).name for p in unfinished]
        raise HTTPException(
            status_code=400,
            detail=f"尚有 {len(unfinished)} 人未确定最终评分：{', '.join(names)}",
        )

    # 校准后 final_* 已经有值了，只需把状态改为 published
    for p in participants:
        p.status = ParticipantStatus.PUBLISHED.value
        session.add(p)

    cycle.status = "published"
    cycle.published_at = datetime.now(timezone.utc)
    session.add(cycle)
    write_audit(
        session,
        operator_userid=hr.wecom_userid,
        operator_name=hr.name,
        action="publish_cycle",
        resource_type="performance_cycle",
        resource_id=str(cycle.id),
        after={"status": cycle.status, "participant_count": len(participants)},
    )
    session.commit()
    session.refresh(cycle)
    return CycleBrief.model_validate(cycle, from_attributes=True)


# ============ HR：考核对象自动过滤（PRD 3.2.2）============

@router.put("/{cycle_id}", response_model=CycleBrief)
def update_cycle(
    cycle_id: int,
    payload: CycleUpdate,
    session: Session = Depends(get_session),
    hr: User = Depends(require_role("hrbp", "super_admin")),
) -> CycleBrief:
    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="周期不存在")
    if payload.name is not None:
        cycle.name = payload.name
    if payload.start_date is not None:
        cycle.start_date = payload.start_date
    if payload.end_date is not None:
        cycle.end_date = payload.end_date
    if payload.enable_self_eval is not None:
        cycle.enable_self_eval = payload.enable_self_eval
    if payload.enable_peer_eval is not None:
        cycle.enable_peer_eval = payload.enable_peer_eval
    if payload.enable_calibration is not None:
        cycle.enable_calibration = payload.enable_calibration
    if payload.enable_feedback is not None:
        cycle.enable_feedback = payload.enable_feedback
    if payload.exclusion_rules is not None:
        cycle.exclusion_rules = payload.exclusion_rules
    session.add(cycle)
    write_audit(
        session,
        operator_userid=hr.wecom_userid,
        operator_name=hr.name,
        action="update_cycle",
        resource_type="performance_cycle",
        resource_id=str(cycle.id),
        after={k: v for k, v in payload.model_dump().items() if v is not None},
    )
    session.commit()
    session.refresh(cycle)
    return CycleBrief.model_validate(cycle, from_attributes=True)


@router.post("/{cycle_id}/suggest-participants")
def suggest_participants(
    cycle_id: int,
    payload: ParticipantFilter | None = None,
    session: Session = Depends(get_session),
    hr: User = Depends(require_role("hrbp", "super_admin")),
) -> list[dict]:
    """根据过滤规则返回建议参与人列表，前端直接"一键添加"。
    若请求体字段为 None，自动使用周期上已保存的排除规则补全。"""
    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="周期不存在")

    saved = cycle.exclusion_rules or {}

    def _pick(key: str):
        from_payload = getattr(payload, key, None) if payload else None
        return from_payload if from_payload is not None else saved.get(key)

    exclude_roles = _pick("exclude_roles")
    exclude_user_ids = _pick("exclude_user_ids")
    exclude_dept_ids = _pick("exclude_dept_ids")
    exclude_levels = _pick("exclude_levels")
    min_hired_before = _pick("min_hired_before")

    q = select(User).where(User.status == "active")

    if exclude_roles:
        q = q.where(User.role.notin_(exclude_roles))
    if exclude_user_ids:
        q = q.where(User.id.notin_(exclude_user_ids))
    if exclude_dept_ids:
        q = q.where(
            (User.department_id == None) | User.department_id.notin_(exclude_dept_ids)  # noqa: E711
        )
    if exclude_levels:
        q = q.where(User.level.notin_(exclude_levels))
    if min_hired_before:
        q = q.where(User.hired_at <= min_hired_before)

    # "谁参加考核"是管理决策，不受"查看绩效"的利益回避限制
    # 仅按 hrbp_scope_dept_ids 做管辖范围限制（如果有）
    if hr.role == "hrbp" and hr.hrbp_scope_dept_ids:
        from pms.services.scope import _descendant_dept_ids
        allowed_depts: set[int] = set()
        for did in hr.hrbp_scope_dept_ids:
            allowed_depts.update(_descendant_dept_ids(session, did))
        q = q.where(User.department_id.in_(allowed_depts))

    users = session.exec(q).all()
    return [
        {"id": u.id, "name": u.name, "role": u.role, "position": u.position,
         "department_id": u.department_id, "level": u.level,
         "hired_at": u.hired_at.isoformat() if u.hired_at else None}
        for u in users
    ]


# ============ HR：参与人管理 ============

@router.get("/{cycle_id}/participants")
def list_participants(
    cycle_id: int,
    only_subordinates: bool = False,
    page: int = 1,
    page_size: int = 50,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    from pms.services.scope import visible_user_ids

    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="周期不存在")

    q = select(CycleParticipant, User).join(User, User.id == CycleParticipant.user_id).where(
        CycleParticipant.cycle_id == cycle_id
    )

    if only_subordinates:
        q = q.where(User.leader_userid == current.wecom_userid)
    else:
        scope = visible_user_ids(session, current)
        if scope is not None:
            q = q.where(CycleParticipant.user_id.in_(scope))

    rows = session.exec(q).all()
    total = len(rows)
    start = (page - 1) * page_size
    paged = rows[start:start + page_size]

    items = [
        ParticipantDetail(
            id=p.id,
            cycle_id=p.cycle_id,
            user_id=p.user_id,
            user_name=u.name,
            user_position=u.position,
            leader_userid_snapshot=p.leader_userid_snapshot,
            dept_name_snapshot=p.dept_name_snapshot,
            status=p.status,
            final_perf_score=p.final_perf_score,
            final_perf_level=p.final_perf_level,
            final_value_belief=p.final_value_belief,
            final_value_team=p.final_value_team,
            final_value_growth=p.final_value_growth,
        )
        for p, u in paged
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/{cycle_id}/participants", response_model=list[ParticipantDetail])
def add_participants(
    cycle_id: int,
    payload: ParticipantAdd,
    session: Session = Depends(get_session),
    hr: User = Depends(require_role("hrbp", "super_admin")),
) -> list[ParticipantDetail]:
    # 只能在 draft 状态加人（已启动的周期里参与人列表是冻结的）
    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="周期不存在")
    if cycle.status != "draft":
        raise HTTPException(status_code=400, detail="只能在草稿状态添加参与人")

    existing_ids = {
        p.user_id
        for p in session.exec(
            select(CycleParticipant).where(CycleParticipant.cycle_id == cycle_id)
        ).all()
    }
    added: list[CycleParticipant] = []
    for uid in payload.user_ids:
        if uid in existing_ids:
            continue
        user = session.get(User, uid)
        if not user:
            continue
        dept = session.get(Department, user.department_id) if user.department_id else None
        cp = CycleParticipant(
            cycle_id=cycle_id,
            user_id=uid,
            leader_userid_snapshot=user.leader_userid,
            dept_name_snapshot=dept.name if dept else None,
            status="pending",
        )
        session.add(cp)
        added.append(cp)

    write_audit(
        session,
        operator_userid=hr.wecom_userid,
        operator_name=hr.name,
        action="add_participants",
        resource_type="performance_cycle",
        resource_id=str(cycle_id),
        after={"added_user_ids": payload.user_ids},
    )
    session.commit()

    return list_participants(cycle_id, session=session, current=hr, page_size=9999)


# ============ 员工 / Leader：我的周期 / 我的待办 ============

@router.get("/mine", response_model=list[dict])
def my_cycles(
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
) -> list[dict]:
    from pms.database.models.feedback import FeedbackRecord

    as_self = session.exec(
        select(PerformanceCycle, CycleParticipant)
        .join(CycleParticipant, CycleParticipant.cycle_id == PerformanceCycle.id)
        .where(CycleParticipant.user_id == current.id)
        .order_by(PerformanceCycle.id.desc())
    ).all()

    # Batch-load feedback records to avoid N+1
    published_cycle_ids = [c.id for c, _ in as_self if c.status == "published"]
    fb_map: dict[int, FeedbackRecord] = {}
    if published_cycle_ids:
        fbs = session.exec(
            select(FeedbackRecord).where(
                FeedbackRecord.user_id == current.id,
                FeedbackRecord.cycle_id.in_(published_cycle_ids),
            )
        ).all()
        fb_map = {fb.cycle_id: fb for fb in fbs}

    result = []
    for c, p in as_self:
        show_final = True
        if c.status == "published":
            fb = fb_map.get(c.id)
            if not fb or fb.confirm_status == "pending":
                show_final = False

        result.append({
            "cycle": CycleBrief.model_validate(c, from_attributes=True).model_dump(mode="json"),
            "role": "participant",
            "participant_status": p.status,
            "final_perf_level": p.final_perf_level if show_final else None,
            "final_value_belief": p.final_value_belief if show_final else None,
            "final_value_team": p.final_value_team if show_final else None,
            "final_value_growth": p.final_value_growth if show_final else None,
            "final_perf_score": p.final_perf_score if show_final else None,
            "result_pending_feedback": not show_final,
        })
    return result
