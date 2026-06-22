#!/bin/bash
#
# YouTube Auto Uploader — Server setup & run script
#
# Cách dùng:
#   bash setup.sh            # cài deps + build frontend rồi chạy server (foreground)
#   bash setup.sh --build    # chỉ cài deps + build, không chạy
#   bash setup.sh --run      # chỉ chạy server foreground (đã build sẵn)
#   bash setup.sh --start    # chạy server NGẦM (background) + ghi log + PID
#   bash setup.sh --stop     # dừng server đang chạy ngầm
#   bash setup.sh --restart  # dừng rồi chạy lại ngầm
#   bash setup.sh --status   # xem trạng thái server ngầm
#   bash setup.sh --logs     # xem log realtime (tail -f)
#
# Port lấy từ biến môi trường PORT (mặc định 8002):
#   PORT=8080 bash setup.sh
#   PORT=8080 bash setup.sh --start
#
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# ─── Cấu hình từ env ──────────────────────────────────────────────────────────
PORT="${PORT:-8002}"
HOST="${HOST:-0.0.0.0}"
export PORT HOST
export RELOAD="${RELOAD:-false}"        # production: tắt auto-reload

PID_FILE="$ROOT_DIR/server.pid"
LOG_FILE="$ROOT_DIR/server.log"

MODE="all"
case "${1:-}" in
  --build)   MODE="build" ;;
  --run)     MODE="run" ;;
  --start)   MODE="start" ;;
  --stop)    MODE="stop" ;;
  --restart) MODE="restart" ;;
  --status)  MODE="status" ;;
  --logs)    MODE="logs" ;;
  "")        MODE="all" ;;
  *) echo "Tham số không hợp lệ: $1 (dùng --build | --run | --start | --stop | --restart | --status | --logs)"; exit 1 ;;
esac

# ─── Hàm quản lý tiến trình ngầm ──────────────────────────────────────────────
is_running() {
  [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

start_bg() {
  if is_running; then
    echo "⚠️  Server đã chạy sẵn (PID $(cat "$PID_FILE")). Dùng 'bash setup.sh --restart' để khởi động lại."
    exit 0
  fi
  echo "🚀 Khởi động server NGẦM tại http://$HOST:$PORT"
  cd "$ROOT_DIR/backend"
  source venv/bin/activate
  HOST="$HOST" PORT="$PORT" RELOAD="$RELOAD" nohup python main.py >> "$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"
  deactivate 2>/dev/null || true
  cd "$ROOT_DIR"
  sleep 1
  if is_running; then
    echo "✅ Đã chạy ngầm (PID $(cat "$PID_FILE"))"
    echo "   Log:     $LOG_FILE"
    echo "   Xem log: bash setup.sh --logs"
    echo "   Dừng:    bash setup.sh --stop"
  else
    echo "❌ Khởi động thất bại. Xem log: $LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
  fi
}

stop_bg() {
  if is_running; then
    PID="$(cat "$PID_FILE")"
    echo "🛑 Đang dừng server (PID $PID)..."
    kill "$PID" 2>/dev/null || true
    for _ in $(seq 1 10); do
      kill -0 "$PID" 2>/dev/null || break
      sleep 0.5
    done
    if kill -0 "$PID" 2>/dev/null; then
      echo "   Tiến trình chưa tắt, buộc dừng (kill -9)..."
      kill -9 "$PID" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
    echo "✅ Đã dừng"
  else
    echo "ℹ️  Server không chạy."
    rm -f "$PID_FILE"
  fi
}

# ─── Lệnh quản lý (không cần build) ───────────────────────────────────────────
case "$MODE" in
  start)   start_bg; exit 0 ;;
  stop)    stop_bg; exit 0 ;;
  restart) stop_bg; start_bg; exit 0 ;;
  status)
    if is_running; then
      echo "✅ Server ĐANG CHẠY (PID $(cat "$PID_FILE")) — http://$HOST:$PORT"
    else
      echo "🔴 Server KHÔNG chạy."
    fi
    exit 0 ;;
  logs)
    [ -f "$LOG_FILE" ] || { echo "Chưa có log: $LOG_FILE"; exit 0; }
    tail -f "$LOG_FILE"
    exit 0 ;;
esac

echo "========================================"
echo "  YouTube Auto Uploader — Server Setup   "
echo "  HOST=$HOST  PORT=$PORT  MODE=$MODE"
echo "========================================"

check_cmd() {
  if ! command -v "$1" &>/dev/null; then
    echo "❌  '$1' không tìm thấy. Vui lòng cài đặt trước."
    exit 1
  fi
}

# ─── Build / cài đặt ──────────────────────────────────────────────────────────
if [ "$MODE" = "all" ] || [ "$MODE" = "build" ]; then
  echo ""
  echo "🔍 Kiểm tra dependencies..."
  check_cmd python3
  check_cmd ffmpeg
  check_cmd node
  check_cmd npm
  command -v yt-dlp &>/dev/null || echo "⚠️  yt-dlp chưa có trên PATH — cần để tải video."
  echo "✅ Dependencies OK"

  # .env
  if [ ! -f .env ]; then
    cp .env.example .env
    echo "📝 Đã tạo .env từ .env.example — hãy chỉnh sửa trước khi chạy!"
  else
    echo "✅ .env đã tồn tại"
  fi

  # Backend
  echo ""
  echo "🐍 Cài đặt Python backend..."
  cd backend
  if [ ! -d "venv" ]; then
    python3 -m venv venv
  fi
  source venv/bin/activate
  pip install --quiet --upgrade pip
  pip install --quiet -r requirements.txt
  deactivate
  echo "✅ Backend dependencies đã cài xong"
  cd "$ROOT_DIR"

  # Frontend — build production (phục vụ qua chính backend, 1 port duy nhất)
  echo ""
  echo "⚛️  Build React frontend (production)..."
  cd frontend
  npm install --silent
  npm run build
  echo "✅ Frontend đã build → frontend/dist"
  cd "$ROOT_DIR"

  # Storage
  mkdir -p storage/{downloads,processed,thumbnails,temp,logos,outros,uploads}
  echo "✅ Thư mục storage đã tạo"

  # client_secrets.json
  echo ""
  if [ ! -f client_secrets.json ]; then
    echo "⚠️  QUAN TRỌNG: client_secrets.json chưa có!"
    echo "   Tải OAuth 2.0 Client (Web app) từ Google Cloud Console và đặt vào thư mục gốc."
    echo "   Nhớ thêm redirect URI khớp với OAUTH_REDIRECT_URI trong .env"
  else
    echo "✅ client_secrets.json đã có"
  fi
fi

# ─── Chạy server ──────────────────────────────────────────────────────────────
if [ "$MODE" = "all" ] || [ "$MODE" = "run" ]; then
  echo ""
  echo "========================================"
  echo "🚀 Khởi động server tại http://$HOST:$PORT"
  echo "========================================"
  cd backend
  source venv/bin/activate
  exec python main.py
fi

if [ "$MODE" = "build" ]; then
  echo ""
  echo "✅ Build hoàn tất."
  echo "   Chạy foreground: PORT=$PORT bash setup.sh --run"
  echo "   Chạy ngầm:       PORT=$PORT bash setup.sh --start"
fi
