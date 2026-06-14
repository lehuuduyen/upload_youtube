from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite only
    pool_size=20,
    max_overflow=20,
    pool_timeout=10,
    echo=settings.DEBUG,
)

# expire_on_commit=False: prevent lazy-reload after commit (avoids extra connection per endpoint)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from models import channel, video_job, schedule, trending, trending_hashtag  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _migrate_add_missing_columns()


def _migrate_add_missing_columns():
    """Add any missing columns to existing tables (safe, idempotent)."""
    from sqlalchemy import text, inspect

    inspector = inspect(engine)
    with engine.connect() as conn:
        # video_jobs migrations
        existing = {col["name"] for col in inspector.get_columns("video_jobs")}
        pending = {
            "upload_mode":      "ALTER TABLE video_jobs ADD COLUMN upload_mode VARCHAR(20) DEFAULT 'immediate'",
            "platform":         "ALTER TABLE video_jobs ADD COLUMN platform VARCHAR(20) DEFAULT 'youtube'",
            "review_status":    "ALTER TABLE video_jobs ADD COLUMN review_status VARCHAR(20) DEFAULT 'auto'",
            "tiktok_video_id":  "ALTER TABLE video_jobs ADD COLUMN tiktok_video_id VARCHAR(100)",
            "tiktok_url":       "ALTER TABLE video_jobs ADD COLUMN tiktok_url VARCHAR(255)",
            "tiktok_account_id":"ALTER TABLE video_jobs ADD COLUMN tiktok_account_id INTEGER",
            "auto_topic":       "ALTER TABLE video_jobs ADD COLUMN auto_topic VARCHAR(255)",
            "auto_script":      "ALTER TABLE video_jobs ADD COLUMN auto_script TEXT",
            "clip_paths":        "ALTER TABLE video_jobs ADD COLUMN clip_paths JSON",
            "mute_range_start":  "ALTER TABLE video_jobs ADD COLUMN mute_range_start REAL",
            "mute_range_end":    "ALTER TABLE video_jobs ADD COLUMN mute_range_end REAL",
            "outro_path":        "ALTER TABLE video_jobs ADD COLUMN outro_path VARCHAR(1024)",
            "logo_path":         "ALTER TABLE video_jobs ADD COLUMN logo_path VARCHAR(1024)",
            "logo_position":     "ALTER TABLE video_jobs ADD COLUMN logo_position VARCHAR(20) DEFAULT 'top-left'",
            "logo_size":         "ALTER TABLE video_jobs ADD COLUMN logo_size INTEGER DEFAULT 80",
        }
        for col, sql in pending.items():
            if col not in existing:
                conn.execute(text(sql))
        conn.commit()

        # channels table migrations
        ch_existing = {col["name"] for col in inspector.get_columns("channels")}
        ch_pending = {
            "client_secrets_file": "ALTER TABLE channels ADD COLUMN client_secrets_file VARCHAR(255)",
        }
        for col, sql in ch_pending.items():
            if col not in ch_existing:
                conn.execute(text(sql))
        conn.commit()
