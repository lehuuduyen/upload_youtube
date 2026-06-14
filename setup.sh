#!/bin/bash
set -e

echo "========================================"
echo "  YouTube Auto Uploader - Setup Script  "
echo "========================================"

# Check dependencies
check_cmd() {
  if ! command -v "$1" &>/dev/null; then
    echo "❌  '$1' không tìm thấy. Vui lòng cài đặt trước."
    exit 1
  fi
}

echo ""
echo "🔍 Kiểm tra dependencies..."
check_cmd python3
check_cmd ffmpeg
check_cmd node
check_cmd npm

echo "✅ Dependencies OK"

# Setup .env
if [ ! -f .env ]; then
  cp .env.example .env
  echo "📝 Đã tạo .env từ .env.example — hãy chỉnh sửa trước khi chạy!"
else
  echo "✅ .env đã tồn tại"
fi

# Backend setup
echo ""
echo "🐍 Cài đặt Python backend..."
cd backend

if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "✅ Backend dependencies đã cài xong"

cd ..

# Frontend setup
echo ""
echo "⚛️  Cài đặt React frontend..."
cd frontend
npm install --silent
echo "✅ Frontend dependencies đã cài xong"
cd ..

# Create storage dirs
mkdir -p storage/{downloads,processed,thumbnails,temp}
echo "✅ Thư mục storage đã tạo"

# Check client_secrets.json
echo ""
if [ ! -f client_secrets.json ]; then
  echo "⚠️  QUAN TRỌNG: client_secrets.json chưa có!"
  echo "   1. Vào https://console.cloud.google.com/"
  echo "   2. Tạo project → Bật YouTube Data API v3"
  echo "   3. Tạo OAuth 2.0 Client ID (Web app)"
  echo "   4. Thêm redirect URI: http://localhost:8000/api/channels/oauth/callback"
  echo "   5. Tải về client_secrets.json và đặt vào thư mục gốc"
else
  echo "✅ client_secrets.json đã có"
fi

echo ""
echo "========================================"
echo "✅ Setup hoàn tất!"
echo ""
echo "Để chạy:"
echo "  Backend:  cd backend && source venv/bin/activate && python main.py"
echo "  Frontend: cd frontend && npm run dev"
echo ""
echo "Hoặc dùng Docker: docker-compose up --build"
echo "========================================"
