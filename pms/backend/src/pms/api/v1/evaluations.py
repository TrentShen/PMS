from __future__ import annotations

# 自评 + 上级评估接口
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from pms.database.models.cycle import CycleParticipant, PerformanceCycle
from pms.database.models.enums import EvalType, ParticipantStatus
from pms.database.models.evaluation import Evaluation
from pms.database.models.objective import Objective
from pms.database.models.objective_cycle import ObjectiveCycle
from pms.database.models.user import User
from pms.database.session import get_session
from pms.services.auth import can_act_as_superior, get_current_user, has_any_role, require_fte
from pms.services.notification import get_hrbp_userids, send_textcard_notification
from pms.services.scope import ensure_can_view_user
from pms.utils.audit import write_audit
from pms.utils.score import (
    derive_perf_level,
    validate_perf_score,
    validate_value_grades,
)

router = APIRouter(
    prefix="/cycles/{cycle_id}",
    tags=["evaluations"],
    dependencies=[Depends(require_fte)],
)


# ============ Schema ============

class ObjectiveView(BaseModel):
    id: int
    title: str
    description: str
    measure_criteria: str | None = None
    weight: int
    order_num: int = 0
    status: str = "draft"
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    reject_reason: str | None = None


class EvaluationView(BaseModel):
    id: int | None = None
    eval_type: str
    evaluator_userid: str | None = None
    perf_score: float | None = None
    perf_level: str | None = None
    # 价值观三维度
    value_belief_grade: str | None = None
    value_belief_example: str | None = None
    value_team_grade: str | None = None
    value_team_example: str | None = None
    value_growth_grade: str | None = None
    value_growth_example: str | None = None
    key_results: str | None = None
    comment: str | None = None
    submitted_at: datetime | None = None
    status: str = "draft"


class EvaluationSubmit(BaseModel):
    perf_score: float
    # 价值观三维度（每个都是 jia/yi/bing）
    value_belief_grade: str
    value_belief_example: str | None = None
    value_team_grade: str
    value_team_example: str | None = None
    value_growth_grade: str
    value_growth_example: str | None = None
    key_results: str
    comment: str | None = None


class UserProfile(BaseModel):
    id: int
    name: str
    position: str | None
    level: str | None
    leader_userid: str | None


# ============ 查：某位员工在该周期的完整视图 ============

@router.get("/users/{user_id}/detail")
def get_evaluation_detail(
    cycle_id: int,
    user_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # 汇总：该员工的基本信息 + 目标 + 自评 + 上级评估
    ensure_can_view_user(session, current, user_id)

    cycle = session.get(PerformanceCycle, cycle_id)
    user = session.get(User, user_id)
    participant = session.exec(
        select(CycleParticipant).where(
            CycleParticipant.cycle_id == cycle_id,
            CycleParticipant.user_id == user_id,
        )
    ).first()
    if not cycle or not user or not participant:
        raise HTTPException(status_code=404, detail="数据不存在")

    # 从关联的目标周期获取目标
    objectives = []
    if cycle.objective_cycle_id:
        objectives = session.exec(
            select(Objective).where(
                Objective.objective_cycle_id == cycle.objective_cycle_id,
                Objective.user_id == user_id,
            ).order_by(Objective.order_num)
        ).all()

    evals = session.exec(
        select(Evaluation).where(
            Evaluation.cycle_id == cycle_id, Evaluation.user_id == user_id
        )
    ).all()
    self_eva = next((e for e in evals if e.eval_type == EvalType.SELF.value), None)
    superior_eva = next((e for e in evals if e.eval_type == EvalType.SUPERIOR.value), None)

    # 可见性：只有在 published 或本人/Leader/HR 时才看到对方的评
    def _eva_view(e: Evaluation | None) -> dict | None:
        if not e:
            return None
        return EvaluationView.model_validate(e, from_attributes=True).model_dump(mode="json")

    # 员工本人如果周期未发布，不允许看到上级评估的分数（只看自己的自评）
    can_see_superior = (
        has_any_role(current, "hrbp", "super_admin", "dept_leader")
        or current.wecom_userid == user.leader_userid
        or cycle.status == "published"
    )

    # PRD 3.4.8：员工最终结果在反馈确认后才可见
    # 如果是本人查看且周期已发布但反馈未确认，隐藏最终分数
    is_self = current.id == user_id
    show_final = True
    if is_self and cycle.status == "published":
        from pms.database.models.feedback import FeedbackRecord
        fb = session.exec(
            select(FeedbackRecord).where(
                FeedbackRecord.cycle_id == cycle_id,
                FeedbackRecord.user_id == user_id,
            )
        ).first()
        # 没有反馈记录 或 反馈未确认 → 隐藏最终分数
        if not fb or fb.confirm_status == "pending":
            show_final = False

    # 历史绩效：该员工所有已发布周期的结果
    history_perf = []
    if can_see_superior:
        from pms.database.models.cycle import PerformanceCycle as PerfCycle
        hist = session.exec(
            select(CycleParticipant, PerfCycle)
            .join(PerfCycle, PerfCycle.id == CycleParticipant.cycle_id)
            .where(
                CycleParticipant.user_id == user_id,
                PerfCycle.status == "published",
                PerfCycle.id != cycle_id,
            )
            .order_by(PerfCycle.end_date.desc())
            .limit(5)
        ).all()
        for hp, hc in hist:
            history_perf.append({
                "cycle_name": hc.name,
                "cycle_id": hc.id,
                "final_perf_score": hp.final_perf_score,
                "final_perf_level": hp.final_perf_level,
                "final_value_belief": hp.final_value_belief,
                "final_value_team": hp.final_value_team,
                "final_value_growth": hp.final_value_growth,
            })

    objective_cycle_info = None
    if cycle.objective_cycle_id:
        oc = session.get(ObjectiveCycle, cycle.objective_cycle_id)
        if oc:
            objective_cycle_info = {
                "id": oc.id,
                "name": oc.name,
                "status": oc.status,
                "start_date": oc.start_date.isoformat(),
                "end_date": oc.end_date.isoformat(),
            }

    return {
        "cycle": {
            "id": cycle.id,
            "name": cycle.name,
            "status": cycle.status,
            "start_date": cycle.start_date.isoformat(),
            "end_date": cycle.end_date.isoformat(),
            "objective_cycle_id": cycle.objective_cycle_id,
            "enable_self_eval": cycle.enable_self_eval,
            "enable_peer_eval": cycle.enable_peer_eval,
            "enable_calibration": cycle.enable_calibration,
            "enable_feedback": cycle.enable_feedback,
        },
        "objective_cycle": objective_cycle_info,
        "user": UserProfile(
            id=user.id,
            name=user.name,
            position=user.position,
            level=user.level,
            leader_userid=user.leader_userid,
        ).model_dump(),
        "participant_status": participant.status,
        # 员工本人在反馈确认前看不到最终分数
        "final_perf_score": participant.final_perf_score if show_final else None,
        "final_perf_level": participant.final_perf_level if show_final else None,
        "final_value_belief": participant.final_value_belief if show_final else None,
        "final_value_team": participant.final_value_team if show_final else None,
        "final_value_growth": participant.final_value_growth if show_final else None,
        "result_pending_feedback": not show_final if is_self else None,
        "objectives": [
            ObjectiveView.model_validate(o, from_attributes=True).model_dump() for o in objectives
        ],
        "self_evaluation": _eva_view(self_eva),
        "superior_evaluation": _eva_view(superior_eva) if can_see_superior else None,
        "history_perf": history_perf,
    }


# ============ 写：自评 ============

@router.post("/self-evaluation")
def submit_self_evaluation(
    cycle_id: int,
    payload: EvaluationSubmit,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # 自评 = 自己给自己，被评人 = 当前用户
    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle or cycle.status != "in_progress":
        raise HTTPException(status_code=400, detail="周期不在进行中，无法提交自评")
    if not cycle.enable_self_eval:
        raise HTTPException(status_code=400, detail="当前周期未开启自评")

    participant = session.exec(
        select(CycleParticipant).where(
            CycleParticipant.cycle_id == cycle_id,
            CycleParticipant.user_id == current.id,
        )
    ).first()
    if not participant:
        raise HTTPException(status_code=403, detail="你不在本周期的参与人列表中")

    # 目标校验：PRD 要求 3-5 条目标，至少要有目标才能自评
    obj_count = 0
    if cycle.objective_cycle_id:
        obj_count = len(session.exec(
            select(Objective).where(
                Objective.objective_cycle_id == cycle.objective_cycle_id,
                Objective.user_id == current.id,
            )
        ).all())
    if obj_count == 0:
        raise HTTPException(status_code=400, detail="你还没有绩效目标，请先导入或录入目标后再自评")

    # 规则校验
    try:
        score = validate_perf_score(payload.perf_score)
        validate_value_grades(
            payload.value_belief_grade, payload.value_belief_example,
            payload.value_team_grade, payload.value_team_example,
            payload.value_growth_grade, payload.value_growth_example,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not payload.key_results or not payload.key_results.strip():
        raise HTTPException(status_code=400, detail="关键成果必填")

    # upsert
    eva = session.exec(
        select(Evaluation).where(
            Evaluation.cycle_id == cycle_id,
            Evaluation.user_id == current.id,
            Evaluation.eval_type == EvalType.SELF.value,
        )
    ).first()
    before = None
    if eva:
        before = {"perf_score": eva.perf_score, "status": eva.status}
        eva.perf_score = score
        eva.perf_level = derive_perf_level(score).value
        eva.value_belief_grade = payload.value_belief_grade
        eva.value_belief_example = payload.value_belief_example
        eva.value_team_grade = payload.value_team_grade
        eva.value_team_example = payload.value_team_example
        eva.value_growth_grade = payload.value_growth_grade
        eva.value_growth_example = payload.value_growth_example
        eva.key_results = payload.key_results
        eva.comment = payload.comment
        eva.submitted_at = datetime.now(timezone.utc)
        eva.status = "submitted"
    else:
        eva = Evaluation(
            cycle_id=cycle_id,
            user_id=current.id,
            evaluator_userid=current.wecom_userid,
            eval_type=EvalType.SELF.value,
            perf_score=score,
            perf_level=derive_perf_level(score).value,
            value_belief_grade=payload.value_belief_grade,
            value_belief_example=payload.value_belief_example,
            value_team_grade=payload.value_team_grade,
            value_team_example=payload.value_team_example,
            value_growth_grade=payload.value_growth_grade,
            value_growth_example=payload.value_growth_example,
            key_results=payload.key_results,
            comment=payload.comment,
            submitted_at=datetime.now(timezone.utc),
            status="submitted",
        )
    session.add(eva)

    # 进度推进
    if participant.status == "pending":
        participant.status = ParticipantStatus.SELF_DONE.value
        session.add(participant)

    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="submit_self_evaluation",
        resource_type="evaluation",
        resource_id=f"{cycle_id}:{current.id}",
        before=before,
        after={"perf_score": score, "value_belief": payload.value_belief_grade, "value_team": payload.value_team_grade, "value_growth": payload.value_growth_grade},
    )
    session.commit()
    session.refresh(eva)

    # 通知直属上级
    if current.leader_userid:
        send_textcard_notification(
            target_userids=[current.leader_userid],
            title="员工自评已完成",
            description=f"员工 {current.name} 已完成「{cycle.name}」的自评，请尽快完成上级评估。",
            url=f"/leader/{cycle.id}/users/{current.id}",
            payload={"cycle_id": cycle.id, "user_id": current.id, "event": "self_eval_submitted"},
        )

    return EvaluationView.model_validate(eva, from_attributes=True)


# ============ 写：上级评估 ============

@router.post("/users/{user_id}/superior-evaluation")
def submit_superior_evaluation(
    cycle_id: int,
    user_id: int,
    payload: EvaluationSubmit,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # 直属上级可做上级评估；HR（hrbp/super_admin）可代评——部分 Leader 需要 HR 支持，刻意保留该入口
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="员工不存在")
    if user_id == current.id:
        raise HTTPException(status_code=400, detail="不能给自己做上级评估（自评请用自评接口）")

    if not can_act_as_superior(current, target):
        raise HTTPException(status_code=403, detail="只有直属上级或 HR 才能做上级评估")

    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle or cycle.status != "in_progress":
        raise HTTPException(status_code=400, detail="周期不在进行中，无法提交上级评估")

    participant = session.exec(
        select(CycleParticipant).where(
            CycleParticipant.cycle_id == cycle_id,
            CycleParticipant.user_id == user_id,
        )
    ).first()
    if not participant:
        raise HTTPException(status_code=404, detail="该员工不在本周期的参与人列表")
    # 仅开启自评时才要求员工先完成自评；未开启自评的周期员工无法自评，直接跳过该前置
    if cycle.enable_self_eval and participant.status == "pending":
        raise HTTPException(status_code=400, detail="员工尚未完成自评")

    # 环节阻断：如果该员工有已审批的互评任务，必须全部提交完才能做上级评估
    from pms.database.models.peer import PeerEvaluation
    pending_peers = session.exec(
        select(PeerEvaluation).where(
            PeerEvaluation.cycle_id == cycle_id,
            PeerEvaluation.target_user_id == user_id,
            PeerEvaluation.status == "pending",
        )
    ).all()
    if pending_peers:
        raise HTTPException(
            status_code=400,
            detail=f"该员工还有 {len(pending_peers)} 位互评人未提交，请等互评完成后再做上级评估",
        )

    try:
        score = validate_perf_score(payload.perf_score)
        validate_value_grades(
            payload.value_belief_grade, payload.value_belief_example,
            payload.value_team_grade, payload.value_team_example,
            payload.value_growth_grade, payload.value_growth_example,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not payload.key_results or not payload.key_results.strip():
        raise HTTPException(status_code=400, detail="关键成果必填")

    eva = session.exec(
        select(Evaluation).where(
            Evaluation.cycle_id == cycle_id,
            Evaluation.user_id == user_id,
            Evaluation.eval_type == EvalType.SUPERIOR.value,
        )
    ).first()
    before = None
    if eva:
        before = {"perf_score": eva.perf_score}
        eva.perf_score = score
        eva.perf_level = derive_perf_level(score).value
        eva.value_belief_grade = payload.value_belief_grade
        eva.value_belief_example = payload.value_belief_example
        eva.value_team_grade = payload.value_team_grade
        eva.value_team_example = payload.value_team_example
        eva.value_growth_grade = payload.value_growth_grade
        eva.value_growth_example = payload.value_growth_example
        eva.key_results = payload.key_results
        eva.comment = payload.comment
        eva.evaluator_userid = current.wecom_userid
        eva.submitted_at = datetime.now(timezone.utc)
        eva.status = "submitted"
    else:
        eva = Evaluation(
            cycle_id=cycle_id,
            user_id=user_id,
            evaluator_userid=current.wecom_userid,
            eval_type=EvalType.SUPERIOR.value,
            perf_score=score,
            perf_level=derive_perf_level(score).value,
            value_belief_grade=payload.value_belief_grade,
            value_belief_example=payload.value_belief_example,
            value_team_grade=payload.value_team_grade,
            value_team_example=payload.value_team_example,
            value_growth_grade=payload.value_growth_grade,
            value_growth_example=payload.value_growth_example,
            key_results=payload.key_results,
            comment=payload.comment,
            submitted_at=datetime.now(timezone.utc),
            status="submitted",
        )
    session.add(eva)

    participant.status = ParticipantStatus.LEADER_DONE.value
    # 上级初评同时写入 final_* 作为校准起点
    participant.final_perf_score = score
    participant.final_perf_level = derive_perf_level(score).value
    participant.final_value_belief = payload.value_belief_grade
    participant.final_value_team = payload.value_team_grade
    participant.final_value_growth = payload.value_growth_grade
    session.add(participant)

    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="submit_superior_evaluation",
        resource_type="evaluation",
        resource_id=f"{cycle_id}:{user_id}",
        before=before,
        after={"perf_score": score, "value_belief": payload.value_belief_grade, "value_team": payload.value_team_grade, "value_growth": payload.value_growth_grade},
    )
    session.commit()
    session.refresh(eva)

    # 通知 HRBP
    hrbp_userids = get_hrbp_userids(session, target)
    if hrbp_userids:
        send_textcard_notification(
            target_userids=hrbp_userids,
            title="上级评估已完成",
            description=f"员工 {target.name} 的「{cycle.name}」上级评估已完成，请查看。",
            url=f"/leader/{cycle.id}/users/{target.id}",
            payload={"cycle_id": cycle.id, "user_id": target.id, "event": "superior_eval_submitted"},
        )

    return EvaluationView.model_validate(eva, from_attributes=True)
