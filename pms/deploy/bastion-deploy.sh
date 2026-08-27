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
      grep -v '^root@' || true  # 输出全被过滤时 grep 返回 1，不能让 set -e 哑死
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
info "🚀 执行 remote-deploy.sh（输出实时回传，完成自动断开）..."

# 同步直跑 + 实时流式回传。关键点：ssh stdin 必须保持打开直到远端脚本结束——
# 交互式 shell 读到 EOF 会立即退出并杀掉前台部署进程（原 sleep 600 的作用，
# 但固定时长会在长部署时误杀）。用 FIFO 让 writer 等到退出码标记出现再关闭 stdin。
STREAM_LOG=/tmp/pms-remote-deploy.log
: > "$STREAM_LOG"
FIFO=$(mktemp -u /tmp/pms-ssh-stdin.XXXXXX)
mkfifo "$FIFO"
(
  printf 'stty -echo 2>/dev/null\n'
  printf 'bash %s 2>&1; echo __PMS_EXIT__$?__\n' "${REMOTE_DIR}/deploy/remote-deploy.sh"
  printf 'exit\n'
  # 兜底 25 分钟：标记始终不出现（连接中断）也关闭，避免死锁
  for _ in $(seq 1 150); do
    grep -q '__PMS_EXIT__' "$STREAM_LOG" 2>/dev/null && break
    sleep 10
  done
) > "$FIFO" &
WRITER_PID=$!

set +e
ssh -tt -p "$BASTION_PORT" -i "$BASTION_KEY" \
     -o BatchMode=yes -o ConnectTimeout=10 \
     "$BASTION_DEST" < "$FIFO" 2>&1 | tr -d '\r' | tee "$STREAM_LOG"
set -e
wait "$WRITER_PID" 2>/dev/null || true
rm -f "$FIFO"

REMOTE_RC=$(grep -o '__PMS_EXIT__[0-9][0-9]*__' "$STREAM_LOG" | tail -1 | sed 's/__PMS_EXIT__//;s/__//' || true)
if [[ -z "$REMOTE_RC" ]]; then
  error "远端部署未返回退出码（连接中断），请登录服务器手工执行 bash /opt/pms/deploy/remote-deploy.sh"
fi
if [[ "$REMOTE_RC" -ne 0 ]]; then
  error "远端部署失败(EXIT=$REMOTE_RC)，详见上方输出"
fi
info "✅ 远程部署完成"

# ---------- 4. 清理 ----------
# 远端 /tmp 的 env/证书备份含敏感信息，部署结束后必须删除（2026-08-27 审计发现残留）
info "🧹 清理远端敏感临时文件..."
bastion_exec "rm -rf /tmp/pms-env-prod.bak /tmp/pms-certs.bak 2>/dev/null || true"
info "🧹 清理本地临时文件..."
rm -f "$LOCAL_TAR" /tmp/pms-sftp.log
info "✅ 部署流程结束"
