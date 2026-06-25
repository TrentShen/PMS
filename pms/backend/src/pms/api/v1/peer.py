from __future__ import annotations

# 互评全流程 API（PRD 3.4.5 + 匿名主动评价）
# 路径分组：
#   - 员工视角：邀请互评人 / 我的互评任务
#   - Leader 视角：审核互评名单 / 发起正式互评 / 看下属的互评汇总
#   - 任意员工：匿名主动评价
from datetime import datetime, timezone
from statistics import mean

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from pms.database.models.cycle import CycleParticipant, PerformanceCycle
from pms.database.models.peer import AnonymousFeedback, PeerEvaluation, PeerInvitation
from pms.database.models.user import User
from pms.database.session import get_session
from pms.services.auth import get_current_user
from pms.services.notification import send_textcard_notification
from pms.utils.audit import write_audit
from pms.utils.score import (
    derive_perf_level,
    validate_perf_score,
)

router = APIRouter(tags=["peer"])

MAX_INVITES = 5  # PRD 3.4.5：员工自选不超过 5 人


# ============ Schema ============

class PeerUserView(BaseModel):
    user_id: int
    name: str
    position: str | None
    status: str  # pending / approved / removed / submitted
    proposed_by: str | None = None


class InviteRequest(BaseModel):
    peer_user_ids: list[int]


class LeaderReviewRequest(BaseModel):
    # Leader 最终确认：add_user_ids 会被加入（并标 approved），
    # remove_user_ids 对应的候选会被标 removed；然后批量将剩余 pending 转 approved。
    add_user_ids: list[int] = []
    remove_user_ids: list[int] = []


class PeerSubmit(BaseModel):
    perf_score: float
    # 价值观三维度（每个都是 jia/yi/bing）
    value_belief_grade: str
    value_belief_example: str | None = None
    value_team_grade: str
    value_team_example: str | None = None
    value_growth_grade: str
    value_growth_example: str | None = None
    comment: str | None = None


class AnonymousFeedbackSubmit(BaseModel):
    target_user_id: int
    perf_score: float | None = None
    value_grade: str | None = None
    comment: str


# ============ 员工侧：邀请互评人 ============

@router.get("/cycles/{cycle_id}/peer/candidates", response_model=list[PeerUserView])
def list_my_peer_candidates(
    cycle_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # 返回"我已邀请 / Leader 已加的"互评人列表
    rows = session.exec(
        select(PeerInvitation, User)
        .join(User, User.id == PeerInvitation.peer_user_id)
        .where(
            PeerInvitation.cycle_id == cycle_id,
            PeerInvitation.invitee_user_id == current.id,
        )
    ).all()
    return [
        PeerUserView(
            user_id=inv.peer_user_id,
            name=u.name,
            position=u.position,
            status=inv.status,
            proposed_by=inv.proposed_by,
        )
        for inv, u in rows
    ]


@router.post("/cycles/{cycle_id}/peer/invite", response_model=list[PeerUserView])
def invite_peers(
    cycle_id: int,
    payload: InviteRequest,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # 员工提交/更新自己的互评人候选名单
    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle or cycle.status != "in_progress":
        raise HTTPException(status_code=400, detail="周期不在进行中")
    if not cycle.enable_peer_eval:
        raise HTTPException(status_code=400, detail="当前周期未开启互评")

    # 必须在参与人列表里
    participant = session.exec(
        select(CycleParticipant).where(
            CycleParticipant.cycle_id == cycle_id,
            CycleParticipant.user_id == current.id,
        )
    ).first()
    if not participant:
        raise HTTPException(status_code=403, detail="你不是本周期的参与人")

    # PRD 3.4.4：互评名单在自评完成后才能提交
    if participant.status == "pending":
        raise HTTPException(status_code=400, detail="请先完成自评，再选互评人")

    # 去重、不能选自己
    ids = list({uid for uid in payload.peer_user_ids if uid != current.id})
    if len(ids) > MAX_INVITES:
        raise HTTPException(status_code=400, detail=f"互评人数量不能超过 {MAX_INVITES}")

    # 员工侧策略：每次覆盖"proposed_by=employee"的记录，不碰 Leader 新增的
    # 1) 已经 approved 的（Leader 审核完成）不允许再改
    existing = session.exec(
        select(PeerInvitation).where(
            PeerInvitation.cycle_id == cycle_id,
            PeerInvitation.invitee_user_id == current.id,
        )
    ).all()
    approved_ids = [inv.peer_user_id for inv in existing if inv.status == "approved"]
    if approved_ids:
        raise HTTPException(
            status_code=400, detail="互评名单已由上级确认，无法再修改"
        )

    # 2) 全部 employee-proposed 的 pending/removed 先删，按新名单重建
    for inv in existing:
        if inv.proposed_by == "employee":
            session.delete(inv)
    session.flush()

    for uid in ids:
        user = session.get(User, uid)
        if not user:
            continue
        session.add(
            PeerInvitation(
                cycle_id=cycle_id,
                invitee_user_id=current.id,
                peer_user_id=uid,
                status="pending",
                proposed_by="employee",
            )
        )

    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="invite_peers",
        resource_type="peer_invitation",
        resource_id=f"{cycle_id}:{current.id}",
        after={"peer_user_ids": ids},
    )
    session.commit()

    return list_my_peer_candidates(cycle_id, session=session, current=current)


# ============ Leader 侧：审核 & 发起正式互评 ============

@router.get(
    "/cycles/{cycle_id}/users/{user_id}/peer/pending",
    response_model=list[PeerUserView],
)
def list_pending_peers_for_review(
    cycle_id: int,
    user_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # Leader 或 HR 看待审核名单
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="员工不存在")
    is_leader = target.leader_userid == current.wecom_userid
    is_admin = current.role in ("hrbp", "super_admin", "dept_leader", "direct_leader")
    if not (is_leader or is_admin):
        raise HTTPException(status_code=403, detail="无权查看")

    rows = session.exec(
        select(PeerInvitation, User)
        .join(User, User.id == PeerInvitation.peer_user_id)
        .where(
            PeerInvitation.cycle_id == cycle_id,
            PeerInvitation.invitee_user_id == user_id,
        )
    ).all()
    return [
        PeerUserView(
            user_id=inv.peer_user_id,
            name=u.name,
            position=u.position,
            status=inv.status,
            proposed_by=inv.proposed_by,
        )
        for inv, u in rows
    ]


@router.post("/cycles/{cycle_id}/users/{user_id}/peer/approve")
def approve_peer_list(
    cycle_id: int,
    user_id: int,
    payload: LeaderReviewRequest,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # Leader 审核：增删候选后一键发起正式互评
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="员工不存在")
    is_leader = target.leader_userid == current.wecom_userid
    is_admin = current.role in ("hrbp", "super_admin", "dept_leader", "direct_leader")
    if not (is_leader or is_admin):
        raise HTTPException(status_code=403, detail="无权审核")

    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle or cycle.status != "in_progress":
        raise HTTPException(status_code=400, detail="周期不在进行中")
    if not cycle.enable_peer_eval:
        raise HTTPException(status_code=400, detail="当前周期未开启互评")

    # 删除
    if payload.remove_user_ids:
        removes = session.exec(
            select(PeerInvitation).where(
                PeerInvitation.cycle_id == cycle_id,
                PeerInvitation.invitee_user_id == user_id,
                PeerInvitation.peer_user_id.in_(payload.remove_user_ids),
            )
        ).all()
        for inv in removes:
            if inv.status == "approved":
                continue  # 已批准的不再改（防止已经填了评价被改掉）
            inv.status = "removed"
            session.add(inv)

    # Leader 新增
    existing_ids = {
        inv.peer_user_id
        for inv in session.exec(
            select(PeerInvitation).where(
                PeerInvitation.cycle_id == cycle_id,
                PeerInvitation.invitee_user_id == user_id,
            )
        ).all()
    }
    for uid in payload.add_user_ids:
        if uid == user_id or uid in existing_ids:
            continue
        if not session.get(User, uid):
            continue
        session.add(
            PeerInvitation(
                cycle_id=cycle_id,
                invitee_user_id=user_id,
                peer_user_id=uid,
                status="approved",
                proposed_by="leader",
            )
        )

    # 把所有剩余 pending 标 approved，并建立 PeerEvaluation 任务
    session.flush()
    all_invs = session.exec(
        select(PeerInvitation).where(
            PeerInvitation.cycle_id == cycle_id,
            PeerInvitation.invitee_user_id == user_id,
        )
    ).all()
    approved_count = 0
    for inv in all_invs:
        if inv.status in ("pending", "approved"):
            if inv.status == "pending":
                inv.status = "approved"
                session.add(inv)
            # 创建正式互评任务（若已存在则跳过，避免重复键）
            exists = session.exec(
                select(PeerEvaluation).where(
                    PeerEvaluation.cycle_id == cycle_id,
                    PeerEvaluation.target_user_id == user_id,
                    PeerEvaluation.evaluator_user_id == inv.peer_user_id,
                )
            ).first()
            if not exists:
                session.add(
                    PeerEvaluation(
                        cycle_id=cycle_id,
                        target_user_id=user_id,
                        evaluator_user_id=inv.peer_user_id,
                        status="pending",
                    )
                )
                approved_count += 1

    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="approve_peer_list",
        resource_type="peer_invitation",
        resource_id=f"{cycle_id}:{user_id}",
        after={
            "added": payload.add_user_ids,
            "removed": payload.remove_user_ids,
            "approved_tasks": approved_count,
        },
    )
    session.commit()

    # 通知所有被确认的互评人
    approved_peer_user_ids = [
        inv.peer_user_id for inv in all_invs if inv.status == "approved"
    ]
    if approved_peer_user_ids:
        peer_users = session.exec(
            select(User).where(User.id.in_(approved_peer_user_ids))
        ).all()
        notify_userids = [u.wecom_userid for u in peer_users if u.wecom_userid]
        if notify_userids:
            send_textcard_notification(
                target_userids=notify_userids,
                title="你被邀请参与互评",
                description=f"你已被邀请为 {target.name} 的「{cycle.name}」互评人，请尽快完成评价。",
                url="/peer/my-tasks",
                payload={"cycle_id": cycle.id, "target_user_id": target.id, "event": "peer_invitation_approved"},
            )

    return {
        "approved_tasks": approved_count,
        "total_peers": len([inv for inv in all_invs if inv.status == "approved"]),
    }


# ============ 评价人视角：我的互评任务 ============

@router.get("/peer/my-tasks")
def list_my_peer_tasks(
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # 返回所有"需要我评价别人"的任务
    rows = session.exec(
        select(PeerEvaluation, User, PerformanceCycle)
        .join(User, User.id == PeerEvaluation.target_user_id)
        .join(PerformanceCycle, PerformanceCycle.id == PeerEvaluation.cycle_id)
        .where(
            PeerEvaluation.evaluator_user_id == current.id,
            PerformanceCycle.status == "in_progress",
        )
    ).all()
    return [
        {
            "id": pe.id,
            "cycle_id": pe.cycle_id,
            "cycle_name": cycle.name,
            "target_user_id": pe.target_user_id,
            "target_name": target.name,
            "target_position": target.position,
            "status": pe.status,
            "submitted_at": pe.submitted_at.isoformat() if pe.submitted_at else None,
        }
        for pe, target, cycle in rows
    ]


@router.post("/peer/tasks/{task_id}/submit")
def submit_peer_evaluation(
    task_id: int,
    payload: PeerSubmit,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    task = session.get(PeerEvaluation, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.evaluator_user_id != current.id:
        raise HTTPException(status_code=403, detail="不是你的互评任务")

    cycle = session.get(PerformanceCycle, task.cycle_id)
    if not cycle or cycle.status != "in_progress":
        raise HTTPException(status_code=400, detail="周期不在进行中")
    if not cycle.enable_peer_eval:
        raise HTTPException(status_code=400, detail="当前周期未开启互评")

    try:
        score = validate_perf_score(payload.perf_score)
        from pms.utils.score import validate_value_grades
        validate_value_grades(
            payload.value_belief_grade, payload.value_belief_example,
            payload.value_team_grade, payload.value_team_example,
            payload.value_growth_grade, payload.value_growth_example,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    before = {"perf_score": task.perf_score, "status": task.status}
    task.perf_score = score
    task.perf_level = derive_perf_level(score).value
    task.value_belief_grade = payload.value_belief_grade
    task.value_belief_example = payload.value_belief_example
    task.value_team_grade = payload.value_team_grade
    task.value_team_example = payload.value_team_example
    task.value_growth_grade = payload.value_growth_grade
    task.value_growth_example = payload.value_growth_example
    task.comment = payload.comment
    task.submitted_at = datetime.now(timezone.utc)
    task.status = "submitted"
    session.add(task)

    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="submit_peer_evaluation",
        resource_type="peer_evaluation",
        resource_id=str(task_id),
        before=before,
        after={
            "perf_score": score,
            "value_belief_grade": payload.value_belief_grade,
            "value_team_grade": payload.value_team_grade,
            "value_growth_grade": payload.value_growth_grade,
        },
    )
    session.commit()

    # 通知被评人直属上级
    target = session.get(User, task.target_user_id)
    if target and target.leader_userid:
        send_textcard_notification(
            target_userids=[target.leader_userid],
            title="互评已完成",
            description=f"你团队成员 {target.name} 的「{cycle.name}」互评已有新提交，请查看汇总。",
            url=f"/leader/{cycle.id}/users/{target.id}",
            payload={"cycle_id": cycle.id, "user_id": target.id, "event": "peer_evaluation_submitted"},
        )

    return {"status": "submitted", "task_id": task_id}


# ============ Leader/HR 视角：某员工收到的互评汇总 ============

@router.get("/cycles/{cycle_id}/users/{user_id}/peer/summary")
def get_peer_summary(
    cycle_id: int,
    user_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # 汇总某位员工收到的所有互评（评分+评语）
    # 仅 Leader / HR / 超管可见（PRD 3.4.5：被评人本人不可见）
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="员工不存在")
    is_leader = target.leader_userid == current.wecom_userid
    is_admin = current.role in ("hrbp", "super_admin", "dept_leader", "direct_leader")
    if not (is_leader or is_admin):
        raise HTTPException(status_code=403, detail="被评人本人不可见自己收到的互评")

    rows = session.exec(
        select(PeerEvaluation).where(
            PeerEvaluation.cycle_id == cycle_id,
            PeerEvaluation.target_user_id == user_id,
        )
    ).all()
    submitted = [r for r in rows if r.status == "submitted" and r.perf_score is not None]

    # 聚合：平均分、价值观分布、评语列表（不展示评价人姓名，避免互相指认）
    summary = {
        "total": len(rows),
        "submitted": len(submitted),
        "avg_perf_score": round(mean([r.perf_score for r in submitted]), 2) if submitted else None,
        "value_grade_dist": {},
        "comments": [],
    }
    for r in submitted:
        # 价值观三维度分布统计（按维度独立计数）
        for dim in ("belief", "team", "growth"):
            grade = getattr(r, f"value_{dim}_grade", None)
            if grade:
                key = f"{dim}_{grade}"
                summary["value_grade_dist"][key] = summary["value_grade_dist"].get(key, 0) + 1
        if r.comment:
            summary["comments"].append(
                {
                    "perf_score": r.perf_score,
                    "value_belief_grade": r.value_belief_grade,
                    "value_team_grade": r.value_team_grade,
                    "value_growth_grade": r.value_growth_grade,
                    "comment": r.comment,
                }
            )

    # 手松手紧：统计该周期内每位评价人的打分均值 vs 全局均值
    rater_stats = []
    if submitted:
        from statistics import mean as stat_mean
        # 该周期内所有已提交的互评（不限于当前被评人）
        all_evals = session.exec(
            select(PeerEvaluation).where(
                PeerEvaluation.cycle_id == cycle_id,
                PeerEvaluation.status == "submitted",
                PeerEvaluation.perf_score is not None,
            )
        ).all()
        global_avg = stat_mean([e.perf_score for e in all_evals]) if all_evals else 0

        # 按评价人分组统计
        from collections import defaultdict
        by_rater: dict[int, list[float]] = defaultdict(list)
        for e in all_evals:
            by_rater[e.evaluator_user_id].append(e.perf_score)

        for idx, (_rater_id, scores) in enumerate(by_rater.items(), 1):
            rater_avg = stat_mean(scores)
            diff = rater_avg - global_avg
            if diff > 0.5:
                bias = "偏松"
            elif diff < -0.5:
                bias = "偏紧"
            else:
                bias = "正常"
            rater_stats.append({
                "label": f"评价人{idx}",
                "count": len(scores),
                "avg": round(rater_avg, 2),
                "global_avg": round(global_avg, 2),
                "diff": round(diff, 2),
                "bias": bias,
            })
        # 按偏差程度排序（偏松/偏紧的放前面）
        rater_stats.sort(key=lambda x: abs(x["diff"]), reverse=True)

    summary["rater_bias"] = rater_stats

    # 额外查：匿名主动评价（仅 HR/部门 Leader 可见；**直属上级不可见**）
    can_see_anon = current.role in ("hrbp", "super_admin", "dept_leader")
    anon_list = []
    if can_see_anon:
        anons = session.exec(
            select(AnonymousFeedback).where(
                AnonymousFeedback.cycle_id == cycle_id,
                AnonymousFeedback.target_user_id == user_id,
            )
        ).all()
        anon_list = [
            {
                "perf_score": a.perf_score,
                "value_grade": a.value_grade,
                "comment": a.comment,
                "created_at": a.created_at.isoformat(),
            }
            for a in anons
        ]
    summary["anonymous_feedback"] = anon_list if can_see_anon else None

    return summary


# ============ 匿名主动评价 ============

@router.post("/cycles/{cycle_id}/anonymous-feedback")
def submit_anonymous_feedback(
    cycle_id: int,
    payload: AnonymousFeedbackSubmit,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # 任何员工都可以对任意在职同事发起匿名评价
    # 不允许评自己
    if payload.target_user_id == current.id:
        raise HTTPException(status_code=400, detail="不能评价自己")
    target = session.get(User, payload.target_user_id)
    if not target or target.status != "active":
        raise HTTPException(status_code=404, detail="目标员工不存在或已停用")

    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle or cycle.status != "in_progress":
        raise HTTPException(status_code=400, detail="周期不在进行中")

    if payload.perf_score is not None:
        try:
            validate_perf_score(payload.perf_score)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    if not payload.comment or not payload.comment.strip():
        raise HTTPException(status_code=400, detail="评语必填")

    fb = AnonymousFeedback(
        cycle_id=cycle_id,
        target_user_id=payload.target_user_id,
        author_user_id=current.id,
        perf_score=payload.perf_score,
        value_grade=payload.value_grade,
        comment=payload.comment,
    )
    session.add(fb)
    # 审计仅记 operator 为当前人；resource_id 不含目标，避免审计里能反向追踪
    # （若合规要求可追踪，可以在 after 里加上）
    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="submit_anonymous_feedback",
        resource_type="anonymous_feedback",
        resource_id=str(cycle_id),
        after={"has_score": payload.perf_score is not None},
    )
    session.commit()
    return {"status": "ok"}
