from __future__ import annotations

# 试用期管理 API
# 独立于绩效周期，覆盖：计划自动创建、目标填写/审批、上级评估/转正建议
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from pms.database.models.enums import ProbationObjectiveStatus, ProbationPlanStatus, ProbationResult
from pms.database.models.probation import ProbationObjective, ProbationPlan
from pms.database.models.user import Department, User
from pms.database.session import get_session
from pms.services.auth import get_current_user, require_role
from pms.services.notification import get_hrbp_userids, send_textcard_notification
from pms.services.scope import ensure_can_view_user, visible_user_ids
from pms.utils.audit import write_audit

router = APIRouter(prefix="/probation", tags=["probation"])

DEFAULT_PROBATION_MONTHS = 6
PENDING_EVALUATION_DAYS = 7  # 临转正前 N 天进入待评估状态


# ============ 工具函数 ============

def _add_months(d: date, months: int) -> date:
    """返回 date 加上指定月数后的日期，处理月末越界。"""
    total_months = d.month - 1 + months
    year = d.year + total_months // 12
    month = total_months % 12 + 1
    max_day = [31, 29 if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    day = min(d.day, max_day)
    return date(year, month, day)


def _is_hr(user: User) -> bool:
    return user.role in ("hrbp", "super_admin")


def _is_superior(session: Session, current: User, target: User) -> bool:
    """判断 current 是否为 target 的直属上级（或 HR 代操作）。"""
    if _is_hr(current):
        return True
    return target.leader_userid == current.wecom_userid


def _get_plan_or_404(session: Session, user_id: int) -> ProbationPlan:
    plan = session.exec(
        select(ProbationPlan).where(ProbationPlan.user_id == user_id)
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="试用期计划不存在")
    return plan


def _status_text(status: str) -> str:
    return {
        ProbationPlanStatus.DRAFT: "计划已创建，等待填写目标",
        ProbationPlanStatus.OBJECTIVE_DRAFT: "填写目标中",
        ProbationPlanStatus.OBJECTIVE_PENDING_REVIEW: "目标待审批",
        ProbationPlanStatus.IN_PROGRESS: "试用期进行中",
        ProbationPlanStatus.PENDING_EVALUATION: "临转正，待评估",
        ProbationPlanStatus.COMPLETED: "已完成",
        ProbationPlanStatus.EXTENDED: "已延期",
    }.get(status, status)


def _result_text(result: str | None) -> str:
    return {
        ProbationResult.REGULAR: "建议转正",
        ProbationResult.ELIMINATE: "建议淘汰",
        ProbationResult.PENDING_OTHER: "待定/其他",
    }.get(result, result or "-")


def _ensure_can_write_objectives(session: Session, current: User, target: User) -> None:
    """员工只能写自己的；HR 可代操作；上级在驳回后也可帮员工改（但本系统要求员工自己写）。"""
    if current.id == target.id or _is_hr(current):
        return
    raise HTTPException(status_code=403, detail="无权操作该员工的试用期目标")


def _ensure_can_evaluate(session: Session, current: User, target: User) -> None:
    if not _is_superior(session, current, target):
        raise HTTPException(status_code=403, detail="无权评估该员工")


# ============ Pydantic Schema ============

class ProbationObjectiveItem(BaseModel):
    id: int | None = None
    title: str
    description: str
    measure_criteria: str
    order_num: int = 0


class ProbationObjectiveSave(BaseModel):
    objectives: list[ProbationObjectiveItem]
    submit: bool = False


class ObjectiveReviewPayload(BaseModel):
    reject_reason: str | None = None


class ProbationEvaluationPayload(BaseModel):
    result: str
    comment: str


class ProbationPlanUpdatePayload(BaseModel):
    end_date: date | None = None
    status: str | None = None
    extension_note: str | None = None


class ProbationObjectiveView(BaseModel):
    id: int
    title: str
    description: str
    measure_criteria: str
    order_num: int
    status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    reject_reason: str | None


class ProbationEvaluationView(BaseModel):
    result: str
    result_text: str
    comment: str
    evaluator_name: str
    evaluated_at: datetime


class ProbationPlanView(BaseModel):
    id: int
    user_id: int
    user_name: str
    department_name: str | None
    leader_name: str | None
    start_date: date
    end_date: date
    remaining_days: int
    status: str
    status_text: str
    objectives: list[ProbationObjectiveView]
    evaluation: ProbationEvaluationView | None


class ProbationListItem(BaseModel):
    id: int
    user_id: int
    user_name: str
    department_name: str | None
    leader_name: str | None
    start_date: date
    end_date: date
    remaining_days: int
    status: str
    status_text: str
    has_evaluation: bool


# ============ 内部：构建视图 ============

def _user_name_map(session: Session, user_ids: set[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    users = session.exec(select(User.id, User.name).where(User.id.in_(user_ids))).all()
    return {u.id: u.name for u in users}


def _dept_name_map(session: Session, dept_ids: set[int]) -> dict[int, str]:
    if not dept_ids:
        return {}
    depts = session.exec(select(Department.id, Department.name).where(Department.id.in_(dept_ids))).all()
    return {d.id: d.name for d in depts}


def _build_plan_view(
    session: Session,
    plan: ProbationPlan,
    user_map: dict[int, User],
    name_map: dict[int, str],
    dept_map: dict[int, str],
) -> ProbationPlanView:
    user = user_map.get(plan.user_id)
    leader_name = None
    if user and user.leader_userid:
        leader = session.exec(select(User).where(User.wecom_userid == user.leader_userid)).first()
        leader_name = leader.name if leader else user.leader_userid

    objectives = session.exec(
        select(ProbationObjective).where(ProbationObjective.plan_id == plan.id).order_by(ProbationObjective.order_num)
    ).all()

    today = date.today()
    remaining_days = (plan.end_date - today).days

    evaluation = None
    if plan.evaluation_result:
        evaluator_name = name_map.get(
            session.exec(select(User.id).where(User.wecom_userid == plan.evaluator_userid)).first() or 0,
            "未知",
        )
        evaluation = ProbationEvaluationView(
            result=plan.evaluation_result,
            result_text=_result_text(plan.evaluation_result),
            comment=plan.evaluation_comment or "",
            evaluator_name=evaluator_name,
            evaluated_at=plan.evaluated_at,
        )

    return ProbationPlanView(
        id=plan.id,
        user_id=plan.user_id,
        user_name=name_map.get(plan.user_id, "未知"),
        department_name=dept_map.get(user.department_id) if user and user.department_id else None,
        leader_name=leader_name,
        start_date=plan.start_date,
        end_date=plan.end_date,
        remaining_days=remaining_days,
        status=plan.status,
        status_text=_status_text(plan.status),
        objectives=[ProbationObjectiveView.model_validate(o, from_attributes=True) for o in objectives],
        evaluation=evaluation,
    )


def _build_list_item(
    session: Session,
    plan: ProbationPlan,
    user_map: dict[int, User],
    name_map: dict[int, str],
    dept_map: dict[int, str],
) -> ProbationListItem:
    user = user_map.get(plan.user_id)
    leader_name = None
    if user and user.leader_userid:
        leader = session.exec(select(User).where(User.wecom_userid == user.leader_userid)).first()
        leader_name = leader.name if leader else user.leader_userid

    today = date.today()
    remaining_days = (plan.end_date - today).days

    return ProbationListItem(
        id=plan.id,
        user_id=plan.user_id,
        user_name=name_map.get(plan.user_id, "未知"),
        department_name=dept_map.get(user.department_id) if user and user.department_id else None,
        leader_name=leader_name,
        start_date=plan.start_date,
        end_date=plan.end_date,
        remaining_days=remaining_days,
        status=plan.status,
        status_text=_status_text(plan.status),
        has_evaluation=bool(plan.evaluation_result),
    )


# ============ 自动同步试用期计划 ============

def _sync_probation_plans(session: Session) -> int:
    """为 employee_status='probation' 且没有 ProbationPlan 的员工自动创建计划。"""
    # 找出所有试用期员工
    probation_users = session.exec(
        select(User).where(User.employee_status == "probation", User.status == "active")
    ).all()

    # 找出已有计划的 user_id
    existing_user_ids = set(
        session.exec(select(ProbationPlan.user_id)).all()
    )

    created = 0
    for user in probation_users:
        if user.id in existing_user_ids:
            continue
        if not user.hired_at:
            continue

        months = user.probation if user.probation else DEFAULT_PROBATION_MONTHS
        start_date = user.hired_at
        end_date = _add_months(start_date, months)

        plan = ProbationPlan(
            user_id=user.id,
            start_date=start_date,
            end_date=end_date,
            probation_months=months,
            status=ProbationPlanStatus.DRAFT,
        )
        session.add(plan)
        created += 1

    if created > 0:
        session.commit()
    return created


# ============ API：手动同步 ============

@router.post("/sync-plans")
def sync_probation_plans(
    session: Session = Depends(get_session),
    current: User = Depends(require_role("hrbp", "super_admin")),
):
    """HR/超管手动触发试用期计划同步。"""
    created = _sync_probation_plans(session)
    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="sync_probation_plans",
        resource_type="probation_plan",
        resource_id="-",
        after={"created_count": created},
    )
    session.commit()
    return {"created": created}


# ============ API：列表查询 ============

@router.get("", response_model=list[ProbationListItem])
def list_probation_plans(
    status: str | None = Query(None),
    keyword: str | None = Query(None),
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """查询试用期计划列表。HR/Leader 按可见范围查看，员工只看自己（理论上走 /mine）。"""
    visible_ids = visible_user_ids(session, current)
    if visible_ids is not None:
        visible_ids = set(visible_ids)

    q = select(ProbationPlan, User).join(User, ProbationPlan.user_id == User.id)

    if visible_ids is not None:
        q = q.where(ProbationPlan.user_id.in_(visible_ids))

    if status:
        q = q.where(ProbationPlan.status == status)

    if keyword:
        q = q.where(User.name.contains(keyword))

    results = session.exec(q.order_by(ProbationPlan.end_date.asc())).all()

    user_ids = {r.User.id for r in results if r.User.id}
    dept_ids = {r.User.department_id for r in results if r.User.department_id}
    name_map = _user_name_map(session, user_ids)
    dept_map = _dept_name_map(session, dept_ids)
    user_map = {r.User.id: r.User for r in results if r.User.id}

    return [
        _build_list_item(session, r.ProbationPlan, user_map, name_map, dept_map)
        for r in results
    ]


# ============ API：我的试用期 ============

@router.get("/mine", response_model=ProbationPlanView | None)
def get_my_probation_plan(
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """当前用户查看自己的试用期计划；没有则自动创建（如果是试用期员工）。"""
    plan = session.exec(
        select(ProbationPlan).where(ProbationPlan.user_id == current.id)
    ).first()

    if not plan and current.employee_status == "probation":
        # 自动创建
        if current.hired_at:
            months = current.probation if current.probation else DEFAULT_PROBATION_MONTHS
            plan = ProbationPlan(
                user_id=current.id,
                start_date=current.hired_at,
                end_date=_add_months(current.hired_at, months),
                probation_months=months,
                status=ProbationPlanStatus.DRAFT,
            )
            session.add(plan)
            session.commit()
            session.refresh(plan)

            send_textcard_notification(
                target_userids=[current],
                title="试用期计划已创建",
                description="你的试用期计划已创建，请尽快填写试用期目标并提交审批。",
                url=f"/probation/{current.id}",
                payload={"probation_plan_id": plan.id, "user_id": current.id, "event": "plan_created"},
            )

    if not plan:
        return None

    user_ids = {plan.user_id}
    dept_ids = {current.department_id} if current.department_id else set()
    name_map = _user_name_map(session, user_ids)
    dept_map = _dept_name_map(session, dept_ids)
    return _build_plan_view(session, plan, {current.id: current}, name_map, dept_map)


# ============ API：详情查询 ============

@router.get("/{user_id}", response_model=ProbationPlanView)
def get_probation_plan_detail(
    user_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """查看某员工的试用期计划详情。"""
    ensure_can_view_user(session, current, user_id)
    plan = _get_plan_or_404(session, user_id)

    target = session.get(User, user_id)
    user_ids = {user_id}
    dept_ids = {target.department_id} if target and target.department_id else set()
    name_map = _user_name_map(session, user_ids)
    dept_map = _dept_name_map(session, dept_ids)
    return _build_plan_view(session, plan, {user_id: target}, name_map, dept_map)


# ============ API：保存/提交目标 ============

@router.post("/{user_id}/objectives")
def save_probation_objectives(
    user_id: int,
    payload: ProbationObjectiveSave,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """员工保存或提交试用期目标。覆盖式保存。"""
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    _ensure_can_write_objectives(session, current, target)

    plan = _get_plan_or_404(session, user_id)
    if plan.status not in (
        ProbationPlanStatus.DRAFT,
        ProbationPlanStatus.OBJECTIVE_DRAFT,
        ProbationPlanStatus.OBJECTIVE_PENDING_REVIEW,
    ) and not _is_hr(current):
        raise HTTPException(status_code=400, detail="当前计划状态不允许修改目标")

    # 校验
    if len(payload.objectives) < 1:
        raise HTTPException(status_code=400, detail="至少需要 1 条目标")
    if len(payload.objectives) > 10:
        raise HTTPException(status_code=400, detail="目标不能超过 10 条")

    for i, item in enumerate(payload.objectives):
        if not item.title.strip():
            raise HTTPException(status_code=400, detail=f"第 {i + 1} 条目标标题不能为空")
        if not item.description.strip():
            raise HTTPException(status_code=400, detail=f"第 {i + 1} 条目标描述不能为空")
        if not item.measure_criteria.strip():
            raise HTTPException(status_code=400, detail=f"第 {i + 1} 条衡量标准不能为空")

    # 覆盖保存
    old = session.exec(
        select(ProbationObjective).where(ProbationObjective.plan_id == plan.id)
    ).all()
    for o in old:
        session.delete(o)
    session.flush()

    now = datetime.now(timezone.utc)
    objective_status = (
        ProbationObjectiveStatus.PENDING_REVIEW
        if payload.submit
        else ProbationObjectiveStatus.DRAFT
    )
    for i, item in enumerate(payload.objectives):
        session.add(ProbationObjective(
            plan_id=plan.id,
            title=item.title.strip(),
            description=item.description.strip(),
            measure_criteria=item.measure_criteria.strip(),
            order_num=i,
            status=objective_status,
        ))

    if payload.submit:
        plan.status = ProbationPlanStatus.OBJECTIVE_PENDING_REVIEW
        plan.objective_submitted_at = now
    else:
        plan.status = ProbationPlanStatus.OBJECTIVE_DRAFT

    plan.updated_at = now

    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="save_probation_objectives",
        resource_type="probation_plan",
        resource_id=str(plan.id),
        after={"user_id": user_id, "count": len(payload.objectives), "submit": payload.submit},
    )
    session.commit()

    if payload.submit and target.leader_userid:
        send_textcard_notification(
            target_userids=[target.leader_userid],
            title="试用期目标待审批",
            description=f"员工 {target.name} 已提交试用期目标，请尽快审批。",
            url=f"/probation/{target.id}",
            payload={"probation_plan_id": plan.id, "user_id": target.id, "event": "objectives_submitted"},
        )

    return {"saved": len(payload.objectives), "submitted": payload.submit}


# ============ API：批准目标 ============

@router.post("/{user_id}/objectives/approve")
def approve_probation_objectives(
    user_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """直属上级或 HR 批准试用期目标。"""
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    _ensure_can_evaluate(session, current, target)

    plan = _get_plan_or_404(session, user_id)
    if plan.status != ProbationPlanStatus.OBJECTIVE_PENDING_REVIEW:
        raise HTTPException(status_code=400, detail="当前没有待审批的目标")

    pending = session.exec(
        select(ProbationObjective).where(
            ProbationObjective.plan_id == plan.id,
            ProbationObjective.status == ProbationObjectiveStatus.PENDING_REVIEW,
        )
    ).all()
    if not pending:
        # 如果状态是 pending_review 但没有 pending 的目标，可能是HR代操作后状态不一致
        raise HTTPException(status_code=400, detail="没有待审批的目标")

    now = datetime.now(timezone.utc)
    for o in pending:
        o.status = ProbationObjectiveStatus.APPROVED
        o.reviewed_by = current.wecom_userid
        o.reviewed_at = now
        session.add(o)

    plan.status = ProbationPlanStatus.IN_PROGRESS
    plan.objective_reviewed_by = current.wecom_userid
    plan.objective_reviewed_at = now
    plan.updated_at = now

    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="approve_probation_objectives",
        resource_type="probation_plan",
        resource_id=str(plan.id),
        after={"user_id": user_id, "count": len(pending)},
    )
    session.commit()

    send_textcard_notification(
        target_userids=[target],
        title="试用期目标已确认",
        description="你的试用期目标已通过审批，请按计划在试用期内完成目标。",
        url=f"/probation/{target.id}",
        payload={"probation_plan_id": plan.id, "user_id": target.id, "event": "objectives_approved"},
    )

    return {"approved": len(pending)}


# ============ API：驳回目标 ============

@router.post("/{user_id}/objectives/reject")
def reject_probation_objectives(
    user_id: int,
    payload: ObjectiveReviewPayload,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """直属上级或 HR 驳回试用期目标，需填写原因。"""
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    _ensure_can_evaluate(session, current, target)

    plan = _get_plan_or_404(session, user_id)
    if plan.status != ProbationPlanStatus.OBJECTIVE_PENDING_REVIEW:
        raise HTTPException(status_code=400, detail="当前没有待审批的目标")

    if not payload.reject_reason or not payload.reject_reason.strip():
        raise HTTPException(status_code=400, detail="驳回原因不能为空")

    pending = session.exec(
        select(ProbationObjective).where(
            ProbationObjective.plan_id == plan.id,
            ProbationObjective.status == ProbationObjectiveStatus.PENDING_REVIEW,
        )
    ).all()
    if not pending:
        raise HTTPException(status_code=400, detail="没有待审批的目标")

    now = datetime.now(timezone.utc)
    for o in pending:
        o.status = ProbationObjectiveStatus.DRAFT
        o.reviewed_by = current.wecom_userid
        o.reviewed_at = now
        o.reject_reason = payload.reject_reason.strip()
        session.add(o)

    plan.status = ProbationPlanStatus.OBJECTIVE_DRAFT
    plan.objective_reviewed_by = current.wecom_userid
    plan.objective_reviewed_at = now
    plan.updated_at = now

    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="reject_probation_objectives",
        resource_type="probation_plan",
        resource_id=str(plan.id),
        after={"user_id": user_id, "reason": payload.reject_reason.strip()},
    )
    session.commit()

    reason = payload.reject_reason.strip()
    send_textcard_notification(
        target_userids=[target],
        title="试用期目标被驳回",
        description=f"你的试用期目标已被驳回，原因：{reason}。请修改后重新提交。",
        url=f"/probation/{target.id}",
        payload={
            "probation_plan_id": plan.id,
            "user_id": target.id,
            "event": "objectives_rejected",
            "reject_reason": reason,
        },
    )

    return {"rejected": len(pending)}


# ============ API：提交评估 ============

@router.post("/{user_id}/evaluate")
def submit_probation_evaluation(
    user_id: int,
    payload: ProbationEvaluationPayload,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """直属上级或 HR 提交试用期评估与转正建议。"""
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    _ensure_can_evaluate(session, current, target)

    plan = _get_plan_or_404(session, user_id)
    if plan.status not in (
        ProbationPlanStatus.IN_PROGRESS,
        ProbationPlanStatus.PENDING_EVALUATION,
        ProbationPlanStatus.EXTENDED,
    ):
        raise HTTPException(status_code=400, detail="当前计划状态不允许评估")

    if payload.result not in (
        ProbationResult.REGULAR,
        ProbationResult.ELIMINATE,
        ProbationResult.PENDING_OTHER,
    ):
        raise HTTPException(status_code=400, detail="无效的转正建议")

    if not payload.comment or not payload.comment.strip():
        raise HTTPException(status_code=400, detail="评估意见不能为空")

    now = datetime.now(timezone.utc)
    plan.evaluation_result = payload.result
    plan.evaluation_comment = payload.comment.strip()
    plan.evaluator_userid = current.wecom_userid
    plan.evaluated_at = now
    plan.status = ProbationPlanStatus.COMPLETED
    plan.updated_at = now

    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="submit_probation_evaluation",
        resource_type="probation_plan",
        resource_id=str(plan.id),
        after={
            "user_id": user_id,
            "result": payload.result,
            "comment": payload.comment.strip(),
        },
    )
    session.commit()

    # 通知员工本人及 HRBP
    recipients: list[User | str] = [target]
    recipients.extend(get_hrbp_userids(session, target))
    send_textcard_notification(
        target_userids=recipients,
        title="试用期评估已完成",
        description=f"员工 {target.name} 的试用期评估已完成，转正建议：{_result_text(payload.result)}。",
        url=f"/probation/{target.id}",
        payload={
            "probation_plan_id": plan.id,
            "user_id": target.id,
            "event": "evaluation_submitted",
            "result": payload.result,
        },
    )

    return {"status": "completed"}


# ============ API：HR 修改计划 ============

@router.patch("/{user_id}")
def update_probation_plan(
    user_id: int,
    payload: ProbationPlanUpdatePayload,
    session: Session = Depends(get_session),
    current: User = Depends(require_role("hrbp", "super_admin")),
):
    """HR/超管修改试用期计划，如延期、调整状态等。"""
    plan = _get_plan_or_404(session, user_id)

    before = {
        "end_date": plan.end_date.isoformat() if plan.end_date else None,
        "status": plan.status,
    }

    now = datetime.now(timezone.utc)
    if payload.end_date:
        if payload.end_date < plan.start_date:
            raise HTTPException(status_code=400, detail="结束日期不能早于开始日期")
        plan.end_date = payload.end_date

    if payload.status:
        if payload.status == ProbationPlanStatus.EXTENDED:
            plan.extended_by = current.wecom_userid
            plan.extended_at = now
            plan.extension_note = payload.extension_note or "HR 手动延期"
        plan.status = payload.status

    plan.updated_at = now

    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="update_probation_plan",
        resource_type="probation_plan",
        resource_id=str(plan.id),
        before=before,
        after={
            "end_date": plan.end_date.isoformat() if plan.end_date else None,
            "status": plan.status,
            "extension_note": plan.extension_note,
        },
    )
    session.commit()
    return {"updated": True}
