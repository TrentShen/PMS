# Harness · AI 辅助研发架构

> 版本：v2.1  
> 适用：PMS 绩效管理系统（FastAPI + React）  
> 工具：Kimi（主 AI 助手）  
> 配套：agents.md、.harness/rules/、.harness/errors.md  
> 最后更新：2026-06-24

---

## 1. 核心理念

**Human-AI Pair Programming（人机结对编程）**

- **人负责**：需求理解、架构决策、业务逻辑把关、最终审批
- **AI 负责**：代码生成、重构建议、测试编写、文档补全、缺陷扫描
- **共同负责**：代码审查、技术方案讨论、边界 case 梳理

**原则**：AI 是"副驾驶"，不是"自动驾驶"。所有进仓库的代码必须有人类确认。

---

## 2. AI 编码行为基线（RULE-012）—— 最高优先级

这是任何情况下不得违反的行为基线：

1. **没有猜测** —— 不确定必须问，不许猜。存疑点声明 `[不确定]`
2. **没有过度设计** —— 先实现"刚好能跑"的版本。当前系统**没有** Celery/消息队列，禁止引入新基础设施
3. **没有越界修改** —— 只改当前任务涉及的代码。如需改其他模块，先声明并等确认
4. **没有隐瞒不确定** —— 有疑问提前说，不要假装确定

---

## 3. 工作模式（P-C-R-V 循环）

所有任务遵循 **Plan → Code → Review → Verify**：

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Plan    │────→│  Code    │────→│  Review  │────→│  Verify  │
│  (计划)   │     │  (编码)   │     │  (审查)   │     │  (验证)   │
└──────────┘     └──────────┘     └──────────┘     └────┬─────┘
       ↑─────────────────────────────────────────────────┘
                        （发现问题，回到 Plan 或 Code）
```

### 3.1 Plan（计划）

- **输入**：需求描述、Bug 报告、重构目标
- **AI 动作**：
  1. 分析影响范围（改了哪些文件、哪些接口、哪些表）
  2. 输出**修改清单**（Checklist）
  3. 如有接口变更，先输出**前后端契约对照表**（字段名/类型/必填必须一致）
  4. 输出**操作确认清单**（见第 7 节）
- **人类动作**：确认方案，必要时调整

### 3.2 Code（编码）

- **AI 动作**：
  1. 按 Checklist 逐项实现，每完成一项勾选
  2. 每改一个模块，即时更新关联的类型/模型/接口
  3. 同步写单元测试（后端）或组件测试（前端）
  4. 更新相关文档/注释
- **人类动作**：在 AI 生成过程中随时喊停、纠偏

### 3.3 Review（审查）

- **AI 动作**（自动触发）：
  1. 类型安全检查（TS ↔ Python Schema 是否对齐）
  2. 安全扫描（SQL 注入、XSS、敏感信息泄露）
  3. 性能检查（N+1 查询、大数据量内存操作）
  4. 规范检查（命名、注释、导入顺序、RULE-012 合规）
- **人类动作**：审阅 AI 的 Review 报告，决定是否需要修改

### 3.4 Verify（验证）

- **AI 动作**：
  1. 运行相关测试（`make test` 或 `npm test`）
  2. 类型检查（`tsc --noEmit` / `pyright`）
  3. 如有 Docker 变更，验证构建是否通过
- **人类动作**：在本地或 CI 中确认，通过后合并

---

## 4. 质量门禁（6 道）

代码进入主分支前必须通过：

| 门禁 | 检查项 |
|------|--------|
| **Gate 1 类型安全** | `tsc --noEmit` 无错误；Python 类型注解完整；前后端字段一致 |
| **Gate 2 测试覆盖** | 新增代码有单元测试；核心流程有 e2e；`make test` / `npm test` 通过 |
| **Gate 3 安全审查** | 无硬编码 secret；SQL 用 ORM/参数化；输入有校验；敏感操作写 `audit_log`；新接口有权限校验 |
| **Gate 4 性能基线** | 无未分页全表查询；无 N+1；大数据量操作流式或异步 |
| **Gate 5 规范合规** | 遵守 RULE-012；无新 `console.log`；无遗留 `TODO`/`FIXME`；`.env.example` 已更新 |
| **Gate 6 文档同步** | FastAPI 文档可用；复杂逻辑有注释；HARNESS/agents/PRD 已同步 |

---

## 5. 技术栈速查

### 后端（Python 3.12）
| 库 | 用途 |
|---|------|
| fastapi | Web 框架 |
| sqlmodel | ORM（SQLAlchemy 2.0 封装） |
| alembic | 数据库迁移 |
| pydantic + pydantic-settings | 数据校验 / 环境变量配置 |
| pymysql | MySQL 驱动 |
| redis | 缓存 / 限流 |
| APScheduler | 定时任务（通讯录同步） |
| loguru | 日志 |
| pyjwt | JWT |
| openpyxl | Excel 读写 |

### 前端（Node 20+）
| 库 | 用途 |
|---|------|
| react + typescript | UI + 类型 |
| vite | 构建 |
| antd + antd-mobile | UI 组件 |
| zustand | 状态管理 |
| axios | HTTP 客户端 |
| react-router-dom | 路由 |

---

## 6. 编码规范（与 agents.md 保持一致）

### 6.1 Python
- **命名**：模块 `snake_case`，类 `PascalCase`，函数/变量 `snake_case`，常量 `UPPER_SNAKE_CASE`
- **导入顺序**：标准库 → 第三方 → 项目内部（绝对导入）
- **类型注解**：所有函数参数和返回值必须有。禁止用 `Any` 逃避
- **时间**：**禁止** `datetime.utcnow()`，用 `datetime.now(timezone.utc)`
- **配置**：所有配置走 `pms.configs.settings`，**禁止** `os.getenv`
- **模型导入**：新增模型必须在 `database/models/__init__.py` 导入

### 6.2 TypeScript / React
- **命名**：组件 `PascalCase.tsx`，Hooks `useSnakeCase.ts`，工具 `camelCase`
- **类型**：**禁止** `any`，用 `unknown` + 类型守卫
- **React**：Hooks 必须在顶层，禁止条件调用。`useEffect` 写完整依赖数组
- **API**：所有请求走 `services/api.ts`
- **表单**：用 Ant Design `<Form>` + `form.validateFields()`

### 6.3 前后端契约（最高频 Bug 来源！）
- **字段名必须完全一致**：前端传的字段名 = 后端 Pydantic Schema 字段名
- **类型对照**：`string`↔`str`，`number`↔`float`/`int`，`boolean`↔`bool`，`T|null`↔`Optional[T]`，`T[]`↔`list[T]`
- **必填一致**：前端 `required` ↔ 后端 `Field(...)` 或无 `default=None`
- **Plan 阶段必须输出字段对照表**

---

## 7. 操作确认机制（破坏性操作清单）

以下操作**执行前必须向人类确认**：

- [ ] 删除任何源码文件
- [ ] 修改数据库模型（`database/models/*.py`）
- [ ] 修改依赖（`package.json` / `pyproject.toml`）
- [ ] 一次修改超过 3 个文件
- [ ] 修改其他模块/PRD 的代码（越界）
- [ ] 修改配置文件（`vite.config.ts`、`docker-compose.yml`、`nginx.conf`）
- [ ] 部署时覆盖生产 `.env`（必须先备份并人工确认）
- [ ] 删表/清数据（migration 删字段/表）
- [ ] 引入新基础设施（Celery、消息队列等——当前系统**没有**这些）

**确认话术**："我需要执行 [操作]，理由 [原因]，影响 [范围]，是否确认？"

---

## 8. 禁止事项（绝对红线）

### 安全
- 硬编码密码/token/secret
- 直接拼接 SQL（必须用 ORM/参数化）
- 生产环境暴露 `/mock-users` 等调试接口
- `.env` 提交到 git
- 部署时覆盖生产 `.env`（必须先 diff 确认）
- 接口不经权限校验返回敏感数据

### 质量
- 提交未测试代码
- 修改后不更新类型定义
- 前端调用字段不匹配的后端接口
- 循环内发数据库查询（N+1）
- 全表查询不分页
- 引入新基础设施（Redis 已存在，但 Celery/消息队列**没有**）

### 规范
- `os.getenv`（走 `settings`）
- `datetime.utcnow()`（用 `datetime.now(timezone.utc)`）
- 前端 API 不走 `services/api.ts`
- 新的 `console.log`（后端用 loguru）
- 遗留 `TODO`/`FIXME`

### 行为（RULE-012）
- 猜测实现
- 过度设计
- 越界修改
- 隐瞒不确定

---

## 9. 已知规则（.harness/rules/）

| 规则 | 说明 |
|------|------|
| RULE-001 | 前后端字段一致性 |
| RULE-002 | 权限校验 |
| RULE-003 | 事务边界 |
| RULE-004 | 时间处理（禁用 utcnow） |
| RULE-005 | 数据库模型导入 |

---

## 10. 调试命令速查

```bash
# 后端
cd pms/backend && make dev       # 启动
cd pms/backend && make test      # 测试
cd pms/backend && make migrate   # 迁移
open http://localhost:8000/docs

# 前端
cd pms/web && npm run dev        # 启动
cd pms/web && npm run build      # 构建检查
cd pms/web && npx tsc --noEmit   # 类型检查

# Docker
cd pms/deploy && docker compose -f docker-compose.dev.yml up -d
cd pms/deploy && docker compose -f docker-compose.prod.yml up -d --build
```

---

## 11. 项目当前状态（迭代进度与阻塞项）

> 本章节由 AI 在每次会话后更新，用于快速同步上下文。

### 11.1 已完成功能

| 批次 | 功能 | 状态 |
|------|------|:--:|
| P0-0 | 生产环境禁用 `/mock-users` 和 `/mock-login` | ✅ |
| P0-1 | 修复 CycleParticipant 关联（历史数据导入后可见） | ✅ |
| P0-2 | 目标设定线上化流程（员工填写 → 提交审批 → 上级批准/驳回） | ✅ |
| P0-3 | 上级评估页增加历史绩效展示（`history_perf` 字段） | ✅ |
| P0-4 | 自动提醒框架（修复 `utcnow()`） | ✅ |
| P0-5 | 反馈与发布流程顺序（已满足"先沟通后公开"） | ✅ |
| P0-6 | `direct_leader` 角色权限补全（互评/反馈可见） | ✅ |
| P1-1 | 手松手紧提示（后端统计 + 前端展示） | ✅ |
| P1-2 | 校准矩阵热力图（按部门/职级分组） | ✅ |
| P1-3 | 考核对象排除规则（周期配置持久化 + 5 维过滤） | ✅ |
| P1-4 | 结构化面谈模板（后端必填校验） | ✅ |
| P1-5 | 目标中途调整（审批流 + revision 历史表） | ✅ |
| 全局 | 所有 `datetime.utcnow()` 替换为 `datetime.now(timezone.utc)` | ✅ |
| 全局 | 后端单元测试覆盖（50 个测试全绿） | ✅ |
| P2-1 | 试用期管理模块：自动创建计划、目标填写/审批、上级评估、转正建议 | ✅ |
| P2-2 | 试用期即时消息通知 + 可复用企微消息推送服务 | ✅ |
| 全局 | Claude Code Loop 使用规范写入 agents.md | ✅ |
| 全局 | 前后端契约自动校验脚本 `scripts/check_contract.py` | ✅ |
| 全局 | 修复 5 个前端 API 路径 mismatch | ✅ |
| 全局 | 前端全量 `any` 清理 + 开启 `noImplicitAny` | ✅ |
| 全局 | 提取共享 `formatError` 到 `services/api.ts` | ✅ |
| 全局 | 周期管理：严格 FTE 过滤（仅 full_time 可参与） | ✅ |
| 全局 | 周期/参与人删除保护（有绩效数据时禁止删除） | ✅ |
| 全局 | 后端测试覆盖删除与 FTE 过滤场景 | ✅ |
| 全局 | 部署安全：登记硬编码密码事件并新增 SSH 密钥管理指南 | ✅ |

### 11.2 剩余待办事项

| 编号 | 事项 | 优先级 | 说明 |
|------|------|:--:|------|
| — | Git 用户信息配置 | 建议 | 当前 commit author 为自动生成，建议配置 `git config --global user.name/email` |
| — | 生产环境执行新迁移 | P0 | 初始迁移已重写为单一完整迁移 `a088a1294289`，新环境执行 `alembic upgrade head` 即可从零建库；生产已升级至 `124515811db3` |
| — | 人事助手权限验证 | P0 | 需确认自建应用有「人事助手」接口权限，且员工在应用可见范围内 |
| — | 全量 utcnow 清理 | P1 | 已替换 src/ 下所有 `datetime.utcnow()` |
| — | 完整 UAT | P0 | 本地 happy path 已跑通，发现并修复 4 个问题（含 Alembic 初始迁移） |
| TODO-001 | 企微通讯录权限开通与部门树同步 | P0 | 当前 `contact_sync` 因权限 `60011`/`60020` 禁用；开通后需重新拉取完整 1-3 级部门树，并校正用户 `department_id` 到最细粒度部门 |
| TODO-002 | 按 1-3 级部门筛选用户/参与人 | P1 | 待 TODO-001 完成后，在用户列表、按条件筛选参与人弹窗中支持按一级/二级/三级部门筛选 |
| TODO-003 | 生产环境代码同步机制 | P1 | 服务器 `/opt/pms/pms` 不是 git 仓库，本次通过 tar 同步；后续建议改用 git pull 或 CI/CD，避免代码/迁移版本不一致 |

### 11.3 冲刺计划

> 当前策略：全力冲刺月底绩效启动会；若赶不上，启用**试用期管理**作为兜底方案。详见 `docs/月底冲刺计划-20260616.md`。

**冲刺关键事项**：
| 编号 | 事项 | 优先级 | 状态 |
|------|------|:------:|:----:|
| S-1 | 前端 `LeaderEvalDetail.tsx` 三维度检查 | P0 | ✅ 已确认 |
| S-2 | 前端 `AnonymousFeedback.tsx` 选人接口改用 `/v1/users` | P0 | ✅ 已完成 |
| S-3 | 后端全局 `datetime.utcnow()` 替换 | P1 | ✅ 已完成 |
| S-4 | Alembic 初始迁移重写（UAT-4） | P1 | ✅ 已修复：新环境 `alembic upgrade head` 可一次性创建所有表 |
| S-5 | User 人事字段 + 人事助手 API 封装 | P1 | ✅ 已完成 |
| S-6 | 人事助手接口权限与可见范围 | P0 | 待验证 |

### 11.4 部署状态

- **公网访问**：`https://shanghai.idc.matrixorigin.cn:30088/`
- **后端**：`python3 -m uvicorn pms.main:app --host 0.0.0.0 --port 8000`
- **后端启动方式**：`cd /opt/pms/pms/backend && PYTHONPATH=src nohup python3 -m uvicorn pms.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &`
- **健康检查**：`GET /api/v1/health` → `{"status":"ok"}`
- **企微登录**：已修复（`WECOM_REDIRECT_URI` 已恢复为生产域名，`APP_ENV=prod`）
- **数据库**：Docker `pms-mysql`，宿主机端口 `3307`
- **缓存**：Docker `pms-redis`，宿主机端口 `6379`

### 11.5 已知风险

1. **MySQL `.env` 密码修正**：服务器 `/opt/pms/pms/backend/.env` 中的 `MYSQL_PASSWORD` 已从错误的 `pms_password` 修正为 `Pms_Prod_2024_Secure`（与 `deploy/.env.prod` 一致）。
2. **`.env` 覆盖事件教训**：2026-06-12 部署时，本地开发 `.env` 被部署包覆盖到服务器，导致 `WECOM_REDIRECT_URI` 变为 `localhost:5173`，企微登录失败且 `APP_ENV=local` 暴露调试接口。已修复并新增 HARNESS 规则禁止此行为。
3. **Alembic 初始迁移重写**：`a088a1294289_v0_9_initial_schema.py` 已重写为包含全部 16 张表的完整初始迁移，并删除已冗余的后续增量迁移。新环境执行 `alembic upgrade head` 即可从零建库；已存在数据的环境需执行 `alembic stamp a088a1294289` 对齐版本号。
4. **人事助手权限待验证**：PMS 已改用自建应用 `WECOM_SECRET` 调用通讯录和人事助手接口，需确认应用有「人事助手」接口权限且员工在可见范围内。
5. **全量 utcnow 清理**：`datetime.utcnow()` 已全部替换为 `datetime.now(timezone.utc)`，但需在完整测试环境中验证无回归。

---

*本文件与 agents.md、.harness/rules/、.harness/errors.md 配套使用。*
