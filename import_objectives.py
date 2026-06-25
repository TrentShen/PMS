import pymysql
from datetime import date

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3307,
    "user": "pms",
    "password": "Pms_Prod_2024_Secure",
    "database": "pms",
    "charset": "utf8mb4",
}

DATA = [
  {
    "name": "黄丽仙",
    "dept": "财务部",
    "position": "出纳",
    "wecom_userid": "huanglixian",
    "objectives": [
      {"title": "财务报告与审计、税务管理", "weight": 40, "order_num": 1, "description": "1、统计局以及其他政府月报、年报的数据填写工作，确保对外报送数据的准确性与及时性\n2、完成各公司所得税汇算清缴申报，税务合规\n3、协助2025年各公司审计报告的出具，保障公司财务信息的合规披露\n4、核算方面，能够识别核算风险和潜在问题并对应解决，包括不限于收入成本分客户和项目，公司盈利预测；税务方面：能够识别税务风险和潜在问题并对应解决，包括不限于：税账问题以及各项税务成本的提前管理。"},
      {"title": "经营分析与预决算管理", "weight": 30, "order_num": 2, "description": "1、按时出具经营数据分析报告\n2、完成项目收入成本费用核算\n3、编制年度财务预决算，合理税务筹划\n4、日常的合同风险审核"},
      {"title": "授信和融资", "weight": 20, "order_num": 3, "description": "1、做好各项资金的收取与支出管理\n2、做资金预算管理以及成本控制计划\n3、协助完成银行贷款授信申请/提款/续贷\n4、支持股权融资"},
      {"title": "个人发展", "weight": 10, "order_num": 4, "description": "1、学习使用AI相关工具辅助财务工作，简化重复性工作，提升数字化办公能力，至少完成一项日常工作的ai提效\n2、专业提升方面，持续学习会计准则和税法更新，考取税务师证书"}
    ]
  },
  {
    "name": "张琼艳",
    "dept": "财务管理",
    "position": "资金管理专员",
    "wecom_userid": "zhangqiongyan",
    "objectives": [
      {"title": "支付和费用", "weight": 45, "order_num": 1, "description": "确保流程合规、审批流规范，实现内部报销与付款流程100%闭环管理，每月按时输出费用报销分摊表，分析差旅费用数据，确保费用归属清晰；优化报销审批，实现几乎线上留痕，审批时效提升10%；闲置资金安全增值运营，提高闲置资金利用率；\n针对具体业务场景识别风险、提供财务建议，包括不限于合规、风险管控、费用节约等。"},
      {"title": "海外业务", "weight": 25, "order_num": 2, "description": "负责香港子公司全部业务 包括不限于财务报表、审计、年审、银行账户、收入及费用管理；支持香港、开曼财务事务工作，保障海外业务运营顺畅；\n确保境外日常收付款、公司往来款调拨零差错，付款及时率高。"},
      {"title": "研发资源治理", "weight": 20, "order_num": 3, "description": "联合研发费用云资源下的云账号台账建立；统筹研发云账号体系并具体关联项目成本；固定资产服务器和算力设备管理，包括不限于深入业务管理流程，对应出具财务核算规则；\n识别闲置资源、高耗资源，协同技术团队优化配置。"},
      {"title": "个人拓展", "weight": 10, "order_num": 4, "description": "学习使用AI相关工具辅助财务工作，简化重复性工作，提升数字化办公能力，至少完成一项日常工作的ai提效。"}
    ]
  },
  {
    "name": "蒯伟康",
    "dept": "研发/AI平台/应用开发/后端开发",
    "position": "研发工程师",
    "wecom_userid": "kuaishengkang",
    "objectives": [
      {"title": "新MOI后端模块开发", "weight": 50, "order_num": 1, "description": "基于 moi-core 完成 moi-backend 各业务模块的开发与上线。\n\n4分标准：\n1. 完成分配的后端模块开发（数据导入导出、连接器管理等），按期交付\n2. 代码质量达标，无严重 bug，通过 code review\n3. 核心模块有完整的集成测试覆盖\n\n5分标准：4分基础上\n1. 主动进行架构优化，提升模块性能与可扩展性\n2. 输出模块设计文档，沉淀到团队知识库"},
      {"title": "客户项目交付", "weight": 30, "order_num": 2, "description": "参与客户项目的后端开发与交付。\n\n4分标准：\n1. 按期按质完成客户项目中的后端需求开发\n2. 项目交付过程中无阻塞性问题\n\n5分标准：4分基础上\n1. 从客户项目中抽取可复用的业务模块，降低后续项目启动成本\n2. 能独立对接客户技术需求，减少上级介入"},
      {"title": "后端模块组件化与复用", "weight": 10, "order_num": 3, "description": "将已开发的后端模块抽象为可复用组件，提升项目交付效率。\n\n4分标准：\n1. 将已开发的后端模块（连接器、导入导出等）抽象为可复用组件，新项目可直接接入\n2. 模块具备独立测试能力，不依赖完整环境即可验证\n\n5分标准：4分基础上\n1. 新客户项目后端模块接入周期缩短 50%\n2. 建立后端模块接入文档与使用规范，其他开发者可自助接入"},
      {"title": "AI 辅助研发效率提升", "weight": 10, "order_num": 4, "description": "将 AI 工具深度融入日常开发流程，提升研发效率。\n\n4分标准：\n1. 后端代码 AI 编写比例达到 80%\n2. 参与共建 MOI 研发知识库，沉淀后端开发规范与最佳实践\n\n5分标准：4分基础上\n1. AI 代码编写比例达到 90%\n2. 总结 AI 辅助后端开发的工作流与提效方法，在团队内分享推广"}
    ]
  },
  {
    "name": "沈康棣",
    "dept": "项目交付与支持",
    "position": "项目开发工程师",
    "wecom_userid": "shenkangdi",
    "objectives": [
      {"title": "确保项目准时、高质量落地", "weight": 30, "order_num": 1, "description": "优化项目交付流程，提升资源利用率，确保项目 100% 按期完成。\n5分：\n1. 完成2个重点项目的全周期交付，项目验收通过率达到 100%。\n2. 严格控制交付周期，将平均交付时长较上一年度缩短 10%。\n3. 交付过程中的重大事故发生率为0。\n\n4分：\n1. 完成1个重点项目的全周期交付，项目验收通过率达到 95%。\n2. 严格控制交付周期，在客户能接受的范围内交付不延期。3. 交付过程中的重大事故发生率为0。"},
      {"title": "提升响应速度与系统稳定性", "weight": 30, "order_num": 2, "description": "建立高效的售后/二次支持体系，保障生产系统平稳运行。\n5分:\n1. 负责区域/客户的故障响应时间达标率不低于 98%，按维保确保修复时间。\n2.针对高频问题建立自动化巡检或监控机制，避免人为触发的生产事件。\n3.实现生产环境组件的高可用配置，可用性达到 99.9%。\n4分：\n1. 负责区域/客户的故障响应时间达标率不低于 90%，按维保确保修复时间。\n2.针对高频问题建立自动化巡检或监控机制，避免人为触发的生产事件。\n3.实现生产环境组件的高可用配置，可用性达到 90%。"},
      {"title": "客户满意度与关系维护维度", "weight": 20, "order_num": 3, "description": "提升客户服务体验，通过专业支持驱动二次需求转化。\n\n5分：\n1.年度客户满意度评分不低于 4.5。\n2.可独立组织并完成 1 场针对客户的技术培训或产品宣贯，提升客户自主运维能力。\n3. 深入挖掘交付过程中的潜在需求，成功转化增补合同或二期项目线索。\n\n4分：\n1.年度客户满意度评分不低于 4。\n2.可组织并完成 1 场针对客户的技术培训或产品宣贯，提升客户自主运维能力。"},
      {"title": "沉淀交付资产，减少重复劳动，实现部门能力的“工具化”与“标准化”。", "weight": 20, "order_num": 4, "description": "5分:\n1. 沉淀 2 份标准化交付文档（《MO,MOI-core部署手册》、《常见故障排查手册》）。\n2.开发或优化 1 套自动化交付工具（基于 Helm的自动化部署脚本），将重复性手工操作降低 30%。"}
    ]
  },
  {
    "name": "王莺瑛",
    "dept": "市场",
    "position": "市场运营",
    "wecom_userid": "wangyingying",
    "objectives": [
      {"title": "海外产品运营与市场推广", "weight": 30, "order_num": 1, "description": "海外宣传渠道建设：搭建至少2个海外核心渠道，完成品牌基础内容矩阵，吸引至少100粉丝；\nSaaS产品上线推广：制定产品对外发布计划（GTM Plan），完成海外联合发布；"},
      {"title": "市场渠道构建与技术影响力打造", "weight": 40, "order_num": 2, "description": "技术影响力打造：国内外KOL名单整理，建联，完成至少3-5人初步响应；\n战略合作伙伴品牌曝光：深化合作伙伴（英伟达、软通等），增强与合作伙伴联合曝光，至少2篇PR，1篇英伟达的博客；"},
      {"title": "销售及合作伙伴支撑", "weight": 20, "order_num": 3, "description": "合作伙伴联合物料：为合作伙伴落地方案提供市场支撑材料；\n销售赋能内容：标准化销售支持材料，deck、案例、视频等"},
      {"title": "AI adoption", "weight": 10, "order_num": 4, "description": "打通至少一个AI发布工具；"}
    ]
  },
  {
    "name": "吴鹏",
    "dept": "项目交付与支持",
    "position": "产品-项目经理",
    "wecom_userid": "wupeng",
    "objectives": [
      {"title": "完成金盘2期项目交付", "weight": 40, "order_num": 1, "description": "5分: 如期交付，客户满意，功能一切正常，提前合同期回款。\n4分: 相对可控时间内完成交付，客户相对满意，基本实现功能，正常完成项目交付签字"},
      {"title": "产品设计", "weight": 30, "order_num": 2, "description": "5分: 完整理解已有产品功能，并能够完整独立完成产品工作\n4分:  对现有架构和产品功能有基本认知，并在一定协助支持下，能够部分完成至少1个产品功能的设计工作"},
      {"title": "交付逻辑复盘与沉淀", "weight": 20, "order_num": 3, "description": "5分：基于现有项目交付的问题进行复盘，并明确优化错误，形成具体机制措施与SOP\n4分：基于已完成项目情况，和交付过程中的问题点，在梳理后形成知识文档，给后续项目形成参考"},
      {"title": "现有issue体系优化", "weight": 10, "order_num": 4, "description": "5分: 完成Issue数据规范化，构建完整的体系并使AI能够识别完整信息，并能够生成日看板\n4分:  能够基本完成issue规范化，并形成相对固定的机制，能够完成基本的体系落地"}
    ]
  }
]

def main():
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # 1. 创建/查找绩效周期
    cycle_name = "2026 1H"
    cursor.execute("SELECT id FROM performance_cycle WHERE name = %s", (cycle_name,))
    row = cursor.fetchone()
    if row:
        cycle_id = row[0]
        print(f"周期已存在: {cycle_name} (id={cycle_id})")
    else:
        cursor.execute(
            "INSERT INTO performance_cycle (name, start_date, end_date, status, enable_self_eval, enable_peer_eval, enable_calibration, enable_feedback, created_by, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())",
            (cycle_name, date(2026, 1, 1), date(2026, 6, 30), "closed", True, True, True, True, "shenxiaowei")
        )
        cycle_id = cursor.lastrowid
        print(f"创建周期: {cycle_name} (id={cycle_id})")

    # 2. 创建/查找部门
    dept_map = {}
    for item in DATA:
        dept_name = item["dept"]
        if dept_name not in dept_map:
            cursor.execute("SELECT id FROM department WHERE name = %s", (dept_name,))
            row = cursor.fetchone()
            if row:
                dept_map[dept_name] = row[0]
                print(f"部门已存在: {dept_name} (id={row[0]})")
            else:
                cursor.execute(
                    "INSERT INTO department (wecom_dept_id, name, order_num) VALUES (%s, %s, %s)",
                    (1000 + len(dept_map), dept_name, 0)
                )
                dept_map[dept_name] = cursor.lastrowid
                print(f"创建部门: {dept_name} (id={cursor.lastrowid})")

    # 3. 创建/查找用户
    user_map = {}
    for item in DATA:
        wuid = item["wecom_userid"]
        cursor.execute("SELECT id FROM user WHERE wecom_userid = %s", (wuid,))
        row = cursor.fetchone()
        if row:
            user_map[wuid] = row[0]
            print(f"用户已存在: {item['name']} (id={row[0]})")
        else:
            dept_id = dept_map.get(item["dept"])
            cursor.execute(
                "INSERT INTO user (wecom_userid, name, department_id, position, role, status, synced_at) VALUES (%s, %s, %s, %s, %s, %s, NOW())",
                (wuid, item["name"], dept_id, item.get("position"), "employee", "active")
            )
            user_map[wuid] = cursor.lastrowid
            print(f"创建用户: {item['name']} (id={cursor.lastrowid})")

    # 4. 导入业绩目标
    total_objs = 0
    for item in DATA:
        wuid = item["wecom_userid"]
        user_id = user_map[wuid]
        for obj in item["objectives"]:
            cursor.execute(
                "INSERT INTO objective (cycle_id, user_id, title, description, weight, order_num) VALUES (%s, %s, %s, %s, %s, %s)",
                (cycle_id, user_id, obj["title"], obj["description"], obj["weight"], obj["order_num"])
            )
            total_objs += 1

    conn.commit()
    print(f"\n导入完成: {total_objs} 条业绩目标")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
