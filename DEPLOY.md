# Hướng dẫn Deploy Production

Kiến trúc:

```
Người dùng ──▶ Vercel (frontend React)  ──▶  https://api.<domain>  (Caddy, tự động SSL)
                                                    │
                                              backend FastAPI (Docker)
                                              ├─ APScheduler: auto upload theo lịch 24/7
                                              ├─ ffmpeg / yt-dlp / Playwright
                                              └─ SQLite + storage/ (volume trên server)
```

Backend **phải** chạy trên server riêng (không serverless được) vì cần ffmpeg render,
Playwright browser, ổ đĩa lưu video và scheduler chạy nền liên tục.

---

## 1. Chuẩn bị server (một lần)

```bash
# Copy script lên server rồi chạy (cài Docker + mở firewall 80/443)
scp deploy/setup-server.sh root@YOUR_SERVER_IP:/tmp/
ssh root@YOUR_SERVER_IP "bash /tmp/setup-server.sh"
```

**DNS**: tạo bản ghi `A` cho `api.<domain>` trỏ về IP server. Caddy sẽ tự lấy SSL
Let's Encrypt khi start (DNS phải trỏ đúng trước).

## 2. Cấu hình deploy (một lần, ở máy local)

```bash
cp deploy/deploy.env.example deploy/deploy.env
# điền SSH_TARGET=root@YOUR_SERVER_IP
```

## 3. Deploy backend

```bash
bash deploy/deploy.sh
```

Lần đầu script sẽ tạo `.env.production` trên server từ file mẫu và dừng lại — SSH vào điền:

```bash
ssh root@YOUR_SERVER_IP nano /opt/upload_youtube/.env.production
```

| Biến | Giá trị |
|---|---|
| `API_DOMAIN` | `api.<domain>` — Caddy dùng để lấy SSL |
| `CORS_ORIGINS` | domain Vercel, vd `https://myapp.vercel.app` |
| `OAUTH_REDIRECT_URI` | `https://api.<domain>/api/channels/oauth/callback` |
| `TIKTOK_REDIRECT_URI` | `https://api.<domain>/api/tiktok/oauth/callback` |
| `ANTHROPIC_API_KEY` | key Claude (cho AI tạo video) |
| `SECRET_KEY` | chuỗi ngẫu nhiên |

Sau đó **copy file secrets lên server** (git không track chúng):

```bash
scp client_secrets.json client_secret_nhi.json client_secret_thiennga.json \
    cookies.txt facebook.com_cookies.txt root@YOUR_SERVER_IP:/opt/upload_youtube/
```

Chạy lại `bash deploy/deploy.sh` — từ giờ mỗi lần sửa code chỉ cần chạy đúng 1 lệnh này.

Kiểm tra: `https://api.<domain>/api/health` → `{"status":"ok"}`

## 4. Google OAuth (bắt buộc để upload YouTube)

Vào [Google Cloud Console](https://console.cloud.google.com/apis/credentials) → OAuth 2.0 Client
→ **Authorized redirect URIs** → thêm:

```
https://api.<domain>/api/channels/oauth/callback
```

(Giữ cả URI localhost nếu vẫn dev ở máy local.) Làm tương tự cho từng file
`client_secret_*.json` nếu chúng thuộc project Google khác nhau.
TikTok: thêm redirect URI mới trong developers.tiktok.com.

> Lưu ý: token OAuth đã cấp ở máy local nằm trong DB (`storage/app.db`), không tự
> chuyển lên server. Sau khi deploy, vào trang **Channels** trên web và bấm
> **Connect** lại cho từng kênh (chỉ cần 1 lần, token lưu vào DB trên server).

## 5. Frontend lên Vercel

1. Push repo lên GitHub, vào [vercel.com](https://vercel.com) → **Add New Project** → import repo.
2. **Root Directory**: `frontend` (Vercel tự nhận Vite).
3. **Environment Variables** thêm:
   ```
   VITE_API_BASE_URL = https://api.<domain>/api
   ```
4. Deploy. Mỗi lần push GitHub, Vercel tự deploy lại frontend.

`frontend/vercel.json` đã có sẵn SPA fallback cho react-router.

## 6. Auto upload theo lịch (chạy 24/7)

Mọi thứ đã có sẵn trong app, chỉ cần cấu hình trên web sau khi deploy:

1. **Channels** → connect OAuth từng kênh YouTube.
2. **Schedules** → tạo lịch upload cho từng kênh (cron 5 trường, timezone `Asia/Ho_Chi_Minh`).
   - Vd `0 19 * * *` = 19h hằng ngày. Đến giờ, scheduler tự lấy job `READY/QUEUED`
     tiếp theo của kênh và upload.
3. Tạo nội dung sẵn cho hàng đợi bằng **Auto Creator** (Reup Trending / AI Tạo Mới)
   hoặc **New Job**, chọn `upload_mode = manual` để duyệt trước, job duyệt xong nằm
   ở trạng thái READY chờ lịch.
4. Backend có `restart: unless-stopped` + healthcheck → server reboot là tự chạy lại,
   scheduler tự nạp lịch từ DB khi khởi động (`load_all_schedules`).

## Vận hành

```bash
# Xem log realtime
ssh root@SERVER 'cd /opt/upload_youtube && docker compose -f docker-compose.prod.yml logs -f backend'

# Restart
ssh root@SERVER 'cd /opt/upload_youtube && docker compose -f docker-compose.prod.yml restart backend'

# Backup DB (SQLite nằm trong ./storage trên server)
ssh root@SERVER 'cp /opt/upload_youtube/storage/app.db /opt/upload_youtube/storage/app.db.bak'
```

- Video đã upload xong sẽ tự xoá file (`AUTO_DELETE_AFTER_UPLOAD=true`) nên ổ đĩa nhẹ.
- Cookies hết hạn (YouTube/Facebook chặn download): export cookies mới từ browser
  và upload qua UI (trang New Job → Cookies) hoặc scp đè `cookies.txt` lên server.
