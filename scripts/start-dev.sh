#!/usr/bin/env bash
# 同时启动后端（FastAPI）和前端（Vite），同一终端；Ctrl+C 会同时停止两者。

set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKEND_PID=""
cleanup() {
  if [[ -n "$BACKEND_PID" ]]; then
    echo ""
    echo "Stopping backend (PID $BACKEND_PID)..."
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  exit 0
}
trap cleanup INT TERM

# 后端：启动前先清理本机 8000 端口上的旧进程，避免请求被旧进程处理导致 500/无日志
if command -v lsof >/dev/null 2>&1; then
  OLD_PIDS=$(lsof -ti :8000 2>/dev/null || true)
  if [[ -n "$OLD_PIDS" ]]; then
    echo "Stopping existing process(es) on port 8000: $OLD_PIDS"
    echo "$OLD_PIDS" | xargs kill -9 2>/dev/null || true
    sleep 1
  fi
fi
# 后端：后台运行
if [[ ! -d "$ROOT/backend/.venv" ]]; then
  echo "Error: backend/.venv not found. Run: cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi
echo "Starting backend at http://localhost:8000 ..."
(cd "$ROOT/backend" && .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000) &
BACKEND_PID=$!

# 稍等再起前端，避免端口/日志交错
sleep 2

# 前端：前台运行（当前终端看前端日志，Ctrl+C 时 trap 会关掉后端）
if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
  echo "Error: frontend/node_modules not found. Run: cd frontend && npm install"
  exit 1
fi
echo "Starting frontend at http://localhost:5173 ..."
(cd "$ROOT/frontend" && npm run dev)

# 若前端正常退出也会清理后端
cleanup
