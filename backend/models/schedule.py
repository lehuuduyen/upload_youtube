from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class UploadSchedule(Base):
    __tablename__ = "upload_schedules"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    name = Column(String(255), nullable=False)

    # Cron expression (e.g. "0 8 * * *" = 8am daily)
    cron_expression = Column(String(100), nullable=False)
    timezone = Column(String(50), default="Asia/Ho_Chi_Minh")

    # Behavior
    is_active = Column(Boolean, default=True)
    min_interval_minutes = Column(Integer, default=30)

    # APScheduler job ID
    scheduler_job_id = Column(String(100), nullable=True)

    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    channel = relationship("Channel", back_populates="schedules")


class MetadataTemplate(Base):
    __tablename__ = "metadata_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Template fields
    title_template = Column(String(100), nullable=True)      # supports {date}, {index} etc.
    description_template = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True)                       # list of default tags
    category_id = Column(String(10), default="22")
    privacy_status = Column(String(20), default="private")
    language = Column(String(10), default="vi")
    default_music_volume = Column(String(5), default="0.8")
    default_original_volume = Column(String(5), default="0.2")

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    video_jobs = relationship("VideoJob", back_populates="template")
