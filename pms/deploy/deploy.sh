#!/usr/bin/env bash
# PMS 绩效管理系统 · Docker 一键部署
# 服务器只需安装 Docker，其余全部容器化
# 用法: bash deploy.sh

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_PROD="$SCRIPT_DIR/.env.prod"
NGINX_CONF="$SCRIPT_DIR/nginx.conf"

# ---------- 1. 检查 Docker ----------
info "检查 Docker 环境..."
command -v docker >/dev/null 2>&1 || error "请先安装 Docker: curl -fsSL https://get.docker.com | bash"

DOCKER_COMPOSE=""
if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker-compose"
else
    error "未找到 docker compose 命令"
fi
info "✅ Docker 就绪"

# ---------- 2. 生成 .env.prod ----------
if [[ ! -f "$ENV_PROD" ]]; then
    echo ""
    warn "首次部署，配置生产环境变量："
    echo ""

    read -r -p "  域名 (如 pms.yourcompany.com): " DOMAIN
    [[ -z "$DOMAIN" ]] && error "域名不能为空"

    read -r -p "  WECOM_CORPID (企业ID): " WECOM_CORPID
    read -r -p "  WECOM_AGENTID (应用AgentId): " WECOM_AGENTID
    read -r -p "  WECOM_SECRET (应用Secret): " WECOM_SECRET
    read -r -p "  WECOM_CONTACT_SECRET (通讯录同步Secret，可留空): " WECOM_CONTACT_SECRET

    APP_SECRET=$(openssl rand -hex 32)
    MYSQL_PASSWORD=$(openssl rand -hex 16)

    cat > "$ENV_PROD" <<EOF
# PMS 生产环境变量（生成于 $(date '+%Y-%m-%d %H:%M:%S')）
APP_ENV=prod
APP_PORT=8000
APP_SECRET=${APP_SECRET}

MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_USER=pms
MYSQL_PASSWORD=${MYSQL_PASSWORD}
MYSQL_DATABASE=pms

REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

WECOM_CORPID=${WECOM_CORPID}
WECOM_AGENTID=${WECOM_AGENTID}
WECOM_SECRET=${WECOM_SECRET}
WECOM_CONTACT_SECRET=${WECOM_CONTACT_SECRET}
WECOM_REDIRECT_URI=https://${DOMAIN}/auth/callback

FRONTEND_ORIGIN=https://${DOMAIN}
EOF
    info "✅ .env.prod 已生成"
else
    info "✅ .env.prod 已存在"
    DOMAIN=$(grep WECOM_REDIRECT_URI "$ENV_PROD" | head -1 | sed 's|.*https://||; s|/auth/callback||')
fi

# ---------- 3. HTTPS 证书 ----------
CERT_DIR="$SCRIPT_DIR/certs"
if [[ ! -f "$CERT_DIR/fullchain.pem" || ! -f "$CERT_DIR/privkey.pem" ]]; then
    echo ""
    warn "HTTPS 证书缺失"
    echo "  [1] 手动放入已有证书到 certs/"
    echo "  [2] Let's Encrypt 自动申请 (certbot)"
    echo "  [3] 自签名证书 (仅内网测试，企微不认)"
    read -r -p "  选择 [1-3]: " CERT_CHOICE

    case "$CERT_CHOICE" in
        1)
            mkdir -p "$CERT_DIR"
            read -r -p "  fullchain.pem 路径: " FULLCHAIN_SRC
            read -r -p "  privkey.pem 路径: " PRIVKEY_SRC
            [[ -f "$FULLCHAIN_SRC" ]] && cp "$FULLCHAIN_SRC" "$CERT_DIR/fullchain.pem"
            [[ -f "$PRIVKEY_SRC" ]] && cp "$PRIVKEY_SRC" "$CERT_DIR/privkey.pem"
            info "✅ 证书已复制"
            ;;
        2)
            command -v certbot >/dev/null 2>&1 || error "请先安装 certbot: sudo apt install certbot"
            mkdir -p "$CERT_DIR"
            sudo certbot certonly --standalone -d "$DOMAIN"
            sudo cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$CERT_DIR/"
            sudo cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" "$CERT_DIR/"
            sudo chown "$(whoami)" "$CERT_DIR"/*.pem
            info "✅ Let's Encrypt 证书已获取"
            ;;
        3)
            mkdir -p "$CERT_DIR"
            openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
                -keyout "$CERT_DIR/privkey.pem" \
                -out "$CERT_DIR/fullchain.pem" \
                -subj "/CN=${DOMAIN:-pms.local}" 2>/dev/null
            warn "自签名证书已生成，生产环境企微 OAuth 不可用"
            ;;
        *)
            error "无效选择"
            ;;
    esac
else
    info "✅ HTTPS 证书已就绪"
fi

# ---------- 4. 替换 Nginx 域名 ----------
if grep -q "pms.company.com" "$NGINX_CONF" 2>/dev/null; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/pms.company.com/${DOMAIN}/g" "$NGINX_CONF"
    else
        sed -i "s/pms.company.com/${DOMAIN}/g" "$NGINX_CONF"
    fi
    info "✅ nginx.conf 域名已替换为 ${DOMAIN}"
fi

# ---------- 5. 启动 ----------
info "构建镜像并启动服务..."
cd "$SCRIPT_DIR"
$DOCKER_COMPOSE -f docker-compose.prod.yml down --remove-orphans 2>/dev/null || true
$DOCKER_COMPOSE -f docker-compose.prod.yml up -d --build

# 等待后端就绪
info "等待服务就绪..."
for i in $(seq 1 30); do
    if docker exec pms-backend python -c "import pms" 2>/dev/null; then
        break
    fi
    sleep 2
done

# 数据库迁移
info "执行数据库迁移..."
docker exec pms-backend alembic upgrade head 2>/dev/null || warn "数据库迁移跳过（可能已是最新）"

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║  🚀 PMS 部署完成！                       ║"
echo "  ╠══════════════════════════════════════════╣"
echo "  ║  地址:    https://${DOMAIN}              ║"
echo "  ║  API 文档: https://${DOMAIN}/api/docs    ║"
echo "  ║  健康检查: https://${DOMAIN}/api/health  ║"
echo "  ║                                          ║"
echo "  ║  🔔 企微管理后台待办:                     ║"
echo "  ║  1. 网页授权 → 可信域名: ${DOMAIN}        ║"
echo "  ║  2. 域名校验文件放到 deploy/web-dist/    ║"
echo "  ║  3. 通讯录同步 → 开启并填入 Secret       ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""
