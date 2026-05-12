# 绩效校准 + 公司级审批 API（PRD 3.4.7）
# 流程：上级初评完 → 部门 Leader 校准 → 提交审批 → HR 批/驳 → CEO 批/驳 → 锁定
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from pms.database.models.calibration import CalibrationRecord, CycleApproval
from pms.database.models.cycle import CycleParticipant, PerformanceCycle
from pms.database.models.enums import PerfLevel
from pms.database.models.evaluation import Evaluation
from pms.database.models.user import User
from pms.database.session import get_session
from pms.services.auth import get_current_user, is_hr_dept_leader
from pms.utils.audit import write_audit
from pms.utils.score import derive_perf_level, validate_perf_score

router = APIRouter(prefix="/calibration", tags=["calibration"])


# ============ Schema ============

class CalibrateItem(BaseModel):
    user_id: int
    perf_score: float | None = None  # 不改就不传
    value_grade: str | None = None   # 不改就不传
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
    initial_perf_score: float | None  # 上级初评
    initial_perf_level: str | None
    initial_value_grade: str | None
    calibrated_perf_score: float | None  # 校准后（cycle_participant 上的）
    calibrated_perf_level: str | None
    calibrated_value_grade: str | None
    participant_status: str


# ============ 3-6-1 分布计算 ============

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
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # Leader / HR / 超管可看
    if current.role not in ("dept_leader", "hrbp", "super_admin"):
        raise HTTPException(status_code=403, detail="无权限")

    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="周期不存在")

    # 拉参与人 + 上级评估初评值
    from pms.services.scope import visible_user_ids
    scope = visible_user_ids(session, current)

    q = select(CycleParticipant, User).join(
        User, User.id == CycleParticipant.user_id
    ).where(CycleParticipant.cycle_id == cycle_id)
    if scope is not None:
        q = q.where(CycleParticipant.user_id.in_(scope))

    rows = session.exec(q).all()
    items: list[CalibrationView] = []
    for p, u in rows:
        # 上级初评值
        sup_eval = session.exec(
            select(Evaluation).where(
                Evaluation.cycle_id == cycle_id,
                Evaluation.user_id == p.user_id,
                Evaluation.eval_type == "superior",
            )
        ).first()
        items.append(CalibrationView(
            user_id=p.user_id,
            user_name=u.name,
            user_position=u.position,
            dept_name=p.dept_name_snapshot,
            initial_perf_score=sup_eval.perf_score if sup_eval else None,
            initial_perf_level=sup_eval.perf_level if sup_eval else None,
            initial_value_grade=sup_eval.value_grade if sup_eval else None,
            calibrated_perf_score=p.final_perf_score,
            calibrated_perf_level=p.final_perf_level,
            calibrated_value_grade=p.final_value_grade,
            participant_status=p.status,
        ))

    # 审批状态
    approval = session.exec(
        select(CycleApproval).where(CycleApproval.cycle_id == cycle_id)
    ).first()

    # 分布
    all_participants = [p for p, _ in rows]
    distribution = _compute_distribution(all_participants)

    return {
        "cycle": {"id": cycle.id, "name": cycle.name, "status": cycle.status},
        "approval_status": approval.status if approval else "calibrating",
        "reject_reason": approval.reject_reason if approval else None,
        "items": [i.model_dump() for i in items],
        "distribution": [d.model_dump() for d in distribution],
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
    if current.role not in ("dept_leader", "hrbp", "super_admin"):
        raise HTTPException(status_code=403, detail="无权校准")

    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle or cycle.status != "in_progress":
        raise HTTPException(status_code=400, detail="周期不在进行中")

    # 审批状态必须是 calibrating 或 被驳回才能改
    approval = session.exec(
        select(CycleApproval).where(CycleApproval.cycle_id == cycle_id)
    ).first()
    if approval and approval.status not in ("calibrating", "rejected_by_hr", "rejected_by_ceo"):
        raise HTTPException(status_code=400, detail=f"当前审批状态为 {approval.status}，不能修改")

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
            score = validate_perf_score(item.perf_score)
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

        if item.value_grade is not None:
            if item.value_grade not in ("jia", "yi", "bing"):
                raise HTTPException(status_code=400, detail="value_grade 只能是 jia/yi/bing")
            old_grade = p.final_value_grade
            p.final_value_grade = item.value_grade
            session.add(CalibrationRecord(
                cycle_id=cycle_id, user_id=item.user_id,
                operator_userid=current.wecom_userid, operator_name=current.name,
                field_changed="value_grade",
                old_value=str(old_grade), new_value=item.value_grade,
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
    if current.role not in ("dept_leader", "hrbp", "super_admin"):
        raise HTTPException(status_code=403, detail="无权操作")

    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle or cycle.status != "in_progress":
        raise HTTPException(status_code=400, detail="周期不在进行中")

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
    if not approval:
        approval = CycleApproval(cycle_id=cycle_id)
    approval.status = "pending_hr"
    approval.submitted_at = datetime.utcnow()
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
    has_hr = current.role in ("hrbp", "super_admin") or is_hr_dept_leader(current, session)
    if not has_hr:
        raise HTTPException(status_code=403, detail="无权审批")

    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle or cycle.status != "in_progress":
        raise HTTPException(status_code=400, detail="周期不在进行中")

    approval = session.exec(
        select(CycleApproval).where(CycleApproval.cycle_id == cycle_id)
    ).first()
    if not approval:
        raise HTTPException(status_code=400, detail="尚未提交校准")

    now = datetime.utcnow()

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
    return {"status": approval.status}


# ============ 校准修改历史 ============

@router.get("/cycles/{cycle_id}/history")
def get_calibration_history(
    cycle_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    if current.role not in ("dept_leader", "hrbp", "super_admin"):
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
