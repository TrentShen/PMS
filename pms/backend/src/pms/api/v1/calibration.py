from __future__ import annotations

# 绩效校准 + 公司级审批 API（PRD 3.4.7）
# 流程：上级初评完 → 部门 Leader 校准 → 提交审批 → HR 批/驳 → CEO 批/驳 → 锁定
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from pms.database.models.audit import AuditLog
from pms.database.models.calibration import CalibrationRecord, CycleApproval
from pms.database.models.cycle import CycleParticipant, PerformanceCycle
from pms.database.models.enums import PerfLevel
from pms.database.models.evaluation import Evaluation
from pms.database.models.user import User
from pms.database.session import get_session
from pms.services.auth import get_current_user, has_any_role, is_hr_dept_leader, require_fte
from pms.services.notification import get_hrbp_userids, send_textcard_notification
from pms.services.scope import visible_user_ids
from pms.utils.audit import write_audit
from pms.utils.score import derive_perf_level, validate_perf_score

router = APIRouter(
    prefix="/calibration",
    tags=["calibration"],
    dependencies=[Depends(require_fte)],
)


# ============ Schema ============

class CalibrateItem(BaseModel):
    user_id: int
    perf_score: float | None = None  # 不改就不传
    # 价值观三维度，不改的维度不传
    value_belief_grade: str | None = None
    value_team_grade: str | None = None
    value_growth_grade: str | None = None
    reason: str  # 修改理由（必填）


class CalibrateRequest(BaseModel):
    items: list[CalibrateItem]


class ApprovalAction(BaseModel):
    action: str  # approve / reject
    comment: str | None = None


class DistributionItem(BaseModel):
    level: str
    label: str
    count: int
    percent: float
    target_percent: str  # 如 "≤30%"
    warning: bool  # 超标预警


class CalibrationView(BaseModel):
    user_id: int
    user_name: str
    user_position: str | None
    dept_name: str | None
    user_level: str | None
    initial_perf_score: float | None  # 上级初评
    initial_perf_level: str | None
    initial_value_belief: str | None
    initial_value_team: str | None
    initial_value_growth: str | None
    calibrated_perf_score: float | None  # 校准后（cycle_participant 上的）
    calibrated_perf_level: str | None
    calibrated_value_belief: str | None
    calibrated_value_team: str | None
    calibrated_value_growth: str | None
    participant_status: str


class MatrixRow(BaseModel):
    group: str
    excellent: int
    exceed_part: int
    meet: int
    below_part: int
    below: int
    unset: int
    total: int


# ============ 3-6-1 分布计算 ============

def _compute_matrix(rows: list) -> dict[str, list[MatrixRow]]:
    """按部门和职级分组，统计各绩效等级人数"""
    from collections import defaultdict

    def _build(groups: dict) -> list[MatrixRow]:
        result = []
        for g, counts in sorted(groups.items()):
            total = sum(counts.values())
            result.append(MatrixRow(
                group=g,
                excellent=counts.get("excellent", 0),
                exceed_part=counts.get("exceed_part", 0),
                meet=counts.get("meet", 0),
                below_part=counts.get("below_part", 0),
                below=counts.get("below", 0),
                unset=counts.get("unset", 0),
                total=total,
            ))
        return result

    by_dept: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_level: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for p, u, _ in rows:
        dept = p.dept_name_snapshot or "未分组"
        level = p.final_perf_level or "unset"
        by_dept[dept][level] += 1

        user_level = u.level or "未设置"
        by_level[user_level][level] += 1

    return {
        "by_dept": [r.model_dump() for r in _build(by_dept)],
        "by_level": [r.model_dump() for r in _build(by_level)],
    }


def _compute_distribution(participants: list[CycleParticipant]) -> list[DistributionItem]:
    # 根据当前 final_perf_level 统计 A/B/C 三档占比
    total = len(participants)
    if total == 0:
        return []

    # A = excellent + exceed_part; B = meet; C = below_part + below
    a_levels = {PerfLevel.EXCELLENT.value, PerfLevel.EXCEED_PART.value}
    b_levels = {PerfLevel.MEET.value}
    c_levels = {PerfLevel.BELOW_PART.value, PerfLevel.BELOW.value}

    a_count = sum(1 for p in participants if p.final_perf_level in a_levels)
    b_count = sum(1 for p in participants if p.final_perf_level in b_levels)
    c_count = sum(1 for p in participants if p.final_perf_level in c_levels)
    unset = total - a_count - b_count - c_count

    def pct(n: int) -> float:
        return round(n / total * 100, 1)

    return [
        DistributionItem(
            level="A", label="优秀+部分超出", count=a_count,
            percent=pct(a_count), target_percent="≤30%",
            warning=pct(a_count) > 30,
        ),
        DistributionItem(
            level="B", label="符合预期", count=b_count,
            percent=pct(b_count), target_percent="≈60%",
            warning=False,  # B 档不做硬预警
        ),
        DistributionItem(
            level="C", label="部分不符+不符合", count=c_count,
            percent=pct(c_count), target_percent="≥10%",
            warning=pct(c_count) < 10,
        ),
        DistributionItem(
            level="unset", label="未评定", count=unset,
            percent=pct(unset), target_percent="-",
            warning=unset > 0,
        ),
    ]


# ============ 校准视图：看当前所有参与人的分数与分布 ============

@router.get("/cycles/{cycle_id}/view")
def get_calibration_view(
    cycle_id: int,
    page: int = 1,
    page_size: int = 50,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    if not has_any_role(current, "dept_leader", "hrbp", "super_admin"):
        raise HTTPException(status_code=403, detail="无权限")

    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="周期不存在")

    from pms.services.scope import visible_user_ids
    scope = visible_user_ids(session, current)

    from sqlalchemy.orm import aliased
    sup_eval_alias = aliased(Evaluation)

    q = (
        select(CycleParticipant, User, sup_eval_alias)
        .join(User, User.id == CycleParticipant.user_id)
        .outerjoin(
            sup_eval_alias,
            (sup_eval_alias.cycle_id == CycleParticipant.cycle_id)
            & (sup_eval_alias.user_id == CycleParticipant.user_id)
            & (sup_eval_alias.eval_type == "superior"),
        )
        .where(CycleParticipant.cycle_id == cycle_id)
    )
    if scope is not None:
        q = q.where(CycleParticipant.user_id.in_(scope))

    rows = session.exec(q).all()

    items: list[CalibrationView] = []
    for p, u, sup_eval in rows:
        items.append(CalibrationView(
            user_id=p.user_id,
            user_name=u.name,
            user_position=u.position,
            dept_name=p.dept_name_snapshot,
            user_level=u.level,
            initial_perf_score=sup_eval.perf_score if sup_eval else None,
            initial_perf_level=sup_eval.perf_level if sup_eval else None,
            initial_value_belief=sup_eval.value_belief_grade if sup_eval else None,
            initial_value_team=sup_eval.value_team_grade if sup_eval else None,
            initial_value_growth=sup_eval.value_growth_grade if sup_eval else None,
            calibrated_perf_score=p.final_perf_score,
            calibrated_perf_level=p.final_perf_level,
            calibrated_value_belief=p.final_value_belief,
            calibrated_value_team=p.final_value_team,
            calibrated_value_growth=p.final_value_growth,
            participant_status=p.status,
        ))

    approval = session.exec(
        select(CycleApproval).where(CycleApproval.cycle_id == cycle_id)
    ).first()

    all_participants = [p for p, _, _ in rows]
    distribution = _compute_distribution(all_participants)
    matrix = _compute_matrix(rows)

    # 分页
    total = len(items)
    start = (page - 1) * page_size
    paged_items = items[start:start + page_size]

    return {
        "cycle": {"id": cycle.id, "name": cycle.name, "status": cycle.status},
        "approval_status": approval.status if approval else "calibrating",
        "reject_reason": approval.reject_reason if approval else None,
        "items": [i.model_dump() for i in paged_items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "distribution": [d.model_dump() for d in distribution],
        "matrix": matrix,
    }


# ============ 部门 Leader 校准：批量改分 ============

@router.post("/cycles/{cycle_id}/calibrate")
def calibrate(
    cycle_id: int,
    payload: CalibrateRequest,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # 仅 dept_leader / hrbp / super_admin 可操作
    if not has_any_role(current, "dept_leader", "hrbp", "super_admin"):
        raise HTTPException(status_code=403, detail="无权校准")

    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle or cycle.status != "in_progress":
        raise HTTPException(status_code=400, detail="周期不在进行中")
    if not cycle.enable_calibration:
        raise HTTPException(status_code=400, detail="当前周期未开启校准")

    # 审批状态必须是 calibrating 或 被驳回才能改
    approval = session.exec(
        select(CycleApproval).where(CycleApproval.cycle_id == cycle_id)
    ).first()
    if approval and approval.status not in ("calibrating", "rejected_by_hr", "rejected_by_ceo"):
        raise HTTPException(status_code=400, detail=f"当前审批状态为 {approval.status}，不能修改")

    # scope 校验：越权用户直接 403（visible_user_ids 返回 None 表示不限制）
    scope = visible_user_ids(session, current)
    if scope is not None:
        for item in payload.items:
            if item.user_id not in scope:
                raise HTTPException(
                    status_code=403,
                    detail=f"无权校准 user_id={item.user_id}（不在你的管辖范围内）",
                )

    modified = 0
    for item in payload.items:
        p = session.exec(
            select(CycleParticipant).where(
                CycleParticipant.cycle_id == cycle_id,
                CycleParticipant.user_id == item.user_id,
            )
        ).first()
        if not p:
            continue
        if not item.reason.strip():
            raise HTTPException(status_code=400, detail=f"user_id={item.user_id} 修改原因必填")

        if item.perf_score is not None:
            try:
                score = validate_perf_score(item.perf_score)
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"user_id={item.user_id} {e}",
                ) from e
            old_score = p.final_perf_score
            p.final_perf_score = score
            p.final_perf_level = derive_perf_level(score).value
            session.add(CalibrationRecord(
                cycle_id=cycle_id, user_id=item.user_id,
                operator_userid=current.wecom_userid, operator_name=current.name,
                field_changed="perf_score",
                old_value=str(old_score), new_value=str(score),
                reason=item.reason,
            ))
            modified += 1

        # 价值观三维度校准
        for dim_field, dim_label in [("belief", "信念"), ("team", "团队"), ("growth", "成长")]:
            new_grade = getattr(item, f"value_{dim_field}_grade", None)
            if new_grade is None:
                continue
            if new_grade not in ("jia", "yi", "bing"):
                raise HTTPException(status_code=400, detail=f"价值观「{dim_label}」只能是 jia/yi/bing")
            final_attr = f"final_value_{dim_field}"
            old_grade = getattr(p, final_attr)
            setattr(p, final_attr, new_grade)
            session.add(CalibrationRecord(
                cycle_id=cycle_id, user_id=item.user_id,
                operator_userid=current.wecom_userid, operator_name=current.name,
                field_changed=f"value_{dim_field}",
                old_value=str(old_grade), new_value=new_grade,
                reason=item.reason,
            ))
            modified += 1

        session.add(p)

    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="calibrate",
        resource_type="performance_cycle",
        resource_id=str(cycle_id),
        after={"modified_count": modified},
    )
    session.commit()
    return {"modified": modified}


# ============ Leader 提交校准 → 进入审批 ============

@router.post("/cycles/{cycle_id}/submit-calibration")
def submit_calibration(
    cycle_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    if not has_any_role(current, "dept_leader", "hrbp", "super_admin"):
        raise HTTPException(status_code=403, detail="无权操作")

    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle or cycle.status != "in_progress":
        raise HTTPException(status_code=400, detail="周期不在进行中")
    if not cycle.enable_calibration:
        raise HTTPException(status_code=400, detail="当前周期未开启校准")

    # 检查所有参与人都有 final_perf_score（即上级评估或校准都赋值了）
    parts = session.exec(
        select(CycleParticipant).where(CycleParticipant.cycle_id == cycle_id)
    ).all()
    unset = [p for p in parts if p.final_perf_score is None]
    if unset:
        raise HTTPException(status_code=400, detail=f"还有 {len(unset)} 人未确定最终评分")

    # 创建或更新 approval
    approval = session.exec(
        select(CycleApproval).where(CycleApproval.cycle_id == cycle_id)
    ).first()
    if approval and approval.status == "approved":
        raise HTTPException(status_code=400, detail="审批已通过，不可回退重新提交")
    if not approval:
        approval = CycleApproval(cycle_id=cycle_id)
    approval.status = "pending_hr"
    approval.submitted_at = datetime.now(timezone.utc)
    approval.reject_reason = None
    approval.rejected_by = None
    approval.rejected_at = None
    session.add(approval)

    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="submit_calibration",
        resource_type="cycle_approval",
        resource_id=str(cycle_id),
        after={"status": "pending_hr"},
    )
    session.commit()

    # 通知 HRBP 进行审批
    hrbp_userids = get_hrbp_userids(session)
    if hrbp_userids:
        send_textcard_notification(
            target_userids=hrbp_userids,
            title="校准结果待审批",
            description=f"「{cycle.name}」校准结果已提交，请尽快进行 HR 审批。",
            url=f"/calibration/{cycle.id}/approval",
            payload={"cycle_id": cycle.id, "event": "calibration_submitted"},
        )

    return {"status": "pending_hr"}


# ============ HR / CEO 审批 ============

@router.post("/cycles/{cycle_id}/approval")
def process_approval(
    cycle_id: int,
    payload: ApprovalAction,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # HR 权限：hrbp / super_admin / HR 部门 Leader
    has_hr = has_any_role(current, "hrbp", "super_admin") or is_hr_dept_leader(current, session)
    if not has_hr:
        raise HTTPException(status_code=403, detail="无权审批")

    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle or cycle.status != "in_progress":
        raise HTTPException(status_code=400, detail="周期不在进行中")
    if not cycle.enable_calibration:
        raise HTTPException(status_code=400, detail="当前周期未开启校准")

    approval = session.exec(
        select(CycleApproval).where(CycleApproval.cycle_id == cycle_id)
    ).first()
    if not approval:
        raise HTTPException(status_code=400, detail="尚未提交校准")

    now = datetime.now(timezone.utc)

    # 判断当前应该谁审批
    if approval.status == "pending_hr":
        # HR 审批
        if payload.action == "approve":
            approval.status = "pending_ceo"
            approval.hr_approver_userid = current.wecom_userid
            approval.hr_approved_at = now
            approval.hr_comment = payload.comment
        elif payload.action == "reject":
            approval.status = "rejected_by_hr"
            approval.reject_reason = payload.comment or "HR 驳回"
            approval.rejected_by = current.wecom_userid
            approval.rejected_at = now
        else:
            raise HTTPException(status_code=400, detail="action 只能是 approve/reject")

    elif approval.status == "pending_ceo":
        # CEO 审批（V0.9 简化：hrbp/super_admin 都可以代 CEO 审批）
        if payload.action == "approve":
            approval.status = "approved"
            approval.ceo_approver_userid = current.wecom_userid
            approval.ceo_approved_at = now
            approval.ceo_comment = payload.comment
        elif payload.action == "reject":
            approval.status = "rejected_by_ceo"
            approval.reject_reason = payload.comment or "CEO 驳回"
            approval.rejected_by = current.wecom_userid
            approval.rejected_at = now
        else:
            raise HTTPException(status_code=400, detail="action 只能是 approve/reject")
    else:
        raise HTTPException(status_code=400, detail=f"当前状态 {approval.status} 不需要审批")

    session.add(approval)
    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="approval_action",
        resource_type="cycle_approval",
        resource_id=str(cycle_id),
        after={"action": payload.action, "new_status": approval.status},
    )
    session.commit()

    # 审批状态变化通知
    _notify_after_approval(session, cycle, approval, payload)

    return {"status": approval.status}


# ============ 校准修改历史 ============

@router.get("/cycles/{cycle_id}/history")
def get_calibration_history(
    cycle_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    if not has_any_role(current, "dept_leader", "hrbp", "super_admin"):
        raise HTTPException(status_code=403, detail="无权限")

    records = session.exec(
        select(CalibrationRecord).where(CalibrationRecord.cycle_id == cycle_id)
        .order_by(CalibrationRecord.created_at.desc())
    ).all()
    return [
        {
            "user_id": r.user_id,
            "operator_name": r.operator_name,
            "field_changed": r.field_changed,
            "old_value": r.old_value,
            "new_value": r.new_value,
            "reason": r.reason,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]


def _notify_after_approval(
    session: Session,
    cycle: PerformanceCycle,
    approval: CycleApproval,
    payload: ApprovalAction,
) -> None:
    """根据审批结果推送关键节点通知。"""
    # 获取提交人（从 audit log 找最近一条 submit_calibration）
    submit_audit = session.exec(
        select(AuditLog)
        .where(
            AuditLog.action == "submit_calibration",
            AuditLog.resource_type == "cycle_approval",
            AuditLog.resource_id == str(cycle.id),
        )
        .order_by(AuditLog.created_at.desc())
    ).first()
    submitter_userid = submit_audit.operator_userid if submit_audit else None

    if approval.status == "pending_ceo":
        # HR 已通过，通知 CEO/超级管理员进入下一轮审批
        ceo_users = session.exec(
            select(User).where(User.role == "super_admin", User.status == "active")
        ).all()
        notify_userids = [u.wecom_userid for u in ceo_users if u.wecom_userid]
        if notify_userids:
            send_textcard_notification(
                target_userids=notify_userids,
                title="校准结果待 CEO 审批",
                description=f"「{cycle.name}」已通过 HR 审批，请尽快进行 CEO 审批。",
                url=f"/calibration/{cycle.id}/approval",
                payload={"cycle_id": cycle.id, "event": "calibration_pending_ceo"},
            )
    elif approval.status == "approved":
        # CEO 审批通过，通知所有部门 Leader 和 HRBP
        dept_leaders = session.exec(
            select(User).where(User.role == "dept_leader", User.status == "active")
        ).all()
        notify_userids = {u.wecom_userid for u in dept_leaders if u.wecom_userid}
        notify_userids.update(get_hrbp_userids(session))
        if notify_userids:
            send_textcard_notification(
                target_userids=list(notify_userids),
                title="校准审批已通过",
                description=f"「{cycle.name}」校准结果已审批通过，绩效结果已锁定。",
                url=f"/calibration/{cycle.id}/view",
                payload={"cycle_id": cycle.id, "event": "calibration_approved"},
            )
    elif approval.status in ("rejected_by_hr", "rejected_by_ceo"):
        # 驳回时通知提交人
        if submitter_userid:
            send_textcard_notification(
                target_userids=[submitter_userid],
                title="校准审批被驳回",
                description=f"「{cycle.name}」校准结果已被{approval.status.replace('rejected_by_', '')}驳回，请修改后重新提交。",
                url=f"/calibration/{cycle.id}/view",
                payload={"cycle_id": cycle.id, "event": "calibration_rejected"},
            )
