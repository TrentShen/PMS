from __future__ import annotations

# 本地测试种子数据
# 用法：python -m pms.services.seed
# 作用：建 1 个部门 + 6 位用户（1 HR + 1 Leader + 4 员工），以及一个进行中的测试周期
from datetime import date

from loguru import logger
from sqlmodel import Session, select

from pms.database.models import (
    CycleParticipant,
    Department,
    Objective,
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
        dept = Department(wecom_dept_id=1, name="技术部", order_num=1)
        s.add(dept)
        s.commit()
        s.refresh(dept)

        # ---- 用户 ----
        users_spec = [
            # wecom_userid, name, role, leader_userid, position
            ("mock-hr", "赵 HR", "hrbp", None, "HRBP"),
            ("mock-leader", "王 Leader", "dept_leader", None, "技术负责人"),
            ("mock-alice", "张 Alice", "employee", "mock-leader", "高级工程师"),
            ("mock-bob", "李 Bob", "employee", "mock-leader", "工程师"),
            ("mock-carol", "孙 Carol", "employee", "mock-leader", "工程师"),
            ("mock-admin", "超级管理员", "super_admin", None, "IT"),
        ]
        for uid, name, role, leader, pos in users_spec:
            s.add(
                User(
                    wecom_userid=uid,
                    name=name,
                    role=role,
                    leader_userid=leader,
                    department_id=dept.id,
                    position=pos,
                    hired_at=date(2024, 1, 1),
                    status="active",
                )
            )
        s.commit()
        logger.info("用户 seed 完成：{} 条", len(users_spec))

        # ---- 部门负责人指向 Leader ----
        dept.leader_userid = "mock-leader"
        s.add(dept)

        # ---- 一个进行中的周期（方便进入系统就有东西看） ----
        cycle = PerformanceCycle(
            name="2025 下半年度绩效考核",
            start_date=date(2025, 7, 1),
            end_date=date(2025, 12, 31),
            status="in_progress",
            created_by="mock-hr",
        )
        s.add(cycle)
        s.commit()
        s.refresh(cycle)
        logger.info("周期创建：id={} name={}", cycle.id, cycle.name)

        # ---- 3 个员工加入参与人 + 写 3 条目标 ----
        alice, bob, carol = s.exec(
            select(User).where(User.wecom_userid.in_(["mock-alice", "mock-bob", "mock-carol"]))
        ).all()
        for u in (alice, bob, carol):
            s.add(
                CycleParticipant(
                    cycle_id=cycle.id,
                    user_id=u.id,
                    leader_userid_snapshot=u.leader_userid,
                    dept_name_snapshot=dept.name,
                    status="pending",
                )
            )
            # 3 条目标，权重 40+30+30
            objectives = [
                ("完成 V0.9 MVP 上线", "按期交付 7 大模块", "12 月底前全员使用", 40),
                ("代码质量", "单测覆盖率≥70%", "Ruff 零 warning", 30),
                ("文档完善", "架构与 API 文档齐全", "新人 1 天上手", 30),
            ]
            for i, (title, desc, m, w) in enumerate(objectives):
                s.add(
                    Objective(
                        cycle_id=cycle.id,
                        user_id=u.id,
                        title=title,
                        description=desc,
                        measure_criteria=m,
                        weight=w,
                        order_num=i,
                    )
                )

        s.commit()
        logger.info("Seed 完成：周期 {} + 3 位参与人 + 9 条目标", cycle.name)


if __name__ == "__main__":
    seed()
