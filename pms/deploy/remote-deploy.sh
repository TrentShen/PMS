#!/bin/bash
# PMS 绩效管理系统 · 远程服务器部署脚本
# 由本地 expect-deploy.tcl 上传并调用，在服务器上执行
# 用法: bash /opt/pms/deploy/remote-deploy.sh

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

REMOTE_DIR="/opt/pms"
ENV_PROD="${REMOTE_DIR}/deploy/.env.prod"
CERT_DIR="${REMOTE_DIR}/deploy/certs"
NGINX_CONF="${REMOTE_DIR}/deploy/nginx.conf"

cd "$REMOTE_DIR"

# ---------- 1. 检查环境 ----------
info "检查 Docker 环境..."
command -v docker >/dev/null 2>&1 || error "未安装 Docker"

DOCKER_COMPOSE=""
if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker-compose"
else
    error "未找到 docker compose 命令"
fi
info "✅ Docker 就绪"

# ---------- 2. 检查必要配置 ----------
if [[ ! -f "$ENV_PROD" ]]; then
    error "deploy/.env.prod 不存在，请先配置生产环境变量"
fi

if [[ ! -f "$CERT_DIR/fullchain.pem" || ! -f "$CERT_DIR/privkey.pem" ]]; then
    error "HTTPS 证书缺失：deploy/certs/{fullchain.pem,privkey.pem}"
fi
info "✅ 生产配置与证书已就绪"

# ---------- 3. 备份 ----------
info "备份当前版本..."
BACKUP_DIR="${REMOTE_DIR}/backup.$(date +%Y%m%d%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -r backend "$BACKUP_DIR/" 2>/dev/null || true
cp -r web "$BACKUP_DIR/" 2>/dev/null || true
cp -r deploy "$BACKUP_DIR/" 2>/dev/null || true
info "✅ 备份到 ${BACKUP_DIR}"

# ---------- 4. 构建并启动 ----------
info "构建镜像并启动服务..."
$DOCKER_COMPOSE -f deploy/docker-compose.prod.yml down --remove-orphans 2>/dev/null || true
$DOCKER_COMPOSE -f deploy/docker-compose.prod.yml up -d --build

# ---------- 5. 等待后端就绪 ----------
info "等待后端就绪..."
READY=0
for i in $(seq 1 30); do
    if docker exec pms-backend python -c "import pms" 2>/dev/null; then
        READY=1
        break
    fi
    sleep 2
done
[[ "$READY" -eq 1 ]] || error "后端服务未能在 60 秒内就绪"
info "✅ 后端服务已就绪"

# ---------- 6. 数据库迁移 ----------
info "执行数据库迁移..."
docker exec pms-backend alembic upgrade head || warn "数据库迁移可能已是最新或失败"

# ---------- 7. 健康检查 ----------
info "健康检查..."
DOMAIN=$(grep FRONTEND_ORIGIN "$ENV_PROD" | head -1 | cut -d= -f2 | sed 's|https://||;s|http://||')
if curl -sf "http://localhost:80/health" >/dev/null 2>&1; then
    info "✅ 后端健康检查通过"
else
    error "健康检查失败"
fi

info "🚀 PMS 部署完成！"
info "🔗 访问地址: https://${DOMAIN}"
info "📋 API 文档: https://${DOMAIN}/api/docs"
info "🔍 健康检查: https://${DOMAIN}/api/v1/health"
