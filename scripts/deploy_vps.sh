#!/usr/bin/env bash
# Speakeasy · VPS 部署脚本（手动 + CI 通用）
#
# 使用方式：
#   手动：cd /opt/speakeasy && ./scripts/deploy_vps.sh
#   CI：  通过 GitHub Actions ssh-action 调用，环境变量由 CI 注入
#
# 环境变量：
#   IMAGE_TAG       镜像 tag（默认 latest）
#   SKIP_GIT        跳过 git pull（默认 0，CI 模式建议设 1）
#   DRY_RUN         只打印命令不执行（默认 0）
#   CI              CI 模式：跳过交互提示（GitHub Actions 自动设置）
#   APP_IMAGE       完整镜像路径（CI 模式注入，覆盖自动拼接）
#   ALIYUN_REGISTRY ACR 地址（CI 模式注入）
#   ALIYUN_USERNAME ACR 用户名（CI 模式注入）
#   ALIYUN_PASSWORD ACR 密码（CI 模式注入）

set -euo pipefail

# ── 颜色 ──────────────────────────────────────────────
C_RST=$'\033[0m'; C_RED=$'\033[31m'; C_GRN=$'\033[32m'
C_YEL=$'\033[33m'; C_BLU=$'\033[34m'; C_DIM=$'\033[2m'
say()  { printf "%s▸%s %s\n"     "$C_BLU" "$C_RST" "$*"; }
ok()   { printf "%s✓%s %s\n"     "$C_GRN" "$C_RST" "$*"; }
warn() { printf "%s!%s %s\n"     "$C_YEL" "$C_RST" "$*" >&2; }
die()  { printf "%s✗ %s%s\n"     "$C_RED" "$*"   "$C_RST" >&2; exit 1; }
run()  {
  if [[ "${DRY_RUN:-0}" == "1" ]]; then
    printf "%s[dry-run]%s %s\n" "$C_DIM" "$C_RST" "$*"
  else
    eval "$@"
  fi
}

SERVICE_NAME="dev-web"
COMPOSE_FILE="docker-compose.yml"
HEALTH_URL="http://localhost:8000/health"
HEALTH_TIMEOUT_SEC=60
IMAGE_TAG="${IMAGE_TAG:-latest}"
IS_CI="${CI:-0}"

# ── 前置检查 ─────────────────────────────────────────
say "环境前置检查"

[[ -f "$COMPOSE_FILE" ]]    || die "找不到 $COMPOSE_FILE，请确认 cwd 是应用目录"
[[ -f .env.production ]]    || die "缺少 .env.production"
command -v docker >/dev/null || die "未安装 docker"
docker compose version >/dev/null 2>&1 || die "docker compose v2 未启用"

# JWT_SECRET 持久化检查
if ! grep -q '^JWT_SECRET=' .env.production; then
  if [[ "$IS_CI" != "0" ]]; then
    # CI 模式：自动生成
    SECRET=$(openssl rand -base64 48 | tr -d '\n')
    SECRET_ESC=${SECRET//\$/\$\$}
    echo "JWT_SECRET=${SECRET_ESC}" >> .env.production
    ok "自动生成 JWT_SECRET"
  else
    warn ".env.production 没有 JWT_SECRET · 容器重启用户登录会全失效"
    read -rp "现在生成一个随机 JWT_SECRET 写入 .env.production？(y/N) " ans
    if [[ "${ans,,}" == "y" ]]; then
      SECRET=$(openssl rand -base64 48 | tr -d '\n')
      SECRET_ESC=${SECRET//\$/\$\$}
      echo "JWT_SECRET=${SECRET_ESC}" >> .env.production
      ok "已写入 JWT_SECRET"
    fi
  fi
fi

# ── 1. 拉新代码（可选，失败不阻塞部署）────────────────
if [[ "${SKIP_GIT:-0}" != "1" ]] && [[ -d .git ]]; then
  say "git pull"
  if run "git pull --ff-only origin main 2>&1"; then
    ok "代码已更新 ($(git rev-parse --short HEAD))"
  else
    warn "git pull 失败（国内网络问题），继续部署（靠 ACR 镜像）"
  fi
fi

# ── 2. 登录阿里云 ACR ────────────────────────────────
if [[ -n "${ALIYUN_PASSWORD:-}" ]] && [[ -n "${ALIYUN_REGISTRY:-}" ]]; then
  # CI 模式：环境变量已由 GitHub Actions 注入
  say "登录阿里云 ACR"
  run "echo \"\$ALIYUN_PASSWORD\" | docker login \"\$ALIYUN_REGISTRY\" -u \"\$ALIYUN_USERNAME\" --password-stdin"
elif [[ -f .env ]] && grep -q '^ALIYUN_PASSWORD=' .env; then
  # 手动模式：从 .env 读取
  say "登录阿里云 ACR（从 .env）"
  set -a; source .env; set +a
  : "${ALIYUN_REGISTRY:?需要 ALIYUN_REGISTRY}"
  : "${ALIYUN_USERNAME:?需要 ALIYUN_USERNAME}"
  : "${ALIYUN_PASSWORD:?需要 ALIYUN_PASSWORD}"
  : "${ALIYUN_NAMESPACE:?需要 ALIYUN_NAMESPACE}"
  run "echo \"\$ALIYUN_PASSWORD\" | docker login \"\$ALIYUN_REGISTRY\" -u \"\$ALIYUN_USERNAME\" --password-stdin"
else
  warn "没有 ACR 凭证 · 跳过登录（如已 docker login 过则忽略）"
fi

# ── 3. 设置 APP_IMAGE ────────────────────────────────
if [[ -n "${APP_IMAGE:-}" ]]; then
  # CI 模式：APP_IMAGE 已由 workflow 注入
  ok "镜像 $APP_IMAGE"
elif [[ -n "${ALIYUN_REGISTRY:-}" ]] && [[ -n "${ALIYUN_NAMESPACE:-}" ]]; then
  APP_IMAGE="${ALIYUN_REGISTRY}/${ALIYUN_NAMESPACE}/speakeasy:${IMAGE_TAG}"
  ok "镜像 $APP_IMAGE"
fi

if [[ -n "${APP_IMAGE:-}" ]]; then
  # 幂等写入 .env
  if [[ -f .env ]]; then
    grep -v '^APP_IMAGE=' .env > .env.tmp && mv .env.tmp .env
  fi
  echo "APP_IMAGE=$APP_IMAGE" >> .env
  ok "APP_IMAGE 已写入 .env"
fi

# ── 4. 拉镜像 ──────────────────────────────────────
say "拉取镜像"
run "docker compose -f $COMPOSE_FILE pull $SERVICE_NAME"

# ── 5. 重建容器 ──────────────────────────────────────
say "重建容器（--force-recreate）"
run "docker compose -f $COMPOSE_FILE up -d --force-recreate $SERVICE_NAME"
run "docker image prune -f"

# ── 6. 健康检查 ────────────────────────────────────
say "等待健康检查（最多 ${HEALTH_TIMEOUT_SEC}s）"
START=$(date +%s)
HEALTHY=0
while (( $(date +%s) - START < HEALTH_TIMEOUT_SEC )); do
  if docker compose -f "$COMPOSE_FILE" exec -T "$SERVICE_NAME" curl -sf "$HEALTH_URL" >/dev/null 2>&1; then
    HEALTHY=1
    break
  fi
  sleep 2
done
if (( HEALTHY == 1 )); then
  ok "/health 200"
else
  warn "$HEALTH_URL 在 ${HEALTH_TIMEOUT_SEC}s 内未返回 200"
  docker compose -f "$COMPOSE_FILE" logs --tail=80 "$SERVICE_NAME" || true
  die "部署失败 · 查看上方日志"
fi

# ── 7. DB 摘要 ───────────────────────────────────
say "数据校验"
docker compose -f "$COMPOSE_FILE" exec -T "$SERVICE_NAME" python -c "
import os, sqlite3
db = os.environ.get('SPEAKEASY_DB_PATH', '/app/data/speakeasy.db')
con = sqlite3.connect(db)
def cnt(t):
    try: return con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
    except Exception: return '-'
print(f'  DB         : {db}')
print(f'  users      : {cnt(\"users\")}')
print(f'  bbc_eaw    : {cnt(\"bbc_eaw_episodes\")}')
print(f'  sessions   : {cnt(\"sessions\")}')
print(f'  cards      : {cnt(\"pronunciation_cards\")}')
print(f'  llm_logs   : {cnt(\"llm_call_logs\")}')
" 2>&1 || warn "DB 摘要查询失败（容器可能还没就绪）"

# ── 8. 收尾 ───────────────────────────────────────
ok "部署完成 · $(date '+%F %T')"
