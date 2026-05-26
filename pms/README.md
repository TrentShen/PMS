# PMS · 绩效管理系统

企业微信 H5 绩效管理系统（100 人内小团队），对应 [PRD v1.2](../docs/PRD-绩效管理系统.md) 与 [技术方案 V0.9](../docs/技术方案-绩效管理系统-V0.9.md)。

## 目录结构

```
pms/
├── backend/          FastAPI + SQLModel + Alembic
│   ├── src/pms/      源码（api/configs/database/services/utils/scheduler）
│   ├── alembic/      数据库迁移
│   ├── Dockerfile    生产镜像
│   └── Makefile      make dev / migrate / test
├── web/              Vite + React 18 + TypeScript + Ant Design
│   └── src/          源码（pages/components/services/hooks/stores）
├── deploy/
│   ├── docker-compose.dev.yml    本地：只起 MySQL + Redis
│   ├── docker-compose.prod.yml   生产：应用+DB+Redis+Nginx 一起
│   └── nginx.conf                HTTPS + SPA 回退 + /api 反代
└── .env.example      环境变量模板
```

## 本地开发快速启动

### 1. 起基础设施

```bash
cd deploy
docker compose -f docker-compose.dev.yml up -d
```

### 2. 配置环境变量

```bash
cp ../.env.example ../backend/.env
# 企微字段暂时留空，先联调健康检查接口
```

### 3. 启动后端

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make migrate            # 应用数据库迁移（表为空时可跳过）
make dev                # http://localhost:8000/docs
```

### 4. 启动前端

```bash
cd web
npm install
npm run dev             # http://localhost:5173
```

打开 `http://localhost:5173`，首页应该显示"后端连通性: ok"。

## V0.9 范围（MVP 单路径）

1. 企微 OAuth 免登
2. 通讯录同步（每日 + 手动）
3. 应用消息推送（含日志 + 重试 + 邮件降级）
4. 绩效周期创建 / 参与人选择
5. 目标录入
6. 自评 + 上级评估
7. 结果发布 + 历史查询
8. HRBP Excel 导出（含导出日志）

Sprint 2 补：互评、部门校准、公司级审批（HR→CEO）、匿名评价、Excel 批量导入。

## 上线

本地开发通过后，把代码发到公司服务器：

```bash
cd deploy
cp .env.example .env.prod   # 填入生产配置
# 把 HTTPS 证书放到 ./certs/{fullchain.pem, privkey.pem}
docker compose -f docker-compose.prod.yml up -d --build  # 前端在容器内多阶段构建
```

## 开发约定

- 后端所有配置读 `pms.configs.settings`，不要 `os.getenv`
- 所有查询接口必须经 `scope_filter` 权限中间件（Sprint 1 实现）
- 敏感写操作写 `audit_log`
- 新增/修改代码都要加注释说明**为什么**
- 业绩评分必须 0.25 分段（前后端双校验）
