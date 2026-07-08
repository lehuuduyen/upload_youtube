#!/usr/bin/env bash
# Chạy MỘT LẦN trên server mới (Ubuntu/Debian) để cài Docker + mở firewall.
#   curl hoặc scp file này lên server rồi:  bash setup-server.sh
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "📦 Cài Docker..."
  curl -fsSL https://get.docker.com | sh
fi

# Docker Compose plugin (bản mới đi kèm get.docker.com, kiểm tra lại)
if ! docker compose version >/dev/null 2>&1; then
  apt-get update && apt-get install -y docker-compose-plugin
fi

# Firewall: mở SSH + HTTP/HTTPS
if command -v ufw >/dev/null 2>&1; then
  ufw allow OpenSSH || true
  ufw allow 80/tcp
  ufw allow 443/tcp
fi

echo "✅ Server sẵn sàng. Từ máy local chạy: bash deploy/deploy.sh"
