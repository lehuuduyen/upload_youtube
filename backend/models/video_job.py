import enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    READY = "ready"
    QUEUED = "queued"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VideoJob(Base):
    __tablename__ = "video_jobs"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("metadata_templates.id"), nullable=True)

    # Input sources
    video_url = Column(String(2048), nullable=True)       # YouTube/TikTok source URL
    music_url = Column(String(2048), nullable=True)       # Music source URL
    music_file_path = Column(String(1024), nullable=True) # Or direct file path

    # Download options
    video_quality = Column(String(20), default="1080p")   # 720p/1080p/4k/best
    music_start_time = Column(Float, nullable=True)       # seconds
    music_end_time = Column(Float, nullable=True)         # seconds

    # Processing options
    mute_original = Column(Boolean, default=True)
    mute_range_start = Column(Float, nullable=True)        # giây — tắt tiếng gốc từ đây
    mute_range_end = Column(Float, nullable=True)          # giây — tắt tiếng gốc đến đây
    original_volume = Column(Float, default=0.2)          # 0.0 - 1.0
    music_volume = Column(Float, default=0.8)             # 0.0 - 1.0
    loop_music = Column(Boolean, default=True)
    fade_in_duration = Column(Float, default=0.0)         # seconds
    fade_out_duration = Column(Float, default=2.0)        # seconds
    output_format = Column(String(10), default="16:9")    # 16:9 / 9:16 / 1:1
    output_width = Column(Integer, nullable=True)
    output_height = Column(Integer, nullable=True)

    # YouTube Metadata
    title = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True)                    # list of strings
    category_id = Column(String(10), default="22")
    privacy_status = Column(String(20), default="private")
    language = Column(String(10), default="vi")
    thumbnail_path = Column(String(1024), nullable=True)
    scheduled_publish_at = Column(DateTime, nullable=True)  # for YouTube scheduled publish

    # File paths
    downloaded_video_path = Column(String(1024), nullable=True)
    downloaded_music_path = Column(String(1024), nullable=True)
    processed_video_path = Column(String(1024), nullable=True)

    # Upload result
    youtube_video_id = Column(String(100), nullable=True)
    youtube_url = Column(String(255), nullable=True)

    # Job state
    status = Column(Enum(JobStatus), default=JobStatus.PENDING)
    priority = Column(Integer, default=0)                 # higher = earlier in queue
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    error_message = Column(Text, nullable=True)
    progress = Column(Float, default=0.0)                 # 0-100
    log = Column(Text, nullable=True)                     # processing log

    # Upload mode: "immediate" = process + upload now; "manual" = process then stop at READY
    upload_mode = Column(String(20), default="immediate")

    # Platform: youtube / tiktok / both
    platform = Column(String(20), default="youtube")

    # Review: auto=skip, pending=needs review, approved, rejected
    review_status = Column(String(20), default="auto")

    # TikTok result
    tiktok_video_id = Column(String(100), nullable=True)
    tiktok_url = Column(String(255), nullable=True)
    tiktok_account_id = Column(Integer, ForeignKey("tiktok_accounts.id"), nullable=True)

    # Auto-creator metadata
    auto_topic = Column(String(255), nullable=True)
    auto_script = Column(Text, nullable=True)             # JSON script from Claude

    # Uploaded clips to concat (list of server paths)
    clip_paths = Column(JSON, nullable=True)              # ["/storage/uploads/abc.mp4", ...]

    # Outro clip appended at the end
    outro_path = Column(String(1024), nullable=True)

    # Logo/icon overlay
    logo_path = Column(String(1024), nullable=True)
    logo_position = Column(String(20), nullable=True, default="top-left")
    logo_size = Column(Integer, nullable=True, default=80)  # width in pixels

    # Upload scheduling
    upload_at = Column(DateTime, nullable=True)           # when to upload

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    channel = relationship("Channel", back_populates="video_jobs")
    template = relationship("MetadataTemplate", back_populates="video_jobs")
    tiktok_account = relationship("TikTokAccount", back_populates="video_jobs")

    def append_log(self, message: str):
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] {message}"
        self.log = f"{self.log}\n{entry}" if self.log else entry
