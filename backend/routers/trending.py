"""
Trending videos + hashtag management endpoints.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.trending import TrendingVideo
from models.trending_hashtag import TrendingHashtag

router = APIRouter(prefix="/api/trending", tags=["trending"])


# ── Pydantic models ───────────────────────────────────────────────────────────

class TrendingUpdate(BaseModel):
    status: Optional[str] = None
    job_id: Optional[int] = None


class FetchRequest(BaseModel):
    hashtag: str = "nailart"
    platform: str = "instagram_reels"
    max_count: int = 30
    browser: str = "chrome"
    filter_people: bool = True


class ImportRequest(BaseModel):
    urls: list[str]
    hashtag: str = "nailart"
    platform: str = "instagram"


class HashtagCreate(BaseModel):
    hashtag: str
    platform: str = "instagram_reels"
    browser: str = "chrome"


class TikTokChannelRequest(BaseModel):
    channel: str  # URL hoặc username, e.g. "@softlux.nails" hoặc full URL
    max_count: int = 30
    browser: str = ""       # "chrome"|"firefox"|"edge" — lấy cookies từ browser (local)
    cookies_file: str = ""  # path tới cookies.txt trong Docker


# ── Trending video endpoints ──────────────────────────────────────────────────

@router.get("/")
def list_trending(
    status: Optional[str] = None,
    hashtag: Optional[str] = None,
    limit: int = 300,
    db: Session = Depends(get_db),
):
    """List trending videos. Default: chỉ status=pending."""
    q = db.query(TrendingVideo).order_by(TrendingVideo.fetched_at.desc())
    # Mặc định ẩn rejected + published
    if status:
        q = q.filter(TrendingVideo.status == status)
    else:
        q = q.filter(TrendingVideo.status == "pending")
    if hashtag:
        q = q.filter(TrendingVideo.hashtag == hashtag)
    return [_to_dict(v) for v in q.limit(limit).all()]


@router.patch("/{item_id}")
def update_trending(item_id: int, body: TrendingUpdate, db: Session = Depends(get_db)):
    item = db.query(TrendingVideo).filter(TrendingVideo.id == item_id).first()
    if not item:
        raise HTTPException(404, "Not found")
    if body.status is not None:
        item.status = body.status
    if body.job_id is not None:
        item.job_id = body.job_id
    db.commit()
    return _to_dict(item)


@router.delete("/{item_id}", status_code=204)
def delete_trending(item_id: int, db: Session = Depends(get_db)):
    """Xoá hẳn (dùng cho Reject — không hiện lại sau khi fetch mới)."""
    item = db.query(TrendingVideo).filter(TrendingVideo.id == item_id).first()
    if not item:
        raise HTTPException(404, "Not found")
    db.delete(item)
    db.commit()


@router.post("/fetch")
async def trigger_fetch(body: FetchRequest):
    """
    Fetch trending videos từ Instagram Reels hoặc YouTube Shorts.
    Chạy đồng bộ và trả về kết quả ngay.
    """
    from services.trend_fetcher import fetch_and_save
    result = await fetch_and_save(
        body.hashtag, body.platform, body.max_count, body.browser, body.filter_people
    )
    if result["error"]:
        raise HTTPException(400, result["error"])
    return {
        "message": f"Đã thêm {result['saved']} video mới (tổng {result['total']} tìm được)",
        "saved": result["saved"],
        "total": result["total"],
    }


@router.post("/fetch-all")
async def fetch_all(filter_people: bool = True):
    """Fetch tất cả hashtag đang active."""
    from services.trend_fetcher import fetch_all_active_hashtags
    await fetch_all_active_hashtags(filter_people)
    return {"message": "Đã fetch tất cả hashtag active"}


@router.post("/fetch-tiktok-channel")
async def fetch_tiktok_channel(body: TikTokChannelRequest):
    """
    Fetch videos từ kênh TikTok cụ thể (yt-dlp).
    `channel`: URL đầy đủ hoặc username (có/không có @).
    """
    from services.trend_fetcher import fetch_and_save

    # Chuẩn hoá thành URL
    channel = body.channel.strip()
    if not channel.startswith("http"):
        username = channel.lstrip("@")
        channel = f"https://www.tiktok.com/@{username}"

    result = await fetch_and_save(
        hashtag=channel,
        platform="tiktok_channel",
        max_count=body.max_count,
        browser=body.browser,
        cookies_file=body.cookies_file,
    )
    if result["error"]:
        raise HTTPException(400, result["error"])
    return {
        "message": f"Đã thêm {result['saved']} video mới từ {channel} (tổng {result['total']} tìm được)",
        "saved": result["saved"],
        "total": result["total"],
        "channel": channel,
    }


@router.post("/import", status_code=201)
async def import_urls(body: ImportRequest, background_tasks: BackgroundTasks):
    """Import danh sách URLs thủ công vào inbox."""
    urls = [u.strip() for u in body.urls if u.strip()]
    if not urls:
        raise HTTPException(400, "Không có URL hợp lệ")
    from services.trend_fetcher import import_urls as _import
    background_tasks.add_task(_import, urls, body.hashtag, body.platform)
    return {"message": f"Đang import {len(urls)} URL(s)...", "count": len(urls)}


# ── Hashtag management endpoints ──────────────────────────────────────────────

@router.get("/hashtags")
def list_hashtags(db: Session = Depends(get_db)):
    """Lấy danh sách hashtag đang theo dõi."""
    items = db.query(TrendingHashtag).order_by(TrendingHashtag.created_at).all()
    return [_hashtag_to_dict(h) for h in items]


@router.post("/hashtags", status_code=201)
def create_hashtag(body: HashtagCreate, db: Session = Depends(get_db)):
    """Thêm hashtag mới."""
    tag = body.hashtag.lstrip("#").strip().lower()
    if not tag:
        raise HTTPException(400, "Hashtag không hợp lệ")
    existing = db.query(TrendingHashtag).filter(
        TrendingHashtag.hashtag == tag,
        TrendingHashtag.platform == body.platform,
    ).first()
    if existing:
        # Reactivate nếu bị tắt
        existing.is_active = True
        db.commit()
        return _hashtag_to_dict(existing)
    item = TrendingHashtag(hashtag=tag, platform=body.platform, browser=body.browser)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _hashtag_to_dict(item)


@router.delete("/hashtags/{item_id}", status_code=204)
def delete_hashtag(item_id: int, db: Session = Depends(get_db)):
    """Xoá hashtag khỏi danh sách theo dõi."""
    item = db.query(TrendingHashtag).filter(TrendingHashtag.id == item_id).first()
    if not item:
        raise HTTPException(404, "Not found")
    db.delete(item)
    db.commit()


@router.patch("/hashtags/{item_id}/toggle")
def toggle_hashtag(item_id: int, db: Session = Depends(get_db)):
    """Bật/tắt auto-fetch cho hashtag."""
    item = db.query(TrendingHashtag).filter(TrendingHashtag.id == item_id).first()
    if not item:
        raise HTTPException(404, "Not found")
    item.is_active = not item.is_active
    db.commit()
    return _hashtag_to_dict(item)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_dict(v: TrendingVideo) -> dict:
    return {
        "id": v.id,
        "platform": v.platform,
        "hashtag": v.hashtag,
        "video_url": v.video_url,
        "video_title": v.video_title,
        "thumbnail_url": v.thumbnail_url,
        "author": v.author,
        "view_count": v.view_count,
        "status": v.status,
        "job_id": v.job_id,
        "fetched_at": v.fetched_at.isoformat() if v.fetched_at else None,
    }


def _hashtag_to_dict(h: TrendingHashtag) -> dict:
    return {
        "id": h.id,
        "hashtag": h.hashtag,
        "platform": h.platform,
        "browser": h.browser,
        "is_active": h.is_active,
        "created_at": h.created_at.isoformat() if h.created_at else None,
    }
