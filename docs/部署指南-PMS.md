# PMS 绩效管理系统 · 部署指南

## 项目概览

企业微信 H5 绩效管理系统（100 人内小团队）。

| 层 | 技术栈 |
|---|---|
| 后端 | FastAPI + SQLModel + Alembic (Python 3.12) |
| 前端 | Vite + React 18 + TypeScript + Ant Design |
| 数据库 | MySQL 8.0 |
| 缓存 | Redis 7 |
| 反代 | Nginx 1.27 (HTTPS + SPA 回退 + /api 反代) |
| 部署 | Docker Compose（全部容器化，服务器仅需 Docker） |

**目录结构：**

```
pms/
├── backend/               FastAPI 后端
│   ├── src/pms/           源码（api/configs/database/services/utils/scheduler）
│   ├── alembic/           数据库迁移
│   ├── Dockerfile         生产镜像
│   └── Makefile
├── web/                   Vite + React 前端
│   ├── src/               源码（pages/components/services/hooks/stores）
│   ├── Dockerfile         前端构建镜像（Node 多阶段构建）
│   └── .dockerignore
├── deploy/
│   ├── docker-compose.dev.yml    本地开发（仅起 MySQL + Redis）
│   ├── docker-compose.prod.yml   生产部署（backend/frontend/mysql/redis/nginx）
│   ├── nginx.conf                HTTPS + /api 反代配置
│   ├── deploy.sh                 一键部署脚本
│   └── certs/                    HTTPS 证书（不上传 Git）
└── docs/
    ├── PRD-绩效管理系统.md
    ├── 技术方案-绩效管理系统-V0.9.md
    ├── 部署指南-PMS.md
    └── 使用手册-绩效管理系统.md
```

---

## 前置准备

### 1. 服务器要求

- Linux（Ubuntu 20.04+ / CentOS 7+）
- **仅需 Docker**（`docker` + `docker compose`），前端构建在容器内完成
- 开放端口：**80**、**443**（防火墙/安全组）

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | bash
```

### 2. 域名 + DNS

需要一个公网域名（如 `pms.yourcompany.com`），将 A 记录指向服务器 IP。

### 3. 企业微信自建应用

在[企微管理后台](https://work.weixin.qq.com/wework_admin/)创建自建应用，获取以下信息：

| 配置项 | 获取路径 |
|---|---|
| `WECOM_CORPID` | 我的企业 → 企业信息 → 企业ID |
| `WECOM_AGENTID` | 应用管理 → 自建应用 → AgentId |
| `WECOM_SECRET` | 应用管理 → 自建应用 → Secret |
| `WECOM_CONTACT_SECRET` | 管理工具 → 通讯录同步 → Secret |

> **注意**：`WECOM_CONTACT_SECRET` 不同于应用 Secret，需在管理工具中单独开启通讯录同步权限。

---

## 一键部署

**服务器只需安装 Docker**，前端构建在容器内完成。

```bash
cd pms/deploy
bash deploy.sh
```

脚本交互式引导：配置填写 → 证书准备 → **一个 `docker compose up -d --build` 完成所有构建和启动**。

### 执行流程

```
检查 Docker 环境
    ↓
配置 .env.prod（交互填入企微信息，自动生成随机密钥）
    ↓
HTTPS 证书准备
  ├─ [1] 手动放入已有证书
  ├─ [2] Let's Encrypt 自动申请
  └─ [3] 自签名证书（仅内网测试）
    ↓
docker compose up -d --build  ← 完全容器化
  ├─ backend  (Python 后端镜像)
  ├─ frontend (Node 构建 → 产出静态文件到共享卷)
  ├─ mysql    (MySQL 8.0)
  ├─ redis    (Redis 7)
  └─ nginx    (HTTPS + 前端静态 + /api 反代)
    ↓
数据库迁移（alembic upgrade head）
```

---

## 手动部署（如需分步操作）

### 1. 配置环境变量

```bash
cp .env.example .env.prod && vi .env.prod
```

关键字段：

```ini
APP_ENV=prod
APP_SECRET=<openssl rand -hex 32>

MYSQL_HOST=mysql          # 容器内服务名，勿改
MYSQL_PORT=3306
MYSQL_USER=pms
MYSQL_PASSWORD=<随机密码>
MYSQL_DATABASE=pms

REDIS_HOST=redis          # 容器内服务名，勿改
REDIS_PORT=6379

WECOM_CORPID=<企业ID>
WECOM_AGENTID=<应用AgentId>
WECOM_SECRET=<应用Secret>
WECOM_CONTACT_SECRET=<通讯录同步Secret>
WECOM_REDIRECT_URI=https://pms.yourcompany.com/auth/callback

FRONTEND_ORIGIN=https://pms.yourcompany.com
```

### 2. HTTPS 证书

```bash
mkdir -p deploy/certs
# 方式A: Let's Encrypt
sudo certbot certonly --standalone -d pms.yourcompany.com
sudo cp /etc/letsencrypt/live/pms.yourcompany.com/{fullchain,privkey}.pem deploy/certs/

# 方式B: 已有证书直接复制到 deploy/certs/
```

### 3. 修改 Nginx 域名

```bash
sed -i 's/pms.company.com/pms.yourcompany.com/g' deploy/nginx.conf
```

### 4. 一键启动（含前端容器内构建）

```bash
cd deploy
docker compose -f docker-compose.prod.yml up -d --build
```

### 5. 数据库迁移

```bash
docker exec pms-backend alembic upgrade head
```

> **注意**：初始迁移 `a088a1294289_v0_9_initial_schema.py` 已重写为完整版本，会一次性创建所有 16 张表。新环境直接执行 `alembic upgrade head` 即可；若从旧版本升级且数据库中已存在这些表，需先执行 `alembic stamp a088a1294289` 对齐版本号，再执行 `alembic upgrade head`。

### 6. 验证

```bash
curl https://pms.yourcompany.com/api/health
# 预期: {"status":"ok"}
```

---

## 企微管理后台配置（上线前必做）

### 1. 配置可信域名

应用管理 → 自建应用 → 网页授权及 JS-SDK → 可信域名

- 填入 `pms.yourcompany.com`
- 下载 `MP_verify_xxx.txt` 校验文件
- 放到 `web/public/` 目录下（Vite 构建时自动复制到根路径）
- 重新 `docker compose up -d --build` 即可生效

### 2. 配置 OAuth 回调地址

应用管理 → 自建应用 → 网页授权及 JS-SDK → 授权回调域

- 填入 `pms.yourcompany.com`

### 3. 开启通讯录同步

管理工具 → 通讯录同步 → 开启 API 同步

- 获取 `SECRET` 填入 `.env.prod` 的 `WECOM_CONTACT_SECRET`
- 设置同步权限范围

---

## 企微集成说明

| 功能 | 对应代码 | 说明 |
|---|---|---|
| OAuth 免登 | `backend/src/pms/services/wecom.py:65` | code 换 userid（静默授权） |
| 通讯录同步 | `backend/src/pms/services/wecom.py:76-103` | 拉取部门 + 用户详情 |
| 消息推送 | `backend/src/pms/services/wecom.py:108-161` | 文本、卡片、Markdown 三种格式 |
| JWT 登录态 | `backend/src/pms/services/auth.py:17-76` | 7 天有效期，Redis 缓存用户信息 |
| 定时提醒 | `backend/src/pms/scheduler/jobs.py:173-183` | 阶段截止提醒 + 通用提醒 |
| 每日通讯录同步 | `backend/src/pms/scheduler/jobs.py:160-170` | 凌晨 02:00 全量同步 |
| 前端 OAuth 回调 | `web/src/pages/AuthCallback.tsx` | 处理企微 code 回调 |

---

## 常用运维命令

```bash
# 查看服务状态
cd deploy && docker compose -f docker-compose.prod.yml ps

# 查看日志
docker logs -f pms-backend
docker logs -f pms-nginx

# 重启服务
docker compose -f docker-compose.prod.yml restart backend

# 停止所有服务
docker compose -f docker-compose.prod.yml down

# 更新部署（代码有改动后）
cd deploy && bash deploy.sh    # 重新构建+启动

# 进入容器调试
docker exec -it pms-backend bash

# 数据库备份
docker exec pms-mysql mysqldump -u pms -p pms > backup_$(date +%Y%m%d).sql
```

---

## 安全注意事项

- `.env` / `.env.prod` / `deploy/certs/` 已加入 `.gitignore`，不会被提交到 Git
- 生产环境 `APP_SECRET` 务必使用 `openssl rand -hex 32` 生成随机串
- MySQL 密码建议随机生成，不要使用 `pms_password` 这种默认值
- 企微 Secret 具有 API 调用权限，请勿在日志中打印或泄露
