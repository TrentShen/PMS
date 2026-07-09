# agents.md — Kimi 协作规则

> 本文件定义 Kimi 在 PMS 项目中的行为准则。每次会话开始时，Kimi 应主动读取本文件和 HARNESS.md。

---

## 1. 项目身份卡

```yaml
name: PMS · 绩效管理系统
version: V0.9
scale: 100 人内小团队
stack_backend: FastAPI + SQLModel + Alembic + MySQL + Redis
stack_frontend: Vite + React 18 + TypeScript + Ant Design 5 + Zustand + Axios
auth: 企业微信 OAuth 2.0 + RBAC（role + scope）
deploy: Docker Compose + Nginx
env: 生产跑在公司服务器，开发本地 Docker
```

---

## 2. 技术栈详情

### 2.1 后端（Python 3.12）

| 库 | 版本 | 用途 |
|---|------|------|
| fastapi | ^0.115 | Web 框架 |
| sqlmodel | ^0.0.22 | ORM（SQLAlchemy 2.0 封装） |
| alembic | ^1.14 | 数据库迁移 |
| pydantic | ^2.10 | 数据校验 / Settings |
| pydantic-settings | ^2.7 | 环境变量配置 |
| aiomysql | ^0.2 | 异步 MySQL 驱动 |
| redis | ^5.2 | 缓存 / 限流 |
| APScheduler | ^3.11 | 定时任务（通讯录同步） |
| loguru | ^0.7 | 日志 |
| python-jose | ^3.4 | JWT |
| passlib | ^1.7 | 密码哈希 |
| pandas | ^2.2 | Excel 导入导出 |
| openpyxl | ^3.1 | Excel 读写 |
| email-validator | ^2.2 | 邮箱格式校验 |

### 2.2 前端（Node 20+）

| 库 | 版本 | 用途 |
|---|------|------|
| react | ^18.3 | UI 框架 |
| typescript | ^5.6 | 类型系统 |
| vite | ^6.0 | 构建工具 |
| antd | ^5.24 | UI 组件库 |
| zustand | ^5.0 | 状态管理 |
| axios | ^1.7 | HTTP 客户端 |
| react-router-dom | ^7.1 | 路由 |
| @ant-design/charts | ^2.2 | 图表（校准分布图等） |
| xlsx | ^0.18 | Excel 前端解析 |

---

## 3. 目录结构约定

```
pms/
├── HARNESS.md              # AI 协作架构（必读）
├── agents.md               # 本文件
├── README.md               # 项目说明
├── .env.example            # 环境变量模板
├── backend/
│   ├── src/pms/
│   │   ├── main.py         # FastAPI 应用入口
│   │   ├── configs/
│   │   │   └── settings.py # 配置中心（所有 env 走这里）
│   │   ├── api/v1/         # API 路由（按业务模块分文件）
│   │   ├── database/
│   │   │   ├── models/     # SQLModel 模型
│   │   │   ├── session.py  # 数据库会话/引擎
│   │   │   └── migrations/ # Alembic 迁移
│   │   ├── services/       # 业务逻辑层
│   │   ├── scheduler/      # 定时任务
│   │   └── utils/          # 工具函数
│   ├── alembic/            # 迁移脚本
│   ├── Dockerfile
│   ├── Makefile            # make dev / test / migrate
│   └── pyproject.toml
├── web/
│   ├── src/
│   │   ├── main.tsx        # 应用入口
│   │   ├── App.tsx         # 路由配置
│   │   ├── global.css      # 全局样式
│   │   ├── pages/          # 页面组件
│   │   ├── components/     # 复用组件
│   │   ├── services/
│   │   │   └── api.ts      # Axios 实例 + 拦截器
│   │   ├── stores/         # Zustand 状态
│   │   └── hooks/          # 自定义 Hooks
│   ├── Dockerfile
│   └── vite.config.ts
└── deploy/
    ├── docker-compose.dev.yml
    ├── docker-compose.prod.yml
    └── nginx.conf
```

**铁律**：
- 后端所有配置必须从 `pms.configs.settings` 读取，禁止直接 `os.getenv`
- 前端所有 API 请求必须经过 `services/api.ts` 的 Axios 实例
- 新增模型必须同时在 `database/models/__init__.py` 中导入

---

## 4. 编码规范

### 4.1 Python 规范

#### 命名
- 模块/包：`snake_case`
- 类：`PascalCase`
- 函数/变量：`snake_case`
- 常量：`UPPER_SNAKE_CASE`
- 私有：`_leading_underscore`

#### 导入顺序（isort 风格）
```python
# 1. 标准库
import os
from datetime import datetime, timezone

# 2. 第三方库
from fastapi import APIRouter, Depends
from sqlmodel import Session, select

# 3. 项目内部（绝对导入）
from pms.configs.settings import get_settings
from pms.database.session import get_db
```

#### 类型注解
- **必须**：所有函数参数和返回值加类型注解
- **必须**：Pydantic / SQLModel 字段加类型
- **禁止**：使用 `Any` 逃避类型检查（除非真的无法确定）

#### 异步
- 数据库操作使用异步会话（`AsyncSession`）
- 路由函数声明 `async def`
- I/O 阻塞操作（文件读写、HTTP 请求）使用 `await`

#### 时间处理
- **禁止**：使用 `datetime.utcnow()`（Python 3.12 已废弃）
- **正确**：`datetime.now(timezone.utc)`
- 数据库字段使用 `DateTime(timezone=True)`

#### 错误处理
- 业务异常使用 HTTPException，带明确的状态码和 detail
- 不允许裸 `except:`，至少 `except Exception:`
- 异常必须记录日志

### 4.2 TypeScript / React 规范

#### 命名
- 组件：`PascalCase.tsx`
- Hooks：`useSnakeCase.ts`
- 工具函数：`camelCase`
- 类型/接口：`PascalCase`
- 常量：`UPPER_SNAKE_CASE`

#### 类型严格
- **禁止**：`any`（用 `unknown` + 类型守卫代替）
- **必须**：函数参数和返回值有类型
- **必须**：API 响应数据有接口定义
- 优先使用 `interface` 定义对象类型，类型别名声名复合类型

#### React
- 函数组件用 `const Component: React.FC<Props> = () => {}`
- Hooks 必须在组件顶层调用，禁止条件调用
- `useEffect` 必须写完整依赖数组
- 表单使用 Ant Design `<Form>` + `form.validateFields()`

#### API 调用
- 所有请求走 `services/api.ts` 的 `request()` 方法
- 响应类型统一在接口定义文件中声明
- 错误处理统一在响应拦截器

### 4.3 前后端契约

**这是最高频的 Bug 来源，必须严格遵守：**

1. **字段名一致**：前端用的字段名必须与后端 Pydantic Schema 完全一致
2. **类型一致**：TS 类型 ↔ Python 类型对照：
   - `string` ↔ `str`
   - `number` ↔ `float` / `int`
   - `boolean` ↔ `bool`
   - `Date` ↔ `datetime`
   - `T | null` ↔ `Optional[T]` / `T | None`
   - `T[]` ↔ `list[T]`
3. **必填一致**：前端 `required` ↔ 后端 `Field(...)` 或没有 `default=None`
4. **枚举一致**：前后端使用相同的枚举值（建议抽离到共享常量文件）

**Plan 阶段必须输出契约对照表：**

```markdown
| 字段 | 前端类型 | 后端类型 | 必填 | 说明 |
|------|----------|----------|------|------|
| user_id | number | int | 是 | 用户ID |
```

---

## 5. 工作流规则

### 5.1 新功能开发流程

1. **理解需求**：读取相关 PRD / 技术方案文档
2. **影响分析**：列出修改的文件清单
3. **接口设计**：先定前后端契约（DTO / Schema）
4. **数据库变更**：如有模型变更，先生成 Alembic migration
5. **后端实现**：API → Service → Model
6. **前端实现**：Page → Component → API Call
7. **测试**：补单元测试 + 手工验证
8. **Review**：检查类型安全、安全漏洞、性能

### 5.2 Bug 修复流程

1. **定位**：找到根因（不要只修表面）
2. **最小改动**：只改必要的地方
3. **回归测试**：写测试复现 Bug，修复后通过
4. **波及检查**：搜索是否有类似代码在其他地方

### 5.3 数据库变更流程

1. 修改 SQLModel 模型
2. 生成 migration：`alembic revision --autogenerate -m "描述"`
3. **人工 review** migration 脚本（AI 生成后必须人看）
4. 本地测试 migration：`make migrate`
5. 提交 migration 文件到 git

### 5.4 Git 提交规范

使用 **Conventional Commits**：

```
<type>(<scope>): <subject>

<body>

<footer>
```

- `type`: `feat` | `fix` | `docs` | `style` | `refactor` | `test` | `chore`
- `scope`: `backend` | `web` | `db` | `deploy` | `api` | `ui`
- `subject`: 动词开头，小写，不超过 50 字

示例：
```
feat(api): add calibration batch update endpoint

- support updating multiple users' scores in one request
- add transaction wrapper for data consistency

Closes #42
```

---

## 6. 禁止事项（绝对红线）

### 6.1 安全红线
- [ ] **禁止**在代码中硬编码密码、token、secret
- [ ] **禁止**直接拼接 SQL 字符串（必须用 ORM / 参数化查询）
- [ ] **禁止**在生产环境暴露 `/mock-users` 等调试接口
- [ ] **禁止**把 `.env` 文件提交到 git（检查 `git ls-files | grep .env`）
- [ ] **禁止**接口不经过权限校验返回敏感数据

### 6.2 质量红线
- [ ] **禁止**提交未测试的代码（至少 happy path 要过）
- [ ] **禁止**修改后不更新类型定义
- [ ] **禁止**前端调用不存在或字段不匹配的后端接口
- [ ] **禁止**在循环内发数据库查询（N+1）
- [ ] **禁止**全表查询不分页（导出除外，但导出要异步）

### 6.3 规范红线
- [ ] **禁止**直接 `os.getenv`，走 `settings`
- [ ] **禁止**新建模型不导入 `models/__init__.py`
- [ ] **禁止`datetime.utcnow()`，用 `datetime.now(timezone.utc)`
- [ ] **禁止**前端 API 不走 `services/api.ts`
- [ ] **禁止**修改后不更新 `.env.example`

---

## 7. 调试与排查指南

### 7.1 后端排查

```bash
cd backend
make dev              # 启动开发服务器
make test             # 运行测试
make migrate          # 执行迁移

# 查看 API 文档
open http://localhost:8000/docs
```

常见问题：
- **ImportError**：检查 `sys.path` 和 `PYTHONPATH`，确保 `src` 在路径中
- **Migration 失败**：检查 `alembic.ini` 的 `sqlalchemy.url`，确认数据库可连
- **异步问题**：确认用了 `await`，确认函数声明了 `async def`

### 7.2 前端排查

```bash
cd web
npm run dev           # 启动开发服务器
npm run build         # 检查构建错误
```

常见问题：
- **类型错误**：运行 `npx tsc --noEmit`
- **API 404**：检查 `VITE_API_BASE_URL` 是否指向正确后端地址
- **状态不更新**：检查 Zustand store 是否正确使用

### 7.3 Docker 排查

```bash
cd deploy
docker compose -f docker-compose.dev.yml up -d    # 起基础设施
docker compose -f docker-compose.prod.yml up -d --build  # 生产构建

# 查看日志
docker compose logs -f backend
docker compose logs -f web
```

---

## 8. 性能与优化 checklist

### 8.1 后端
- [ ] 查询是否用了 `select()` 的 `where` 条件？
- [ ] 列表接口是否分页（`LIMIT`/`OFFSET` 或 cursor）？
- [ ] 关联查询是否用了 `joinedload` 避免 N+1？
- [ ] 大数据量计算是否异步（Celery / APScheduler background job）？
- [ ] 缓存是否合理使用（Redis 缓存热点数据）？

### 8.2 前端
- [ ] 列表是否虚拟滚动（大数据量时）？
- [ ] 图片/资源是否懒加载？
- [ ] 是否避免不必要的重渲染（`React.memo`、`useMemo`）？
- [ ] API 请求是否防抖/节流？

---

## 9. 已知问题与注意事项

### 9.1 高频 Bug 模式
1. **前后端字段不匹配**：前端用 `value_grade`，后端实际存 `value_belief_grade`/`value_team_grade`/`value_growth_grade`
2. **类型不一致**：前端传 `string`，后端期望 `int`
3. **权限遗漏**：新接口忘记加 `@scope_filter`
4. **事务边界**：`session.commit()` 写在不该写的地方

### 9.2 项目特殊约定
- 业绩评分必须 0.25 分段（前后端双校验）
- 所有敏感写操作必须记 `audit_log`
- 企微 OAuth 登录后新用户名字初始为 userid，等通讯录同步后更新
- 导出功能限制 200 行（后续可能调整）

---

## 10. 外部依赖与资源

- PRD: `../docs/PRD-绩效管理系统.md`
- 技术方案: `../docs/技术方案-绩效管理系统-V0.9.md`
- FastAPI 文档: https://fastapi.tiangolo.com/
- SQLModel 文档: https://sqlmodel.tiangolo.com/
- Ant Design: https://ant.design/components/overview/
- Zustand: https://docs.pmnd.rs/zustand/getting-started/introduction

---

## 11. Claude Code Loop 使用规范

> Claude Code Loop 指让 AI 在可验证的完成标准下自动迭代（写代码 → 跑检查 → 发现问题 → 再改），直到达标或达到上限。本规范明确 PMS 项目中允许和禁止的使用方式。

### 11.1 何时使用 Loop

适合 Loop 的任务特征：
- **可验证**：有客观的红/绿标准（`make test` 通过、`npx tsc --noEmit` 通过、构建成功）
- **可拆分**：能拆成多次小迭代，每次只做一小块
- **机械化高**：重复、规则明确、人工干预价值低的工作

本项目推荐场景（按优先级）：
1. **前后端契约自动校验脚本**：新增 `scripts/check_contract.py`，扫描字段名/类型/必填差异
2. **前端 `any` 类型清理**：按页面逐步替换为具体类型，最终打开 `noImplicitAny`
3. **流程开关 `enable_*` 前后端一致性改造**：后端返回开关，前端菜单/页面响应
4. **CI/CD 轻量化闭环**：GitHub Actions 跑 pytest、tsc/build、ruff、契约校验
5. **后端测试补全**：为导出、历史、通知等薄弱模块补单元测试
6. **历史绩效结果导入**：后端 API + 前端页面 + Excel 模板
7. **关键节点企微通知补全**：在状态变更点补充通知触发

### 11.2 项目专用约束（重要）

**绝对禁止自动合并**：
- 本项目**不允许**使用 Continuous Claude 等工具的自动 PR 合并功能。
- Loop 可以生成代码、跑检查、生成 PR/分支，但**最终合并必须由人类在 review 后执行**。
- 任何 Loop 流程不得绕过代码 review 和人工确认。

Loop 必须满足：
- 每次 Loop 必须设定 `--max-iterations` 或时间/成本上限，防止无限循环
- 必须定义清晰的完成标准，不能是"更好一点"这类模糊目标
- 每次 Loop 开始前必须列出本次要修改的文件清单，禁止越界修改
- 涉及数据库模型、环境变量、部署配置的修改，必须在执行前取得人类确认

### 11.3 推荐命令模板

#### 后端补测试 / 修 Bug
```bash
cd pms/backend
/goal "为 feedback.py:list_feedback_status 添加 N+1 回归测试，并确保 make test 全绿"
/loop every 3m until: make test passes
```

#### 前端类型清理（每次限定 1-2 个文件）
```bash
cd pms/web
/ralph-loop "清理 web/src/pages/HrConsole.tsx 中的 any 类型，只改本文件，完成后 npx tsc --noEmit 必须通过" \
  --completion-promise "DONE" \
  --max-iterations 15
```

#### 契约校验脚本开发
```bash
cd pms/backend
/goal "新增 scripts/check_contract.py，扫描后端 Pydantic Schema 与前端 API payload 的字段名/类型/必填差异，输出报告并接入 make lint"
/loop every 5m until: make lint passes
```

### 11.4 Loop 专属红线

- **禁止**让 Loop 自动执行 `git push`、`docker compose -f docker-compose.prod.yml up`、`alembic upgrade` 等生产相关命令
- **禁止**让 Loop 修改 `.env`、密码、密钥、OAuth 配置
- **禁止**让 Loop 在未经许可的情况下删除文件或表
- **禁止**让 Loop 跳过 HARNESS.md 的 6 道质量门禁
- **禁止**让 Loop 一次处理超过 3 个页面或模块（控制爆炸半径）

### 11.5 Loop 结束时的必做检查

每次 Loop 完成后，无论成功或失败，都必须：
1. 运行项目本地验证命令（`make test`、`npx tsc --noEmit`、`npm run build` 等）
2. 检查 `git diff`，确认没有意外修改
3. 更新 `.workbuddy/memory/` 或相关文档，记录本次 Loop 的范围和结果
4. 如果修改了接口，更新前后端契约对照表

---

*本文件与 HARNESS.md 配套使用。每次开始新任务时，Kimi 应确认已读取这两个文件。*
