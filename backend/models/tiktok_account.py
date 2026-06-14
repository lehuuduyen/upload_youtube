from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class TikTokAccount(Base):
    __tablename__ = "tiktok_accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    open_id = Column(String(100), nullable=True)          # TikTok user open_id
    display_name = Column(String(100), nullable=True)
    avatar_url = Column(String(512), nullable=True)

    # OAuth2 tokens
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)

    is_authenticated = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    video_jobs = relationship("VideoJob", back_populates="tiktok_account")
