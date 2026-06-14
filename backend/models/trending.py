from sqlalchemy import Column, Integer, String, DateTime, BigInteger, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class TrendingVideo(Base):
    __tablename__ = "trending_videos"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(20), default="tiktok")
    hashtag = Column(String(100), nullable=False)
    video_url = Column(String(500), unique=True, nullable=False)
    video_title = Column(String(500), nullable=True)
    thumbnail_url = Column(String(1000), nullable=True)
    author = Column(String(200), nullable=True)
    view_count = Column(BigInteger, nullable=True)

    # pending = vừa lấy về, chờ duyệt
    # approved = đã xem, sẵn sàng tạo job
    # rejected = bỏ qua
    # published = đã tạo job
    status = Column(String(20), default="pending")

    job_id = Column(Integer, ForeignKey("video_jobs.id"), nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
