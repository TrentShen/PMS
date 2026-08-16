from __future__ import annotations

# APScheduler 定时任务：提醒扫描 + 通讯录同步
from datetime import date, datetime, timedelta, timezone

from loguru import logger
from sqlmodel import Session, select

from pms.database.models.audit import NotificationLog
from pms.database.models.cycle import CycleParticipant, PerformanceCycle
from pms.database.models.enums import EvalType, ProbationPlanStatus
from pms.database.models.evaluation import Evaluation
from pms.database.models.feedback import FeedbackRecord
from pms.database.models.peer import PeerEvaluation, PeerInvitation
from pms.database.models.probation import ProbationPlan
from pms.database.models.user import User
from pms.database.session import engine
from pms.services.auth import is_fte
from pms.services.notification import (
    get_hrbp_userids,
    send_textcard_notification,
)

STAGE_LABELS = {
    "self_eval": "自评",
    "peer_confirm": "互评名单确认",
    "peer_eval": "互评",
    "superior_eval": "上级评估",
    "calibration": "绩效校准",
    "approval": "公司级审批",
    "feedback": "绩效反馈",
}


def _today() -> date:
    return date.today()


def _already_notified(s: Session, userid: str, title: str, today: date) -> bool:
    exists = s.exec(
        select(NotificationLog).where(
            NotificationLog.target_userid == userid,
            NotificationLog.title == title,
            NotificationLog.created_at >= datetime(today.year, today.month, today.day),
        )
    ).first()
    return exists is not None


def _role_side_reminders(s: Session, cycle: PerformanceCycle, stage_key: str) -> list[tuple[str, str, str]]:
    """角色侧待办催办：返回 (目标 wecom_userid, 描述, 跳转链接) 列表。

    环节的责任人往往不是参与人本人，参与人状态催办覆盖不到：
    - peer_confirm：互评名单待 Leader 审核
    - peer_eval：互评任务待评价人填写
    - superior_eval：上级评估未提交
    - feedback：面谈记录未填写（催上级）/ 已填写未确认（催员工）
    """
    reminders: list[tuple[str, str, str]] = []

    if stage_key == "peer_confirm" and cycle.enable_peer_eval:
        rows = s.exec(
            select(PeerInvitation, User)
            .join(User, User.id == PeerInvitation.invitee_user_id)
            .where(PeerInvitation.cycle_id == cycle.id, PeerInvitation.status == "pending")
        ).all()
        by_leader: dict[str, set[str]] = {}
        for _inv, invitee in rows:
            # Leader 自己的待审名单不计入"下属"（审核页 review-list 同样排除自己）
            if invitee.wecom_userid == invitee.leader_userid:
                continue
            if invitee.leader_userid:
                by_leader.setdefault(invitee.leader_userid, set()).add(invitee.name)
        for leader_userid, names in by_leader.items():
            ordered = sorted(names)
            shown = "、".join(ordered[:5]) + (" 等" if len(ordered) > 5 else "")
            reminders.append((
                leader_userid,
                f"「{cycle.name}」有 {len(ordered)} 名下属的互评名单待确认（{shown}），请尽快审核。",
                "/peer-review",
            ))

    elif stage_key == "peer_eval" and cycle.enable_peer_eval:
        rows = s.exec(
            select(PeerEvaluation, User)
            .join(User, User.id == PeerEvaluation.evaluator_user_id)
            .where(PeerEvaluation.cycle_id == cycle.id, PeerEvaluation.status == "pending")
        ).all()
        counts: dict[str, int] = {}
        for _pe, evaluator in rows:
            if is_fte(evaluator):
                counts[evaluator.wecom_userid] = counts.get(evaluator.wecom_userid, 0) + 1
        for userid, n in counts.items():
            reminders.append((
                userid,
                f"「{cycle.name}」你还有 {n} 条互评任务待评价，请尽快完成。",
                "/peer",
            ))

    elif stage_key == "superior_eval":
        rows = s.exec(
            select(CycleParticipant, User)
            .join(User, User.id == CycleParticipant.user_id)
            .where(CycleParticipant.cycle_id == cycle.id)
        ).all()
        submitted = set(s.exec(
            select(Evaluation.user_id).where(
                Evaluation.cycle_id == cycle.id,
                Evaluation.eval_type == EvalType.SUPERIOR.value,
                Evaluation.status == "submitted",
            )
        ).all())
        by_leader: dict[str, list[str]] = {}
        for p, u in rows:
            if p.user_id in submitted or not p.leader_userid_snapshot:
                continue
            by_leader.setdefault(p.leader_userid_snapshot, []).append(u.name)
        for leader_userid, names in by_leader.items():
            shown = "、".join(names[:5]) + (" 等" if len(names) > 5 else "")
            reminders.append((
                leader_userid,
                f"「{cycle.name}」你有 {len(names)} 名下属的上级评估未提交（{shown}），请尽快完成。",
                "/leader",
            ))

    elif stage_key == "feedback" and cycle.enable_feedback:
        records = s.exec(
            select(FeedbackRecord).where(FeedbackRecord.cycle_id == cycle.id)
        ).all()
        recorded_user_ids = {r.user_id for r in records}
        # 已填写但员工未确认：催员工确认/异议（批量取用户，避免循环内查库）
        pending_records = [r for r in records if r.confirm_status == "pending"]
        if pending_records:
            employee_map = {
                u.id: u
                for u in s.exec(
                    select(User).where(User.id.in_([r.user_id for r in pending_records]))
                ).all()
            }
            for r in pending_records:
                employee = employee_map.get(r.user_id)
                if employee and is_fte(employee):
                    reminders.append((
                        employee.wecom_userid,
                        f"「{cycle.name}」你的绩效反馈面谈记录待确认，请及时查看并确认。",
                        f"/feedback/{cycle.id}",
                    ))
        # 未填写面谈记录：催上级填写（链接直达第一位未填下属的填写页）
        rows = s.exec(
            select(CycleParticipant, User)
            .join(User, User.id == CycleParticipant.user_id)
            .where(CycleParticipant.cycle_id == cycle.id)
        ).all()
        by_leader: dict[str, list[tuple[int, str]]] = {}
        for p, u in rows:
            if p.user_id in recorded_user_ids or not p.leader_userid_snapshot:
                continue
            by_leader.setdefault(p.leader_userid_snapshot, []).append((u.id, u.name))
        for leader_userid, members in by_leader.items():
            names = [name for _, name in members]
            shown = "、".join(names[:5]) + (" 等" if len(names) > 5 else "")
            reminders.append((
                leader_userid,
                f"「{cycle.name}」你有 {len(names)} 名下属的反馈面谈记录未填写（{shown}），请尽快完成。",
                f"/feedback/{cycle.id}/{members[0][0]}",
            ))

    return reminders


def check_stage_reminders():
    """按 stage_json 配置的截止日期发送提醒（截止前3天/1天/当天）"""
    today = _today()
    with Session(engine) as s:
        cycles = s.exec(
            select(PerformanceCycle).where(PerformanceCycle.status == "in_progress")
        ).all()

        for cycle in cycles:
            if not cycle.stage_json:
                continue
            stages = cycle.stage_json

            for stage_key, label in STAGE_LABELS.items():
                end_key = f"{stage_key}_end"
                end_str = stages.get(end_key)
                if not end_str:
                    continue
                try:
                    end_date = date.fromisoformat(end_str)
                except ValueError:
                    continue

                days_left = (end_date - today).days
                if days_left not in (3, 1, 0):
                    continue

                # 标题带周期名：去重键是（人, 标题, 当天），多周期并行时互不吞提醒
                if days_left == 0:
                    title = f"「{cycle.name}」{label}今日截止"
                    content = f"「{cycle.name}」{label}环节今日截止，请尽快完成。"
                else:
                    title = f"「{cycle.name}」{label}即将截止"
                    content = f"「{cycle.name}」{label}环节将在 {days_left} 天后截止。"

                participants = s.exec(
                    select(CycleParticipant, User)
                    .join(User, User.id == CycleParticipant.user_id)
                    .where(
                        CycleParticipant.cycle_id == cycle.id,
                        CycleParticipant.status.in_(["pending", "self_done"]),
                    )
                ).all()

                sent_count = 0
                for _p, u in participants:
                    if not is_fte(u):
                        continue
                    if _already_notified(s, u.wecom_userid, title, today):
                        continue
                    send_textcard_notification(
                        target_userids=[u.wecom_userid],
                        title=title,
                        description=content,
                        url="/",
                        payload={"cycle_id": cycle.id, "stage": stage_key, "days_left": days_left},
                    )
                    sent_count += 1

                if sent_count:
                    logger.info("周期 {} / {} 截止提醒: {} 人", cycle.name, label, sent_count)

                # 角色侧催办：责任人不是参与人本人的环节（名单确认/互评填写/上级评估/反馈）
                # 标题带周期名：去重键是（人, 标题, 当天），多周期并行时互不吞提醒
                role_sent = 0
                role_title = (
                    f"「{cycle.name}」{label}催办" if days_left > 0 else f"「{cycle.name}」{label}今日截止催办"
                )
                for userid, rdesc, rurl in _role_side_reminders(s, cycle, stage_key):
                    if _already_notified(s, userid, role_title, today):
                        continue
                    send_textcard_notification(
                        target_userids=[userid],
                        title=role_title,
                        description=rdesc,
                        url=rurl,
                        payload={"cycle_id": cycle.id, "stage": stage_key, "days_left": days_left},
                    )
                    role_sent += 1
                if role_sent:
                    logger.info("周期 {} / {} 角色侧催办: {} 人", cycle.name, label, role_sent)


def check_deadline_reminders():
    """兜底：给 pending 人员发通用提醒"""
    today = _today()
    with Session(engine) as s:
        cycles = s.exec(
            select(PerformanceCycle).where(PerformanceCycle.status == "in_progress")
        ).all()
        for cycle in cycles:
            pending = s.exec(
                select(CycleParticipant, User)
                .join(User, User.id == CycleParticipant.user_id)
                .where(
                    CycleParticipant.cycle_id == cycle.id,
                    CycleParticipant.status == "pending",
                )
            ).all()
            sent_count = 0
            for _p, u in pending:
                if not is_fte(u):
                    continue
                title = f"「{cycle.name}」自评截止提醒"
                if _already_notified(s, u.wecom_userid, title, today):
                    continue
                send_textcard_notification(
                    target_userids=[u.wecom_userid],
                    title=title,
                    description=f"「{cycle.name}」自评尚未完成，请尽快提交。",
                    url="/",
                    payload={"cycle_id": cycle.id},
                )
                sent_count += 1
            if sent_count:
                logger.info("周期 {} 通用提醒 {} 人", cycle.name, sent_count)


def sync_contacts_daily():
    """每日 02:00 全量同步企微通讯录 + 人事字段"""
    from pms.api.v1.users import _enrich_users_hr_info, _sync_departments, _sync_users
    from pms.database.session import Session, engine
    with Session(engine) as s:
        try:
            _sync_departments(s)
            count = _sync_users(s)
            hr_count = _enrich_users_hr_info(s)
            logger.info("每日通讯录同步完成: {} 个用户, {} 个人事字段补充", count, hr_count)
        except Exception:
            logger.exception("每日通讯录同步失败")


def _add_months(d: date, months: int) -> date:
    """返回 date 加上指定月数后的日期，处理月末越界。"""
    total_months = d.month - 1 + months
    year = d.year + total_months // 12
    month = total_months % 12 + 1
    max_day = [31, 29 if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    day = min(d.day, max_day)
    return date(year, month, day)


def sync_probation_plans():
    """每日扫描试用期员工，自动创建试用期计划；临转正前更新状态为待评估。"""
    default_probation_months = 6
    pending_evaluation_days = 7

    with Session(engine) as s:
        try:
            # 1. 自动创建缺失的计划
            probation_users = s.exec(
                select(User).where(
                    User.employee_status == "probation",
                    User.status == "active",
                    User.employee_type == "full_time",
                )
            ).all()
            existing_user_ids = set(s.exec(select(ProbationPlan.user_id)).all())

            created = 0
            for user in probation_users:
                if user.id in existing_user_ids or not user.hired_at:
                    continue
                months = user.probation if user.probation else default_probation_months
                plan = ProbationPlan(
                    user_id=user.id,
                    start_date=user.hired_at,
                    end_date=_add_months(user.hired_at, months),
                    probation_months=months,
                    status=ProbationPlanStatus.DRAFT,
                )
                s.add(plan)
                created += 1

            if created:
                s.commit()
                logger.info("自动创建试用期计划: {} 人", created)

                # 通知员工计划已创建
                for user in probation_users:
                    if user.id in existing_user_ids or not user.hired_at:
                        continue
                    send_textcard_notification(
                        target_userids=[user.wecom_userid],
                        title="试用期计划已创建",
                        description="你的试用期计划已创建，请尽快填写试用期目标并提交审批。",
                        url=f"/probation/{user.id}",
                        payload={"user_id": user.id, "event": "plan_created"},
                    )

            # 2. 临转正前进入待评估状态
            today = _today()
            threshold = today + timedelta(days=pending_evaluation_days)
            in_progress_plans = s.exec(
                select(ProbationPlan).where(
                    ProbationPlan.status == ProbationPlanStatus.IN_PROGRESS,
                    ProbationPlan.end_date <= threshold,
                    ProbationPlan.end_date >= today,
                )
            ).all()

            pending_users: list[User] = []
            pending_count = 0
            for plan in in_progress_plans:
                plan.status = ProbationPlanStatus.PENDING_EVALUATION
                plan.updated_at = datetime.now(timezone.utc)
                s.add(plan)
                pending_count += 1
                user = s.get(User, plan.user_id)
                if user:
                    pending_users.append(user)

            if pending_count:
                s.commit()
                logger.info("试用期进入待评估状态: {} 人", pending_count)

                for user in pending_users:
                    recipients: list[User | str] = []
                    if user.leader_userid:
                        recipients.append(user.leader_userid)
                    recipients.extend(get_hrbp_userids(s, user))
                    if recipients:
                        send_textcard_notification(
                            target_userids=recipients,
                            title="试用期评估提醒",
                            description=f"员工 {user.name} 即将结束试用期，请尽快完成试用期评估。",
                            url=f"/probation/{user.id}",
                            payload={"user_id": user.id, "event": "pending_evaluation"},
                        )

        except Exception:
            logger.exception("试用期计划同步失败")


def probation_evaluation_reminder():
    """提醒上级对临转正员工做试用期评估。"""
    today = _today()
    with Session(engine) as s:
        try:
            pending_plans = s.exec(
                select(ProbationPlan, User)
                .join(User, ProbationPlan.user_id == User.id)
                .where(ProbationPlan.status == ProbationPlanStatus.PENDING_EVALUATION)
            ).all()

            sent_count = 0
            for plan, user in pending_plans:
                if not user.leader_userid:
                    continue
                title = "试用期评估提醒"
                if _already_notified(s, user.leader_userid, title, today):
                    continue
                send_textcard_notification(
                    target_userids=[user.leader_userid],
                    title=title,
                    description=f"员工 {user.name} 即将结束试用期，请尽快完成试用期评估。",
                    url=f"/probation/{user.id}",
                    payload={"probation_plan_id": plan.id, "user_id": user.id},
                )
                sent_count += 1

            if sent_count:
                logger.info("试用期评估提醒发送: {} 人", sent_count)
        except Exception:
            logger.exception("试用期评估提醒失败")


def start_scheduler():
    """启动定时任务调度器"""
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    # 每小时检查时间节点提醒
    scheduler.add_job(check_stage_reminders, "interval", hours=1, id="stage_remind")
    # 每天早上 9 点通用提醒
    scheduler.add_job(check_deadline_reminders, "cron", hour=9, id="deadline_remind")
    # 每日凌晨 2 点同步通讯录
    # 临时禁用：当前企微应用可见范围仅 HR 部门，同步会返回空列表并误标全员 inactive。
    # 待管理员在企微后台扩大应用可见范围后再开启。
    # scheduler.add_job(sync_contacts_daily, "cron", hour=2, id="contact_sync")
    # 每日凌晨 2:30 同步试用期计划并标记临转正员工
    scheduler.add_job(sync_probation_plans, "cron", hour=2, minute=30, id="probation_sync")
    # 每日早上 9 点提醒上级做试用期评估
    scheduler.add_job(probation_evaluation_reminder, "cron", hour=9, id="probation_eval_remind")
    scheduler.start()
    logger.info("APScheduler started: stage_remind + deadline_remind + probation_sync + probation_eval_remind")
