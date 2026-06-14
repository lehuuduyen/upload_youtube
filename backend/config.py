import os
from pydantic_settings import BaseSettings
from pathlib import Path

# Local dev: config.py is at project/backend/config.py → parent.parent = project root
# Docker:    config.py is at /app/config.py → parent.parent = / (wrong)
# Fix: APP_BASE_DIR env var overrides when running in Docker
BASE_DIR = Path(os.getenv("APP_BASE_DIR", str(Path(__file__).resolve().parent.parent)))


class Settings(BaseSettings):
    # App
    APP_NAME: str = "YouTube Auto Uploader"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-this-secret-key-in-production"

    # Database
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/storage/app.db"

    # Storage paths
    STORAGE_DIR: str = str(BASE_DIR / "storage")
    DOWNLOADS_DIR: str = str(BASE_DIR / "storage" / "downloads")
    PROCESSED_DIR: str = str(BASE_DIR / "storage" / "processed")
    THUMBNAILS_DIR: str = str(BASE_DIR / "storage" / "thumbnails")
    TEMP_DIR: str = str(BASE_DIR / "storage" / "temp")
    LOGOS_DIR: str = str(BASE_DIR / "storage" / "logos")
    OUTROS_DIR: str = str(BASE_DIR / "storage" / "outros")
    UPLOADS_DIR: str = str(BASE_DIR / "storage" / "uploads")

    # YouTube OAuth2
    GOOGLE_CLIENT_SECRETS_FILE: str = str(BASE_DIR / "client_secrets.json")
    YOUTUBE_SCOPES: list[str] = ["https://www.googleapis.com/auth/youtube.upload"]
    OAUTH_REDIRECT_URI: str = "http://localhost:8001/api/channels/oauth/callback"

    # FFmpeg
    FFMPEG_PATH: str = "ffmpeg"
    FFPROBE_PATH: str = "ffprobe"

    # Redis (optional, for Celery)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Scheduler
    SCHEDULER_TIMEZONE: str = "Asia/Ho_Chi_Minh"

    # TikTok API
    TIKTOK_CLIENT_KEY: str = ""
    TIKTOK_CLIENT_SECRET: str = ""
    TIKTOK_REDIRECT_URI: str = "http://localhost:8000/api/tiktok/oauth/callback"

    # Anthropic (Claude AI) — for auto-creator
    ANTHROPIC_API_KEY: str = ""

    # Upload limits
    MAX_CONCURRENT_DOWNLOADS: int = 3
    MAX_CONCURRENT_UPLOADS: int = 2
    MIN_UPLOAD_INTERVAL_MINUTES: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
