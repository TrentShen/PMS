# HANDOFF.md — PMS 项目交接上下文

> 写给后续接手开发的 AI(Codex)和人类协作者。
> 最后更新:2026-08-05(Kimi Code 交接)。
> 读法:先读本文 → 再按 §2 的清单深入 → 开工前核对 §3 的状态快照是否已过时。

---

## 1. 项目速览

- **名称**:MO绩效 · 绩效管理系统(PMS),100 人内小团队内部系统
- **阶段**:灰度测试中(未正式全员推广),企微 H5 为主要入口
- **技术栈(以代码为准,文档曾有多处漂移已修正)**:
  - 后端:FastAPI + SQLModel(**同步 Session + pymysql**,不是异步!)+ Alembic + MySQL 8 + Redis 7,Python 3.12
  - 前端:Vite 5 + React 18 + TS + antd 5 + zustand + react-router-dom 6
  - 部署:Docker Compose 单机 + 宿主机 nginx 终结 SSL
- **生产**:https://shanghai.idc.matrixorigin.cn:30088(企微应用"绩效[测试中]")
- **服务器**:root@10.222.4.38(Ubuntu,Docker;密码问项目 owner)
- **代码仓库**:
  - 主仓库 github.com/TrentShen/PMS(main 直推)
  - 协作仓库 github.com/matrixorigin/hr-trent 的 `03-performance-management/`(main 受保护,必须 PR;**同步时不要带 .github/workflows**,按约定)

## 2. 必读文件(按顺序)

| 文件 | 内容 |
|---|---|
| `AGENTS.md` | 协作规范:技术栈、命名、前后端契约铁律、禁止事项、反过度设计约束(§12 必读) |
| `HARNESS.md` | 质量门禁与工作流 |
| `docs/待决策事项-20260804.md` | **权限语义等产品决策的记录**(第六节"决策执行结果"是已定口径,不要反着改) |
| `docs/PMS-前端全面自检-20260805.md` | 最近一次全面自检:发现、修复、复检、有意不修的 backlog |
| `docs/PMS-Codex审计评估与修复计划-20260805.md` | Codex 审计核实 + 批次 1 已修、批次 2 待确认 |
| `.workbuddy/memory/` | 逐日工作记录(2026-07-22 / 07-31 / 08-04 三份信息量最大,含大量踩坑记录) |
| `docs/部署指南-PMS.md` | 部署与企微配置 |

## 3. 当前状态快照(2026-08-05,使用前请重新核对)

### Git
- `TrentShen/PMS` origin/main = `7c1b3e8`(自检修复已推)
- **未提交改动(批次 1)**:AGENTS.md 纠偏、pyproject requires-python 收紧、删 init_db.py 与 import_objectives.py、/health 加探针 + test_health.py、前端 Vitest 骨架(7 用例 + CI 接入)、api.ts 注释修正
- `hr-trent` PR #13(同步 7c1b3e8 内容)**待人工合并**

### 生产
- 线上版本 ≈ `74e1805`(8-05 上午部署,权限语义 + 安全加固 + 唯一约束)
- **未上线**:`7c1b3e8`(前端自检修复)和批次 1 全部内容
- 部署方式见 §5;迁移会自动跑(有 DB 备份兜底)

### 测试基线
- 后端:`cd pms/backend && .venv/bin/python -m pytest -q` → **197 passed**
- 前端:`cd pms/web && npm test`(vitest,7 例)+ `npx tsc --noEmit` + `npm run build` + `npx eslint src`(0 error,15 存量 warning 勿动)
- 后端测试依赖本地 docker 的 pms-mysql / pms-redis(常年在跑)

## 4. 待办与待决策(按优先级)

1. **生产部署**(随时可做):把 7c1b3e8 + 批次 1 一起上;部署后真机验证:企微登录回跳、iPad/手机校准页、首页"结果待发布"、/health 探针
2. **端口回收**(等 owner 问运维):确认无人直连 3307/6379 后,删 docker-compose.prod.yml 的 mysql/redis ports 映射
3. **K8s 迁移 2 个决策**(等 owner):① MySQL 集群内 StatefulSet vs 外部 RDS;② 定时任务:独立 scheduler Deployment + SCHEDULER_ENABLED 开关(推荐)vs K8s CronJob。背景见 `.workbuddy/memory/2026-07-31.md`
4. **服务器密码轮换**(owner 已知,灰度期暂缓):MySQL 双密码 + Redis 设密码;正式推广前必做
5. **backlog(有意不修,勿主动做)**:antd chunk 1.17MB、首页重复请求、StrictMode dev 双发、草稿 key 残留、LeaderEvalDetail 互评卡片 rowKey 拼接、HrConsole 卡片点击冒泡、同步 SQLAlchemy 迁移异步(200+ 用户再说)、导出 OOM(200 行限制内无风险)

## 5. 运维操作手册(踩坑后的正确姿势)

### 部署(生产)
```bash
cd pms && expect deploy/expect-deploy.tcl   # 交互式问 SSH 密码;或 DEPLOY_SSH_PASSWORD=xxx 环境变量
```
- 流程:本地打包 pms/ → scp 到 /opt/pms → 预拉基础镜像 → **先 build 后切换**(build 失败不影响在运行服务,8-05 强化)→ DB 备份 → alembic upgrade head → 健康检查
- **长任务防 SSH 断开**:关键操作用 nohup + 日志文件,本地轮询(参考 8-05 事故:expect 同步等待 pip install 会超时误杀)
- 服务器 Docker Hub/PyPI 直连不稳:daemon.json 已配国内 mirror;Dockerfile 已走阿里云 pip 镜像;仍失败就先手动 `docker pull python:3.12-slim node:20-alpine alpine`
- 备份:代码 /opt/pms/backup.<时间戳>/,数据库同目录 db.sql.gz(保留 10 份)

### GitHub 网络(本机)
- github.com 直连时通时断,push/clone 失败**重试即可**(循环最多 10-15 次,间隔 10-15s);HTTP/2 报 "failure when receiving data" 时 `git config http.version HTTP/1.1` 可看到真实错误
- API 认证:`printf 'protocol=https\nhost=github.com\n' | git credential fill` 取 PAT(无需 gh CLI)

### CI
- GitHub Actions 跑 backend pytest + frontend(lint/vitest/build)+ ruff;**CI 无 .env**,测试不能依赖 .env(wecom agentid 容错已做)
- CI 日志 API 需认证,用上面的 PAT 下载

## 6. 关键决策与口径(改动前先读)

- **未开反馈环节的周期:不向员工发布最终结果**(后端 mask 是有意设计,前端显示"结果待发布")
- **历史绩效结果:仅直属上级/HR 可见**,员工不可见
- **互评内容保密**:仅直属上级 + HR;dept_leader 按可见范围(部门子树)放宽过(8-04 决策)
- **校准由 HR 统一提交**;dept_leader 按钮置灰是刻意的
- **业绩分 0.25 分段**,前后端双校验;**试用期/常规目标权重合计必须 100%**,前后端双校验
- **价值观三维(belief/team/growth)前端合并为单项**,提交时 expandValueGrades 展开写回三字段;老数据只有 value_grade,展示层有兜底
- **角色体系**:super_admin/hrbp/dept_leader/direct_leader/employee;is_hr_dept_leader 按**生效角色**判定(8-04 统一);超管可切视角
- **试用期计划状态**:HR 只能改为 in_progress/pending_evaluation/completed/extended 四值,回退态由流程驱动

## 7. 踩坑记录(别再犯)

- **同步栈,别写 async**:路由是 def + 同步 Session;引入 async 混用会出错
- **改依赖要改两个文件**:pyproject.toml 和 requirements.txt(Dockerfile 用后者)
- **测试夹具**:同 session 先 add 后 delete 会撞唯一约束(flush 顺序),删后先 `flush()`;取周期按名称锁定,别取"第一个 in_progress"
- **nginx `add_header` 不被有自定义 header 的 location 继承**,安全头要在子块重复声明
- **断点**:useMobile 是 `< 768`,与 CSS `max-width: 767px` 严格对齐(iPad 竖屏 768px 空白事故)
- **antd TextArea**:autoSize 与手动 resize 不可兼得,项目选了手动拉伸
- **antd `add_participants` 返回处还有一处已知 N+1**(objective_cycles.py),未修
- **生产迁移**:只验证过空库路径;"已有数据+stamp"路径未验证过
- **alembic 全新库重放已验证**(CI 曾挂,4f08/1b1a 两个迁移已修)

## 8. 与 owner 协作的约定

- owner 非技术背景:汇报说人话,给选项不给裸命令;危险操作(部署/删数据/git 变更)先确认
- 变更预算(AGENTS.md §12):单功能新增文件 ≤3、修改 ≤10、新增依赖 = 0(需先说明);不为假设的未来需求加抽象
- 所有敏感写操作记 audit_log;接口必须过权限校验;配置只走 pms.configs.settings
- 完成后必须跑 §3 的测试基线并如实汇报,不允许"应该没问题"

---

*本文档随重大变更更新。接手第一件事:核对 §3 快照(git log、生产版本、待办状态)。*
