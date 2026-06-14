# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Project

**Backend** (FastAPI + uvicorn, port 8000):
```bash
cd backend
source venv/bin/activate
python main.py
```

**Frontend** (Vite + React, port 5173):
```bash
cd frontend
npm run dev
```

Vite proxies all `/api` requests to `http://localhost:8000`, so no CORS config needed in dev.

**First-time setup:**
```bash
bash setup.sh
```
Requires: `python3`, `ffmpeg`, `yt-dlp`, `node`, `npm` on PATH. Also requires `client_secrets.json` (Google OAuth2) in the project root.

**Docker:**
```bash
docker-compose up --build
```

## IDE Configuration

VSCode Python interpreter must be set to `./backend/venv/bin/python` to avoid false "Cannot find module" warnings from Pylance. The `.vscode/settings.json` already sets this, but use **Cmd+Shift+P → Python: Select Interpreter** to activate it.

## Architecture

### Backend (`/backend`)

FastAPI app with SQLite via SQLAlchemy. No Alembic migrations — instead, `database.py:_migrate_add_missing_columns()` runs on every startup to add missing columns idempotently.

**Routers** (`/backend/routers/`):
- `channels.py` — YouTube channel management + Google OAuth2 flow
- `downloads.py` — Manual job creation (URL or uploaded clips)
- `queue.py` — Job lifecycle: list, update, cancel, retry, upload-now, reorder
- `auto_creator.py` — Two pipelines: Reup (find/download trending video + brand) and AI (Claude script → TTS → FFmpeg render)
- `media.py` — Video stream preview (Range requests), job review approve/reject, file uploads (logo, outro, video clips)
- `schedules.py` — APScheduler-based upload schedules per channel
- `tiktok_accounts.py` — TikTok OAuth + account management

**Workers** (`/backend/workers/job_worker.py`):

The main pipeline for `VideoJob` records: download video → (optional) download music → (optional) concat uploaded clips → FFmpeg process → upload to YouTube/TikTok. Background tasks use `asyncio.create_task()` (not `ensure_future`, which fails in AnyIO worker threads).

**Services** (`/backend/services/`):
- `downloader.py` — yt-dlp wrappers for async video/music download
- `processor.py` — FFmpeg audio merge, aspect ratio conversion
- `youtube_service.py` — YouTube Data API v3: OAuth token management, upload, quota tracking
- `scheduler.py` — APScheduler singleton (`AsyncIOScheduler`)
- `auto_creator/trend_finder.py` — pytrends Google Trends analysis
- `auto_creator/script_generator.py` — Claude API script generation with template fallback
- `auto_creator/voiceover_gen.py` — edge-tts async TTS
- `auto_creator/video_renderer.py` — FFmpeg Gen Z-style 9:16 video render from script
- `auto_creator/video_finder.py` — yt-dlp YouTube search (`ytsearch{N}:query`), returns results sorted newest-first by `_ts`
- `auto_creator/video_reup_processor.py` — Core reup functions: `download_video`, `process_reup` (watermark/logo/outro/music), `concat_clips` (stream copy), `concat_clips_reencode` (re-encode, handles mixed codecs)

**Key model** (`/backend/models/video_job.py`):

`VideoJob` tracks the full lifecycle. Important fields:
- `status` — `JobStatus` enum: pending → downloading → processing → ready → queued → uploading → uploaded / failed / cancelled
- `upload_mode` — `"immediate"` (process + upload) or `"manual"` (stop at READY for review)
- `review_status` — `"auto"` / `"pending"` / `"approved"` / `"rejected"`
- `platform` — `"youtube"` / `"tiktok"` / `"both"`
- `clip_paths` — JSON list of server-side absolute paths to uploaded video clips for concatenation
- `downloaded_video_path` — set after download/concat; if already set, download step is skipped on retry
- `auto_topic` — set for reup/AI jobs; used by retry logic to re-run correct pipeline

**Storage dirs** (created on startup, configured in `config.py`):
```
storage/downloads/    # yt-dlp downloads
storage/processed/    # final output videos
storage/temp/         # intermediate FFmpeg files
storage/thumbnails/   # auto-extracted thumbnails
storage/logos/        # uploaded logo images
storage/outros/       # uploaded outro clips
storage/uploads/      # uploaded video clips for concat
```

### Frontend (`/frontend`)

React 18 + Vite + Tailwind. State: React Query v3 for server state, react-hook-form for forms. No global store.

**Pages** (`/frontend/src/pages/`):
- `Dashboard.jsx` — Stats, quota, activity, upcoming queue
- `NewJob.jsx` — Manual job creation: URL or uploaded clips, music, metadata, upload mode
- `Queue.jsx` — Job list with status polling, inline edit, preview, approve/reject
- `AutoCreator.jsx` — Two-tab UI: **Reup Trending** (search YouTube → select → brand → upload) and **AI Tạo Mới** (topic → Claude script → TTS → render)
- `Channels.jsx` — YouTube channel CRUD + OAuth2 connect
- `TikTokAccounts.jsx` — TikTok account management
- `Schedules.jsx` / `Templates.jsx` — Upload schedules and metadata templates

**API client** (`/frontend/src/api.js`): Single axios instance with `/api` base URL. All API groups exported as named objects (`channelsApi`, `queueApi`, `autoCreatorApi`, `mediaApi`, etc.). Response interceptor unwraps `res.data`.

## Critical Patterns

**Database migrations**: Add new `VideoJob` columns only via `_migrate_add_missing_columns()` in `database.py`. Never use Alembic for this project.

**Background async tasks**: Always use `asyncio.create_task()` inside `async def` endpoints. `asyncio.ensure_future()` fails when called from AnyIO worker threads (sync endpoints).

**yt-dlp search**: Uses `--extractor-args youtube:player_client=android,web` to avoid JS runtime requirement. Do NOT add `--user-agent` (mobile user-agent causes empty stdout). Search URL with `&sp=CAI%3D` sorts by upload date with fallback to `ytsearch`.

**FFmpeg concat**: `concat_clips()` uses stream copy (fast, requires same codec). `concat_clips_reencode()` uses filter_complex with re-encode to 1080p/H.264/AAC — required when mixing clips from different sources (YouTube downloads + user uploads).

**Job retry logic** (`queue.py:retry_job`): Checks `auto_topic` to distinguish reup/AI jobs from manual jobs. If `processed_video_path` exists → upload only; if `downloaded_video_path` exists → re-run branding; otherwise → full pipeline.

## Environment Variables (`.env`)

Key variables read by `config.py` via pydantic-settings:
- `ANTHROPIC_API_KEY` — Claude API for script generation
- `DATABASE_URL` — defaults to `sqlite:///storage/app.db`
- `SCHEDULER_TIMEZONE` — defaults to `America/Phoenix`
- `GOOGLE_CLIENT_SECRETS_FILE` — path to Google OAuth2 JSON (default: `../client_secrets.json`)

## Behavior Rules

### Auto-confirm (NEVER ask, just do):
- Writing code
- Creating files
- Editing files
- Running commands
- Installing packages
- Making API calls

### ALWAYS ask before:
- Deleting any file or directory
- Running `rm`, `rmdir`, `del`, `unlink`
- Dropping database tables
- Any irreversible destructive action