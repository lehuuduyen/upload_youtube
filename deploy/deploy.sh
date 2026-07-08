#!/usr/bin/env bash
# Deploy backend lên server qua SSH (chạy từ máy local).
#
# Lần đầu: copy deploy/deploy.env.example → deploy/deploy.env rồi điền SSH_TARGET.
# Sau đó mỗi lần deploy chỉ cần:  bash deploy/deploy.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ── Load config ──────────────────────────────────────────────────────────────
if [[ -f "$SCRIPT_DIR/deploy.env" ]]; then
  # shellcheck disable=SC1091
  source "$SCRIPT_DIR/deploy.env"
fi
SSH_TARGET="${SSH_TARGET:-}"          # vd: root@203.0.113.10
REMOTE_DIR="${REMOTE_DIR:-/opt/upload_youtube}"

if [[ -z "$SSH_TARGET" ]]; then
  echo "❌ Chưa cấu hình SSH_TARGET. Copy deploy/deploy.env.example → deploy/deploy.env rồi điền."
  exit 1
fi

echo "🚀 Deploy lên $SSH_TARGET:$REMOTE_DIR"

# ── Sync code (bỏ file nặng / file chỉ dùng local) ──────────────────────────
ssh "$SSH_TARGET" "mkdir -p $REMOTE_DIR"
rsync -az --info=progress2 --delete \
  --exclude ".git/" \
  --exclude "backend/venv/" \
  --exclude "frontend/node_modules/" \
  --exclude "frontend/dist/" \
  --exclude "storage/" \
  --exclude "*.log" \
  --exclude "server.pid" \
  --exclude ".env.production" \
  --exclude "deploy/deploy.env" \
  "$PROJECT_DIR/" "$SSH_TARGET:$REMOTE_DIR/"

# ── Kiểm tra .env.production trên server ────────────────────────────────────
if ! ssh "$SSH_TARGET" "test -f $REMOTE_DIR/.env.production"; then
  ssh "$SSH_TARGET" "cp $REMOTE_DIR/.env.production.example $REMOTE_DIR/.env.production"
  echo ""
  echo "⚠️  Lần đầu deploy: đã tạo $REMOTE_DIR/.env.production từ file mẫu."
  echo "   SSH vào server, điền domain + API keys thật rồi chạy lại script này:"
  echo "   ssh $SSH_TARGET 'nano $REMOTE_DIR/.env.production'"
  exit 1
fi

# ── Tạo file cookies rỗng nếu chưa có (compose mount chúng) ─────────────────
ssh "$SSH_TARGET" "cd $REMOTE_DIR && touch cookies.txt facebook.com_cookies.txt"

# ── Build + restart ──────────────────────────────────────────────────────────
ssh "$SSH_TARGET" "cd $REMOTE_DIR && docker compose -f docker-compose.prod.yml up -d --build"

# ── Health check ─────────────────────────────────────────────────────────────
echo "⏳ Chờ backend khởi động..."
sleep 10
if ssh "$SSH_TARGET" "docker compose -f $REMOTE_DIR/docker-compose.prod.yml exec -T backend curl -fsS http://localhost:8001/api/health" >/dev/null 2>&1; then
  echo "💚 Backend healthy."
else
  echo "⚠️  Backend chưa trả lời health check — xem log bên dưới:"
  ssh "$SSH_TARGET" "cd $REMOTE_DIR && docker compose -f docker-compose.prod.yml logs --tail=50 backend" || true
fi
ssh "$SSH_TARGET" "cd $REMOTE_DIR && docker compose -f docker-compose.prod.yml ps"

echo ""
echo "✅ Deploy xong. Kiểm tra: https://\$API_DOMAIN/api/health"
echo "   Xem log:  ssh $SSH_TARGET 'cd $REMOTE_DIR && docker compose -f docker-compose.prod.yml logs -f backend'"
