from __future__ import annotations

# 本地 UAT 测试种子数据
# 用法：python -m pms.services.seed
# 作用：创建 2 个部门 + 8 位用户（1 CEO + 1 HR + 2 Leader + 4 员工 + 1 超管）
#       以及一个配置完整的测试周期和参与人/目标
from datetime import date, datetime, timezone

from loguru import logger
from sqlmodel import Session, select

from pms.database.models import (
    CycleParticipant,
    Department,
    Objective,
    ObjectiveCycle,
    PerformanceCycle,
    User,
)
from pms.database.session import engine


def seed() -> None:
    with Session(engine) as s:
        # 幂等：已有数据就退出
        if s.exec(select(User).limit(1)).first():
            logger.info("已存在用户数据，跳过 seed")
            return

        # ---- 部门 ----
        tech_dept = Department(wecom_dept_id=1, name="技术部", order_num=1)
        prod_dept = Department(wecom_dept_id=2, name="产品部", order_num=2)
        hr_dept = Department(wecom_dept_id=3, name="人力资源部", order_num=3)
        s.add_all([tech_dept, prod_dept, hr_dept])
        s.commit()
        for d in (tech_dept, prod_dept, hr_dept):
            s.refresh(d)

        # ---- 用户 ----
        # 设计汇报关系：
        #   CEO 管理 Leader 和 HR
        #   Leader 管理各自部门员工
        users_spec = [
            # (wecom_userid, name, role, leader_userid, position, department_id)
            ("mock-ceo", "陈 CEO", "super_admin", None, "首席执行官", None),
            ("mock-hr", "赵 HR", "hrbp", "mock-ceo", "HRBP", hr_dept.id),
            ("mock-tech-leader", "王 Leader", "dept_leader", "mock-ceo", "技术负责人", tech_dept.id),
            ("mock-prod-leader", "刘 Leader", "dept_leader", "mock-ceo", "产品负责人", prod_dept.id),
            ("mock-alice", "张 Alice", "employee", "mock-tech-leader", "高级工程师", tech_dept.id),
            ("mock-bob", "李 Bob", "employee", "mock-tech-leader", "工程师", tech_dept.id),
            ("mock-carol", "孙 Carol", "employee", "mock-prod-leader", "产品经理", prod_dept.id),
            ("mock-david", "周 David", "employee", "mock-prod-leader", "产品专员", prod_dept.id),
        ]
        for uid, name, role, leader, pos, dept_id in users_spec:
            s.add(
                User(
                    wecom_userid=uid,
                    name=name,
                    role=role,
                    leader_userid=leader,
                    department_id=dept_id,
                    position=pos,
                    hired_at=date(2024, 1, 1),
                    status="active",
                    synced_at=datetime.now(timezone.utc),
                )
            )
        s.commit()
        logger.info("用户 seed 完成：{} 条", len(users_spec))

        # ---- 部门负责人指向各自 Leader ----
        tech_dept.leader_userid = "mock-tech-leader"
        prod_dept.leader_userid = "mock-prod-leader"
        hr_dept.leader_userid = "mock-hr"
        s.add_all([tech_dept, prod_dept, hr_dept])

        # ---- 目标周期：2025 下半年 ----
        objective_cycle = ObjectiveCycle(
            name="2025 下半年度目标（UAT）",
            start_date=date(2025, 7, 1),
            end_date=date(2025, 12, 31),
            status="active",
            created_by="mock-hr",
        )
        s.add(objective_cycle)
        s.commit()
        s.refresh(objective_cycle)
        logger.info("目标周期创建：id={} name={}", objective_cycle.id, objective_cycle.name)

        # ---- 绩效评估周期：2025 下半年 ----
        cycle = PerformanceCycle(
            name="2025 下半年度绩效考核（UAT）",
            start_date=date(2025, 7, 1),
            end_date=date(2025, 12, 31),
            status="in_progress",
            objective_cycle_id=objective_cycle.id,
            enable_self_eval=True,
            enable_peer_eval=True,
            enable_calibration=True,
            enable_feedback=True,
            stage_json={
                "self_eval": {"start": "2025-12-01", "end": "2025-12-10", "name": "员工自评"},
                "peer_eval": {"start": "2025-12-11", "end": "2025-12-15", "name": "互评"},
                "leader_eval": {"start": "2025-12-16", "end": "2025-12-20", "name": "上级评估"},
                "calibration": {"start": "2025-12-21", "end": "2025-12-23", "name": "校准"},
                "approval": {"start": "2025-12-24", "end": "2025-12-25", "name": "审批"},
                "feedback": {"start": "2025-12-26", "end": "2025-12-28", "name": "反馈面谈"},
                "publish": {"start": "2025-12-29", "end": "2025-12-31", "name": "结果发布"},
            },
            exclusion_rules={
                "exclude_dept_ids": [],
                "exclude_positions": [],
                "exclude_levels": [],
                "exclude_entry_after": None,
                "exclude_status": ["resigned"],
            },
            created_by="mock-hr",
        )
        s.add(cycle)
        s.commit()
        s.refresh(cycle)
        logger.info("绩效周期创建：id={} name={}", cycle.id, cycle.name)

        # ---- 4 个员工加入参与人 + 写目标 ----
        employee_users = s.exec(
            select(User).where(User.role == "employee")
        ).all()
        dept_map = {tech_dept.id: tech_dept.name, prod_dept.id: prod_dept.name}
        objectives_template = [
            ("核心项目交付", "按期高质量完成负责模块", "里程碑全部达成", 40),
            ("协作与沟通", "跨团队协作效率", "无重大协作投诉", 30),
            ("能力提升", "学习新技术/方法并落地", "有具体落地案例", 30),
        ]
        for u in employee_users:
            dept_name = dept_map.get(u.department_id, "未知部门")
            s.add(
                CycleParticipant(
                    cycle_id=cycle.id,
                    user_id=u.id,
                    leader_userid_snapshot=u.leader_userid,
                    dept_name_snapshot=dept_name,
                    status="pending",
                )
            )
            for i, (title, desc, m, w) in enumerate(objectives_template):
                s.add(
                    Objective(
                        objective_cycle_id=objective_cycle.id,
                        user_id=u.id,
                        title=title,
                        description=desc,
                        measure_criteria=m,
                        weight=w,
                        order_num=i,
                        status="approved",
                    )
                )

        s.commit()
        logger.info(
            "Seed 完成：{} 个部门 + {} 位用户 + 周期 {} + {} 位参与人 + {} 条目标",
            3,
            len(users_spec),
            cycle.name,
            len(employee_users),
            len(employee_users) * len(objectives_template),
        )


if __name__ == "__main__":
    seed()
