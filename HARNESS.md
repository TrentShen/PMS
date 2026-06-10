# Harness · AI 辅助研发架构

> 版本：v2.0  
> 适用：PMS 绩效管理系统（FastAPI + React）  
> 工具：Kimi（主 AI 助手）  
> 配套：agents.md、.harness/rules/、.harness/errors.md

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

*本文件与 agents.md、.harness/rules/、.harness/errors.md 配套使用。*
