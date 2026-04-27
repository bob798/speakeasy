#!/bin/bash
# 一键拉起前后端 dev 环境，默认监听 0.0.0.0 支持内网访问
# 用法: ./start-dev.sh
# 停止: Ctrl+C （会同时杀掉前后端）

set -e
cd "$(dirname "$0")"

BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

# 打印本机内网 IP，方便手机访问
LAN_IPS=$(ifconfig 2>/dev/null | awk '/inet / && $2 != "127.0.0.1" {print $2}')

echo "================================================"
echo "  Speakeasy Dev (LAN-ready)"
echo "------------------------------------------------"
echo "  Backend : http://${BACKEND_HOST}:${BACKEND_PORT}"
echo "  Frontend: http://${FRONTEND_HOST}:${FRONTEND_PORT}"
if [ -n "$LAN_IPS" ]; then
  echo "  LAN URLs:"
  for ip in $LAN_IPS; do
    echo "    - http://${ip}:${FRONTEND_PORT}/  (frontend)"
    echo "    - http://${ip}:${BACKEND_PORT}/   (backend)"
  done
fi
echo "================================================"

# 退出时清理子进程
cleanup() {
  echo ""
  echo "Stopping dev servers..."
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null || true
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

# 后端
source venv/bin/activate
uvicorn main:app --reload --host "$BACKEND_HOST" --port "$BACKEND_PORT" &
BACKEND_PID=$!

# 前端
(cd frontend && npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT") &
FRONTEND_PID=$!

wait
