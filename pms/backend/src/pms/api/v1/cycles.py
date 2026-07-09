from __future__ import annotations

# 绩效周期管理
# HR 端：创建周期、加参与人、发布结果、总览
# 员工端：列出自己参与的周期、我的待办
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from pms.database.models.calibration import CalibrationRecord, CycleApproval
from pms.database.models.cycle import CycleParticipant, PerformanceCycle
from pms.database.models.enums import ParticipantStatus
from pms.database.models.evaluation import Evaluation
from pms.database.models.feedback import FeedbackRecord
from pms.database.models.objective_cycle import ObjectiveCycle
from pms.database.models.objective_cycle_participant import ObjectiveCycleParticipant
from pms.database.models.peer import AnonymousFeedback, PeerEvaluation, PeerInvitation
from pms.database.models.user import Department, User
from pms.database.session import get_session
from pms.services.auth import get_current_user, has_any_role, is_fte, require_fte, require_role
from pms.services.notification import send_textcard_notification
from pms.utils.audit import write_audit

router = APIRouter(prefix="/cycles", tags=["cycles"])


# ============ 请求/响应 Schema ============

class CycleCreate(BaseModel):
    name: str
    start_date: date
    end_date: date
    # 关联目标周期：本评估周期评估哪个目标周期
    objective_cycle_id: int | None = None
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
    objective_cycle_id: int | None = None
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
    objective_cycle_id: int | None
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

    has_hr = has_any_role(current, "hrbp", "super_admin") or is_hr_dept_leader(current, session)
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
    if payload.objective_cycle_id:
        oc = session.get(ObjectiveCycle, payload.objective_cycle_id)
        if not oc:
            raise HTTPException(status_code=404, detail="关联的目标周期不存在")

    cycle = PerformanceCycle(
        name=payload.name,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status="draft",
        objective_cycle_id=payload.objective_cycle_id,
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

    # 通知所有参与人
    _notify_cycle_started(session, cycle)

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

    # 若开启校准，必须通过校准审批流程才能发布
    if cycle.enable_calibration:
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

    # 若开启绩效反馈，必须完成反馈闭环（每个参与人都有反馈记录且已确认/异议）
    if cycle.enable_feedback:
        from pms.database.models.feedback import FeedbackRecord

        feedback_map = {
            fb.user_id: fb
            for fb in session.exec(
                select(FeedbackRecord).where(FeedbackRecord.cycle_id == cycle_id)
            ).all()
        }
        pending_feedback = [
            p for p in participants
            if p.user_id not in feedback_map or feedback_map[p.user_id].confirm_status == "pending"
        ]
        if pending_feedback:
            names = [session.get(User, p.user_id).name for p in pending_feedback]
            raise HTTPException(
                status_code=400,
                detail=f"尚有 {len(pending_feedback)} 人未完成绩效反馈确认：{', '.join(names)}",
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

    # 通知所有参与人结果已发布
    _notify_cycle_published(session, cycle)

    return CycleBrief.model_validate(cycle, from_attributes=True)


@router.post("/{cycle_id}/close", response_model=CycleBrief)
def close_cycle(
    cycle_id: int,
    session: Session = Depends(get_session),
    hr: User = Depends(require_role("hrbp", "super_admin")),
) -> CycleBrief:
    """published -> closed：归档周期。未完成的参与人标记为 excluded，避免 closed 周期仍存在 pending。"""
    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="周期不存在")
    if cycle.status != "published":
        raise HTTPException(status_code=400, detail=f"当前状态 {cycle.status}，不能归档")

    participants = session.exec(
        select(CycleParticipant).where(CycleParticipant.cycle_id == cycle_id)
    ).all()
    closed_count = 0
    for p in participants:
        if p.status in (ParticipantStatus.PENDING.value, ParticipantStatus.SELF_DONE.value, ParticipantStatus.LEADER_DONE.value):
            p.status = ParticipantStatus.EXCLUDED.value
            session.add(p)
            closed_count += 1

    before = {"status": cycle.status}
    cycle.status = "closed"
    session.add(cycle)
    write_audit(
        session,
        operator_userid=hr.wecom_userid,
        operator_name=hr.name,
        action="close_cycle",
        resource_type="performance_cycle",
        resource_id=str(cycle.id),
        before=before,
        after={"status": cycle.status, "excluded_count": closed_count, "participant_count": len(participants)},
    )
    session.commit()
    session.refresh(cycle)
    return CycleBrief.model_validate(cycle, from_attributes=True)


@router.delete("/{cycle_id}")
def delete_cycle(
    cycle_id: int,
    session: Session = Depends(get_session),
    hr: User = Depends(require_role("hrbp", "super_admin")),
) -> dict:
    """删除草稿周期。
    只有草稿状态可删除；若周期内已存在绩效数据（评估、校准、反馈、互评等），
    禁止删除以保护历史数据。空周期仅删除参与人记录和周期本身。"""
    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="周期不存在")
    if cycle.status != "draft":
        raise HTTPException(status_code=400, detail="只能删除草稿状态的周期")

    # 绩效数据保护：若周期内已产生任何绩效相关记录，禁止删除，确保数据可找回
    perf_models = [
        ("评估", Evaluation),
        ("校准记录", CalibrationRecord),
        ("审批记录", CycleApproval),
        ("反馈", FeedbackRecord),
        ("互评邀请", PeerInvitation),
        ("互评", PeerEvaluation),
        ("匿名反馈", AnonymousFeedback),
    ]
    counts: list[str] = []
    for label, model in perf_models:
        cnt = session.exec(select(model).where(model.cycle_id == cycle_id)).all()
        if cnt:
            counts.append(f"{label} {len(cnt)} 条")
    if counts:
        raise HTTPException(
            status_code=400,
            detail=f"周期内已存在绩效数据（{', '.join(counts)}），无法删除，避免历史数据丢失",
        )

    # 仅删除空的参与人记录（CycleParticipant 本身不是绩效数据）
    for cp in session.exec(select(CycleParticipant).where(CycleParticipant.cycle_id == cycle_id)).all():
        session.delete(cp)

    session.delete(cycle)
    write_audit(
        session,
        operator_userid=hr.wecom_userid,
        operator_name=hr.name,
        action="delete_cycle",
        resource_type="performance_cycle",
        resource_id=str(cycle_id),
        before={"name": cycle.name, "status": cycle.status},
    )
    session.commit()
    return {"status": "ok"}


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
    if payload.objective_cycle_id is not None:
        oc = session.get(ObjectiveCycle, payload.objective_cycle_id)
        if not oc:
            raise HTTPException(status_code=404, detail="关联的目标周期不存在")
        cycle.objective_cycle_id = payload.objective_cycle_id
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

    # 绩效周期仅面向正式员工；未同步 employee_type 时视为非 full_time，不纳入
    q = select(User).where(User.status == "active", User.employee_type == "full_time")

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
        if not has_any_role(current, "direct_leader", "dept_leader", "hrbp", "super_admin"):
            raise HTTPException(status_code=403, detail="无权限查看下属列表")
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
        # 仅正式员工（full_time）可参与绩效周期；未同步 employee_type 的不放行
        if user.employee_type != "full_time":
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

    return [
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
        for p, u in (
            (p, session.get(User, p.user_id))
            for p in added
        )
        if u
    ]


@router.delete("/{cycle_id}/participants/{participant_id}")
def delete_participant(
    cycle_id: int,
    participant_id: int,
    session: Session = Depends(get_session),
    hr: User = Depends(require_role("hrbp", "super_admin")),
) -> dict:
    """草稿状态下删除参与人；启动后不能删除。"""
    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="周期不存在")
    if cycle.status != "draft":
        raise HTTPException(status_code=400, detail="只能在草稿状态删除参与人")

    participant = session.get(CycleParticipant, participant_id)
    if not participant or participant.cycle_id != cycle_id:
        raise HTTPException(status_code=404, detail="参与人不存在")

    user_id = participant.user_id
    has_perf_data = any(
        session.exec(
            select(model).where(
                model.cycle_id == cycle_id,
                getattr(model, field) == user_id,
            )
        ).first()
        for model, field in (
            (Evaluation, "user_id"),
            (CalibrationRecord, "user_id"),
            (FeedbackRecord, "user_id"),
            (PeerInvitation, "invitee_user_id"),
            (PeerEvaluation, "target_user_id"),
            (PeerEvaluation, "evaluator_user_id"),
            (AnonymousFeedback, "target_user_id"),
            (AnonymousFeedback, "author_user_id"),
        )
    )
    if has_perf_data:
        raise HTTPException(
            status_code=400,
            detail="该参与人已产生绩效数据，无法删除；如需移除请联系管理员归档",
        )

    session.delete(participant)
    write_audit(
        session,
        operator_userid=hr.wecom_userid,
        operator_name=hr.name,
        action="delete_participant",
        resource_type="performance_cycle",
        resource_id=str(cycle_id),
        before={"participant_id": participant.id, "user_id": participant.user_id},
    )
    session.commit()
    return {"status": "ok"}


# ============ 员工 / Leader：我的周期 / 我的待办 ============

@router.get("/mine", response_model=list[dict])
def my_cycles(
    session: Session = Depends(get_session),
    current: User = Depends(require_fte),
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


def _notify_cycle_started(session: Session, cycle: PerformanceCycle) -> None:
    """周期启动后通知所有参与人（仅通知 FTE）。"""
    rows = session.exec(
        select(User)
        .join(CycleParticipant, CycleParticipant.user_id == User.id)
        .where(CycleParticipant.cycle_id == cycle.id, User.status == "active")
    ).all()
    rows = [u for u in rows if is_fte(u)]
    if not rows:
        return
    send_textcard_notification(
        target_userids=list(rows),
        title="绩效周期已启动",
        description=f"「{cycle.name}」已启动，请尽快完成自评。",
        url=f"/cycles/{cycle.id}/self-eval",
        payload={"cycle_id": cycle.id, "event": "cycle_started"},
    )


def _notify_cycle_published(session: Session, cycle: PerformanceCycle) -> None:
    """周期结果发布后通知所有参与人（仅通知 FTE）。"""
    rows = session.exec(
        select(User)
        .join(CycleParticipant, CycleParticipant.user_id == User.id)
        .where(CycleParticipant.cycle_id == cycle.id, User.status == "active")
    ).all()
    rows = [u for u in rows if is_fte(u)]
    if not rows:
        return
    send_textcard_notification(
        target_userids=list(rows),
        title="绩效结果已发布",
        description=f"「{cycle.name}」绩效结果已发布，请查看并确认反馈。",
        url=f"/cycles/{cycle.id}/result",
        payload={"cycle_id": cycle.id, "event": "cycle_published"},
    )


# ============ HR 看板：周期进度仪表盘 ============

@router.get("/{cycle_id}/dashboard")
def cycle_dashboard(
    cycle_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(require_role("hrbp", "super_admin")),
):
    """返回某个绩效周期的整体进度看板数据，供 HR 监控各环节完成情况。"""
    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="周期不存在")

    # 评估参与人
    perf_participants = session.exec(
        select(CycleParticipant).where(CycleParticipant.cycle_id == cycle_id)
    ).all()
    perf_user_ids = [p.user_id for p in perf_participants]

    # 目标参与人（来自关联目标周期）
    objective_participant_count = 0
    objective_user_ids: list[int] = []
    if cycle.objective_cycle_id:
        oc_participants = session.exec(
            select(ObjectiveCycleParticipant).where(
                ObjectiveCycleParticipant.objective_cycle_id == cycle.objective_cycle_id
            )
        ).all()
        objective_participant_count = len(oc_participants)
        objective_user_ids = [p.user_id for p in oc_participants]

    # 自评完成数
    self_eval_submitted = 0
    if perf_user_ids:
        self_eval_submitted = len(session.exec(
            select(Evaluation).where(
                Evaluation.cycle_id == cycle_id,
                Evaluation.user_id.in_(perf_user_ids),
                Evaluation.eval_type == "self",
                Evaluation.status == "submitted",
            )
        ).all())

    # 上级评估完成数
    superior_eval_submitted = 0
    if perf_user_ids:
        superior_eval_submitted = len(session.exec(
            select(Evaluation).where(
                Evaluation.cycle_id == cycle_id,
                Evaluation.user_id.in_(perf_user_ids),
                Evaluation.eval_type == "superior",
                Evaluation.status == "submitted",
            )
        ).all())

    # 互评名单确认数：已批准（approved）的互评邀请数
    peer_approved_count = 0
    if perf_user_ids:
        peer_approved_count = len(session.exec(
            select(PeerInvitation).where(
                PeerInvitation.cycle_id == cycle_id,
                PeerInvitation.invitee_user_id.in_(perf_user_ids),
                PeerInvitation.status == "approved",
            )
        ).all())

    # 互评完成数：已提交的正式互评任务数
    peer_eval_submitted = 0
    if perf_user_ids:
        peer_eval_submitted = len(session.exec(
            select(PeerEvaluation).where(
                PeerEvaluation.cycle_id == cycle_id,
                PeerEvaluation.target_user_id.in_(perf_user_ids),
                PeerEvaluation.status == "submitted",
            )
        ).all())

    # 按部门统计：自评完成进度 + 互评完成进度
    dept_self_progress: list[dict] = []
    dept_peer_progress: list[dict] = []

    if perf_user_ids:
        # 批量加载用户和部门
        users = session.exec(select(User).where(User.id.in_(perf_user_ids))).all()
        user_map = {u.id: u for u in users}
        dept_ids = {u.department_id for u in users if u.department_id}
        depts = session.exec(select(Department).where(Department.id.in_(dept_ids))).all() if dept_ids else []
        dept_map = {d.id: d.name for d in depts}

        # 自评提交用户
        self_submitted_user_ids = {
            e.user_id for e in session.exec(
                select(Evaluation).where(
                    Evaluation.cycle_id == cycle_id,
                    Evaluation.user_id.in_(perf_user_ids),
                    Evaluation.eval_type == "self",
                    Evaluation.status == "submitted",
                )
            ).all()
        }

        # 互评完成用户（所有正式互评任务都已提交的被评人）
        peer_evals = session.exec(
            select(PeerEvaluation).where(
                PeerEvaluation.cycle_id == cycle_id,
                PeerEvaluation.target_user_id.in_(perf_user_ids),
            )
        ).all()
        peer_target_total: dict[int, int] = {}
        peer_target_submitted: dict[int, int] = {}
        for ev in peer_evals:
            peer_target_total[ev.target_user_id] = peer_target_total.get(ev.target_user_id, 0) + 1
            if ev.status == "submitted":
                peer_target_submitted[ev.target_user_id] = peer_target_submitted.get(ev.target_user_id, 0) + 1
        peer_done_user_ids = {
            uid for uid in peer_target_total
            if peer_target_submitted.get(uid, 0) >= peer_target_total[uid]
        }

        # 聚合
        dept_perf_count: dict[int, int] = {}
        dept_self_done: dict[int, int] = {}
        dept_peer_done: dict[int, int] = {}
        for p in perf_participants:
            u = user_map.get(p.user_id)
            if not u or not u.department_id:
                continue
            did = u.department_id
            dept_perf_count[did] = dept_perf_count.get(did, 0) + 1
            if p.user_id in self_submitted_user_ids:
                dept_self_done[did] = dept_self_done.get(did, 0) + 1
            if p.user_id in peer_done_user_ids:
                dept_peer_done[did] = dept_peer_done.get(did, 0) + 1

        dept_self_progress = [
            {
                "department_id": did,
                "department_name": dept_map.get(did, "未知部门"),
                "total": total,
                "done": dept_self_done.get(did, 0),
                "undone": total - dept_self_done.get(did, 0),
            }
            for did, total in dept_perf_count.items()
        ]
        dept_peer_progress = [
            {
                "department_id": did,
                "department_name": dept_map.get(did, "未知部门"),
                "total": total,
                "done": dept_peer_done.get(did, 0),
                "undone": total - dept_peer_done.get(did, 0),
            }
            for did, total in dept_perf_count.items()
        ]

    return {
        "cycle": CycleBrief.model_validate(cycle, from_attributes=True).model_dump(mode="json"),
        "objective_cycle_participant_count": objective_participant_count,
        "performance_participant_count": len(perf_participants),
        "self_eval_done": self_eval_submitted,
        "self_eval_total": len(perf_participants),
        "peer_list_confirmed": peer_approved_count,
        "peer_eval_done": peer_eval_submitted,
        "superior_eval_done": superior_eval_submitted,
        "superior_eval_total": len(perf_participants),
        "self_eval_progress_by_department": dept_self_progress,
        "peer_eval_progress_by_department": dept_peer_progress,
    }
