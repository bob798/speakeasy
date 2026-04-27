#!/usr/bin/env bash
# Speakeasy · VPS 一键部署脚本
#
# 在 VPS 上以应用所在目录为 cwd 执行：
#   cd /opt/speakeasy
#   ./scripts/deploy_vps.sh                    # 默认拉最新代码 + latest 镜像 + 重建
#   IMAGE_TAG=v0.9.6 ./scripts/deploy_vps.sh   # 指定镜像 tag
#   SKIP_PULL=1     ./scripts/deploy_vps.sh    # 跳过 git/docker pull · 仅重启
#   DRY_RUN=1       ./scripts/deploy_vps.sh    # 只打印将执行的命令
#
# 前置：
#   1. cwd 是 git 仓库（本地代码用于读 docker-compose.yml）
#   2. .env.production 存在，含 JWT_SECRET 与 OPENROUTER_API_KEY 等
#   3. .env 含 ALIYUN_REGISTRY/USERNAME/PASSWORD/NAMESPACE（用于 ACR 登录）
#   4. 已加入 docker compose 网络 liboboa（external: true）

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

# ── 前置检查 ─────────────────────────────────────────
say "环境前置检查"

[[ -f "$COMPOSE_FILE" ]]    || die "找不到 $COMPOSE_FILE，请确认 cwd 是应用目录"
[[ -f .env.production ]]    || die "缺少 .env.production"
command -v docker >/dev/null || die "未安装 docker"
docker compose version >/dev/null 2>&1 || die "docker compose v2 未启用"

# .env.production 里 $ 未转义会让 compose 警告 "variable not set"
if grep -nE '(^|=).*[^$]\$[a-zA-Z_]' .env.production >/dev/null; then
  warn ".env.production 里有未转义的 \$，compose 会把它当变量插值。建议改成 \$\$"
  grep -nE '(^|=).*[^$]\$[a-zA-Z_]' .env.production || true
fi

# JWT_SECRET 持久化检查
if ! grep -q '^JWT_SECRET=' .env.production; then
  warn ".env.production 没有 JWT_SECRET · 容器重启用户登录会全失效"
  read -rp "现在生成一个随机 JWT_SECRET 写入 .env.production？(y/N) " ans
  if [[ "${ans,,}" == "y" ]]; then
    SECRET=$(openssl rand -base64 48 | tr -d '\n')
    # 转义所有 $ 为 $$（base64 中 $ 罕见，但保险）
    SECRET_ESC=${SECRET//\$/\$\$}
    echo "JWT_SECRET=${SECRET_ESC}" >> .env.production
    ok "已写入 JWT_SECRET（60 天有效期）"
  fi
fi

# ── 1. 拉新代码（compose 文件可能更新）──────────────
if [[ "${SKIP_PULL:-0}" != "1" ]]; then
  say "git pull"
  if [[ -d .git ]]; then
    BEFORE=$(git rev-parse HEAD)
    run "git pull --ff-only origin main"
    AFTER=$(git rev-parse HEAD)
    if [[ "$BEFORE" != "$AFTER" ]]; then
      ok "代码更新到 $(git rev-parse --short HEAD)"
    else
      ok "代码已是最新 ($(git rev-parse --short HEAD))"
    fi
  else
    warn "非 git 仓库，跳过 git pull"
  fi
fi

# ── 2. 登录阿里云 ACR ────────────────────────────────
if [[ -f .env ]] && grep -q '^ALIYUN_PASSWORD=' .env; then
  say "登录阿里云 ACR"
  # shellcheck disable=SC1091
  set -a; source .env; set +a
  : "${ALIYUN_REGISTRY:?需要 .env 里设 ALIYUN_REGISTRY}"
  : "${ALIYUN_USERNAME:?需要 ALIYUN_USERNAME}"
  : "${ALIYUN_PASSWORD:?需要 ALIYUN_PASSWORD}"
  : "${ALIYUN_NAMESPACE:?需要 ALIYUN_NAMESPACE}"
  run "echo \"\$ALIYUN_PASSWORD\" | docker login \"\$ALIYUN_REGISTRY\" -u \"\$ALIYUN_USERNAME\" --password-stdin"
  IMAGE="${ALIYUN_REGISTRY}/${ALIYUN_NAMESPACE}/speakeasy:${IMAGE_TAG}"
  ok "镜像目标 $IMAGE"
  # 幂等更新 APP_IMAGE：先删旧的，再追加新值。避免 .env 行数随每次部署增长
  if grep -q '^APP_IMAGE=' .env; then
    grep -v '^APP_IMAGE=' .env > .env.tmp
    mv .env.tmp .env
  fi
  echo "APP_IMAGE=$IMAGE" >> .env
  ok "APP_IMAGE 已写入 .env"
else
  warn "没找到 .env 或 ALIYUN_PASSWORD · 跳过 ACR 登录（如已 docker login 过则忽略）"
fi

# ── 3. 拉镜像 ──────────────────────────────────────
if [[ "${SKIP_PULL:-0}" != "1" ]]; then
  say "拉取镜像"
  run "docker compose -f $COMPOSE_FILE pull $SERVICE_NAME"
fi

# ── 4. 重建容器（关键：让新挂载/新 env 生效）─────────
say "重建容器（--force-recreate）"
run "docker compose -f $COMPOSE_FILE up -d --force-recreate $SERVICE_NAME"

# 清旧镜像
run "docker image prune -f"

# ── 5. 健康检查 ────────────────────────────────────
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
  die "部署可能失败 · 查看上方日志，必要时 ./scripts/deploy_vps.sh --rollback（暂未实现）"
fi

# ── 6. seeder 与 DB 摘要 ───────────────────────────
say "数据校验"
docker compose -f "$COMPOSE_FILE" logs --tail=200 "$SERVICE_NAME" 2>/dev/null | grep -E "bbc_eaw seeder|create_all|Application startup" | tail -5 || true

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
" 2>&1 || warn "DB 摘要查询失败（容器可能还没就绪）"

# ── 7. 收尾 ───────────────────────────────────────
ok "部署完成 · $(date '+%F %T')"
echo
echo "下一步检查清单："
echo "  1. 浏览器访问 https://<your-domain>/"
echo "  2. DevTools → Application → Service Workers → Unregister + Cmd-Shift-R"
echo "  3. 进发音练习 → 应看到 BBC English at Work · 67 集"
echo
echo "实时日志：  docker compose -f $COMPOSE_FILE logs -f $SERVICE_NAME"
echo "回滚镜像：  IMAGE_TAG=<上一版 tag> ./scripts/deploy_vps.sh"
