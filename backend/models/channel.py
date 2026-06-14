from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    channel_id = Column(String(100), unique=True, nullable=True)  # YouTube channel ID
    email = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)

    # OAuth2 credentials (stored as JSON)
    credentials_json = Column(Text, nullable=True)  # encrypted JSON
    is_authenticated = Column(Boolean, default=False)
    client_secrets_file = Column(String(255), nullable=True)  # filename, e.g. "client_secrets.json"

    # Quota tracking
    daily_quota_used = Column(Integer, default=0)
    daily_quota_limit = Column(Integer, default=10000)
    quota_reset_date = Column(DateTime, nullable=True)

    # Settings
    default_timezone = Column(String(50), default="Asia/Ho_Chi_Minh")
    default_privacy = Column(String(20), default="private")  # public/unlisted/private
    default_category_id = Column(String(10), default="22")  # 22 = People & Blogs
    min_upload_interval_minutes = Column(Integer, default=30)

    # Status
    is_active = Column(Boolean, default=True)
    last_upload_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    video_jobs = relationship("VideoJob", back_populates="channel", cascade="all, delete-orphan")
    schedules = relationship("UploadSchedule", back_populates="channel", cascade="all, delete-orphan")

    def quota_remaining(self) -> int:
        return max(0, self.daily_quota_limit - self.daily_quota_used)

    def can_upload(self) -> bool:
        # Each upload costs ~1600 units
        return self.quota_remaining() >= 1600 and self.is_authenticated and self.is_active
