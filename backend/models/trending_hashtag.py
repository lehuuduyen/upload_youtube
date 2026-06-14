from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from database import Base


class TrendingHashtag(Base):
    __tablename__ = "trending_hashtags"

    id = Column(Integer, primary_key=True, index=True)
    hashtag = Column(String(100), nullable=False)
    platform = Column(String(20), default="instagram_reels")  # instagram_reels | youtube_shorts
    browser = Column(String(20), default="chrome")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
