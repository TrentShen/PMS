#!/usr/bin/env bash
# PMS 绩效管理系统 · 经 JumpServer 堡垒机部署
# 用法: bash pms/deploy/bastion-deploy.sh
# 环境变量可覆盖默认值: BASTION_USER, BASTION_KEY, BASTION_HOST, BASTION_PORT,
#                       BASTION_ASSET, BASTION_SFTP_ROOT, REMOTE_DIR

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ---------- 配置 ----------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOCAL_DIR="$(cd "$PROJECT_DIR" && pwd)"
LOCAL_TAR="/tmp/pms-deploy.$(date +%s).tar.gz"

BASTION_USER="${BASTION_USER:-TrentShen}"
BASTION_KEY="${BASTION_KEY:-$HOME/.ssh/TrentShen-jumpserver.pem}"
BASTION_HOST="${BASTION_HOST:-bastion.matrixorigin.cn}"
BASTION_PORT="${BASTION_PORT:-2222}"
# PMS 在 JumpServer 中的资产登录账号及资产 IP（不是办公网直连 IP）
BASTION_TARGET="${BASTION_TARGET:-root}"
BASTION_ASSET="${BASTION_ASSET:-10.206.32.8}"
# koko SFTP 虚拟目录前缀，映射到资产的 /tmp
BASTION_SFTP_ROOT="${BASTION_SFTP_ROOT:-/VM-10-222-4-38}"

REMOTE_DIR="${REMOTE_DIR:-/opt/pms}"
REMOTE_TAR_NAME="pms-deploy.tar.gz"
REMOTE_TAR_PATH="/tmp/${REMOTE_TAR_NAME}"

BASTION_DEST="${BASTION_USER}@${BASTION_TARGET}@${BASTION_ASSET}@${BASTION_HOST}"

# ---------- 检查 ----------
[[ -f "$BASTION_KEY" ]] || error "JumpServer 私钥不存在: $BASTION_KEY"
chmod 600 "$BASTION_KEY" 2>/dev/null || true
command -v ssh >/dev/null 2>&1 || error "请先安装 ssh"
command -v sftp >/dev/null 2>&1 || error "请先安装 sftp"
command -v tar >/dev/null 2>&1 || error "请先安装 tar"

info "堡垒机配置: ${BASTION_USER}@${BASTION_TARGET}@${BASTION_ASSET}@${BASTION_HOST}:${BASTION_PORT}"
info "SFTP 目录: ${BASTION_SFTP_ROOT}"

# ---------- 1. 本地打包 ----------
info "📦 本地打包 PMS..."
COPYFILE_DISABLE=1 tar czf "$LOCAL_TAR" \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='.venv' \
  --exclude='.venv-local' \
  --exclude='.pytest_cache' \
  --exclude='.ruff_cache' \
  --exclude='__pycache__' \
  --exclude='.DS_Store' \
  --exclude='*.pyc' \
  --exclude='.env' \
  --exclude='.env.prod' \
  --exclude='certs' \
  --exclude='._*' \
  -C "$LOCAL_DIR" .
info "✅ 打包完成: $LOCAL_TAR"

# ---------- 2. 上传 ----------
info "⬆️  上传部署包到堡垒机 SFTP (${BASTION_SFTP_ROOT})..."
{
  printf 'put %s %s/%s\n' "$LOCAL_TAR" "$BASTION_SFTP_ROOT" "$REMOTE_TAR_NAME"
  printf 'bye\n'
} | sftp -b - -P "$BASTION_PORT" -i "$BASTION_KEY" \
      -o BatchMode=yes -o ConnectTimeout=10 \
      "$BASTION_DEST" >/tmp/pms-sftp.log 2>&1 || {
  cat /tmp/pms-sftp.log
  error "SFTP 上传失败"
}
info "✅ 上传完成"

# ---------- 3. 远程执行 ----------
info "🔧 在远程服务器执行部署..."

bastion_exec() {
  local cmd="$1"
  local m="KX$$"
  local out rc
  out=$(
    (
      sleep 2
      printf 'stty -echo 2>/dev/null; echo %sS\n' "$m"
      printf 'echo; %s; echo __PMS_EXIT__$?__\n' "$cmd"
      printf 'echo %sE\nexit\n' "$m"
      sleep 3
    ) | ssh -tt -p "$BASTION_PORT" -i "$BASTION_KEY" \
         -o BatchMode=yes -o ConnectTimeout=10 \
         "$BASTION_DEST" 2>&1 | \
      tr -d '\r' | awk -v s="${m}S" -v e="${m}E" \
        'index($0,e){f=0;next} index($0,s){f=1;next} f{print}' | \
      grep -v '^root@'
  )
  # 退出码标记可能与提示符粘连在同一行，不做行首锚定；|| true 防空匹配时 set -e 哑死
  rc=$(printf '%s\n' "$out" | grep -o '__PMS_EXIT__[0-9][0-9]*__' | tail -1 | sed 's/__PMS_EXIT__//;s/__//' || true)
  # 展示输出时去掉标记
  printf '%s\n' "$out" | sed 's/__PMS_EXIT__[0-9][0-9]*__//g'
  if [[ -z "$rc" ]]; then
    error "远端命令未返回退出码(连接可能中断): $cmd"
  fi
  if [[ "$rc" -ne 0 ]]; then
    error "远端命令失败(EXIT=$rc): $cmd"
  fi
}

# 备份服务器现有 .env.prod 和 certs
bastion_exec "cd ${REMOTE_DIR} && cp -f deploy/.env.prod /tmp/pms-env-prod.bak 2>/dev/null || true"
bastion_exec "cp -rf ${REMOTE_DIR}/deploy/certs /tmp/pms-certs.bak 2>/dev/null || true"

# 解压覆盖
bastion_exec "cd ${REMOTE_DIR} && tar xzf ${REMOTE_TAR_PATH} && rm -f ${REMOTE_TAR_PATH}"

# 恢复敏感配置
bastion_exec "cp -f /tmp/pms-env-prod.bak ${REMOTE_DIR}/deploy/.env.prod 2>/dev/null || true"
bastion_exec "cp -rf /tmp/pms-certs.bak ${REMOTE_DIR}/deploy/certs 2>/dev/null || true"

# 设置权限并执行远程部署脚本
bastion_exec "chmod +x ${REMOTE_DIR}/deploy/remote-deploy.sh"
info "🚀 后台执行 remote-deploy.sh，轮询日志（超时 20 分钟）..."
bastion_exec "nohup bash ${REMOTE_DIR}/deploy/remote-deploy.sh > /tmp/pms-deploy.log 2>&1 &"

# 每 15s 拉一次远端日志，增量打印；出现结束/错误标记或超时则退出
DEPLOY_LOG_TIMEOUT=1200
elapsed=0
last_count=0
while :; do
  sleep 15
  elapsed=$((elapsed + 15))
  remote_log=$(bastion_exec "cat /tmp/pms-deploy.log 2>/dev/null || true")
  total=$(printf '%s\n' "$remote_log" | wc -l | tr -d ' ')
  if (( total > last_count )); then
    printf '%s\n' "$remote_log" | tail -n +$((last_count + 1))
    last_count=$total
  fi
  if printf '%s\n' "$remote_log" | grep -q '部署流程结束'; then
    info "✅ 远程部署完成"
    break
  fi
  if printf '%s\n' "$remote_log" | grep -q '\[ERROR\]'; then
    error "远程部署失败（详见上方日志）"
  fi
  if (( elapsed >= DEPLOY_LOG_TIMEOUT )); then
    error "部署日志轮询超时（20 分钟），请登录服务器查看 /tmp/pms-deploy.log"
  fi
done

# ---------- 4. 清理 ----------
# 远端 /tmp 的 env/证书备份含敏感信息，部署结束后必须删除（2026-08-27 审计发现残留）
info "🧹 清理远端敏感临时文件..."
bastion_exec "rm -rf /tmp/pms-env-prod.bak /tmp/pms-certs.bak 2>/dev/null || true"
info "🧹 清理本地临时文件..."
rm -f "$LOCAL_TAR" /tmp/pms-sftp.log
info "✅ 部署流程结束"
