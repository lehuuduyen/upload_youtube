"""
Download endpoints: validate URL, fetch info, trigger download jobs.
"""
import re
import os
import shutil
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[mK]", "", str(text))

from database import get_db
from models.video_job import VideoJob, JobStatus
from services.downloader import get_video_info

router = APIRouter(prefix="/api/downloads", tags=["downloads"])


class UrlInfoRequest(BaseModel):
    url: str


class CreateJobRequest(BaseModel):
    channel_id: int
    video_url: Optional[str] = None
    music_url: Optional[str] = None
    music_file_path: Optional[str] = None
    clip_paths: Optional[list[str]] = None   # uploaded video clips to concat
    video_quality: str = "1080p"
    music_start_time: Optional[float] = None
    music_end_time: Optional[float] = None

    # Processing
    mute_original: bool = True
    mute_range_start: Optional[float] = None   # giây — bắt đầu tắt tiếng gốc
    mute_range_end: Optional[float] = None     # giây — kết thúc tắt tiếng gốc
    original_volume: float = 0.2
    music_volume: float = 0.8
    loop_music: bool = True
    fade_in_duration: float = 0.0
    fade_out_duration: float = 2.0
    output_format: str = "16:9"

    # Metadata
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    category_id: str = "22"
    privacy_status: str = "private"
    language: str = "vi"
    template_id: Optional[int] = None

    # Upload mode: "immediate" = process + upload now; "manual" = process then stop at READY
    upload_mode: str = "immediate"

    # Outro clip appended at the end
    outro_path: Optional[str] = None

    # Logo/icon overlay
    logo_path: Optional[str] = None
    logo_position: str = "top-left"
    logo_size: int = 80

    # Scheduling
    upload_at: Optional[str] = None  # ISO datetime string

    priority: int = 0


class JobOut(BaseModel):
    id: int
    channel_id: int
    status: str
    video_url: Optional[str]
    music_url: Optional[str]
    title: Optional[str]
    progress: float
    error_message: Optional[str]
    youtube_url: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


@router.post("/info")
async def get_url_info(body: UrlInfoRequest):
    """Fetch video metadata (title, duration, formats) without downloading."""
    try:
        info = get_video_info(body.url)
        return info
    except Exception as e:
        raise HTTPException(400, f"Cannot fetch info: {_strip_ansi(e)}")


@router.post("/jobs", status_code=201)
async def create_job(
    body: CreateJobRequest,
    db: Session = Depends(get_db),
):
    """
    Lưu job với metadata — chưa download hay xử lý gì.
    Scheduler sẽ kích hoạt pipeline khi đến upload_at (hoặc ngay khi không có upload_at).
    """
    from datetime import datetime as dt, timezone

    upload_at = None
    if body.upload_at:
        try:
            parsed = dt.fromisoformat(body.upload_at.replace("Z", "+00:00"))
            upload_at = parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed
        except ValueError:
            raise HTTPException(400, "Invalid upload_at format. Use ISO 8601.")

    if not body.video_url and not body.clip_paths:
        raise HTTPException(400, "Phải có video_url hoặc ít nhất 1 clip_paths")

    job = VideoJob(
        channel_id=body.channel_id,
        template_id=body.template_id,
        video_url=body.video_url,
        music_url=body.music_url,
        music_file_path=body.music_file_path,
        clip_paths=body.clip_paths or [],
        outro_path=body.outro_path or None,
        logo_path=body.logo_path or None,
        logo_position=body.logo_position,
        logo_size=body.logo_size,
        video_quality=body.video_quality,
        music_start_time=body.music_start_time,
        music_end_time=body.music_end_time,
        mute_original=body.mute_original,
        mute_range_start=body.mute_range_start,
        mute_range_end=body.mute_range_end,
        original_volume=body.original_volume,
        music_volume=body.music_volume,
        loop_music=body.loop_music,
        fade_in_duration=body.fade_in_duration,
        fade_out_duration=body.fade_out_duration,
        output_format=body.output_format,
        title=body.title,
        description=body.description,
        tags=body.tags,
        category_id=body.category_id,
        privacy_status=body.privacy_status,
        language=body.language,
        upload_mode=body.upload_mode,
        upload_at=upload_at,
        priority=body.priority,
        status=JobStatus.PENDING,  # luôn PENDING — scheduler sẽ khởi động pipeline
    )

    # Apply template defaults
    if body.template_id:
        from models.schedule import MetadataTemplate
        tmpl = db.query(MetadataTemplate).filter(MetadataTemplate.id == body.template_id).first()
        if tmpl:
            if not job.title and tmpl.title_template:
                job.title = tmpl.title_template.replace("{date}", dt.now().strftime("%Y-%m-%d"))
            if not job.description and tmpl.description_template:
                job.description = tmpl.description_template
            if not job.tags and tmpl.tags:
                job.tags = tmpl.tags
            if tmpl.category_id:
                job.category_id = tmpl.category_id
            if tmpl.privacy_status:
                job.privacy_status = tmpl.privacy_status

    db.add(job)
    db.commit()
    db.refresh(job)

    scheduled = upload_at is not None and upload_at > dt.utcnow()
    return {
        "id": job.id,
        "status": job.status,
        "message": f"Đã lên lịch lúc {upload_at.isoformat()}" if scheduled else "Job đã lưu — sẽ xử lý ngay",
        "upload_at": upload_at.isoformat() if upload_at else None,
    }


# ── Cookies.txt management ────────────────────────────────────────────────────

@router.get("/cookies/status")
async def get_cookies_status():
    """Kiểm tra cookies.txt có tồn tại không."""
    from config import settings
    exists = os.path.exists(settings.COOKIES_FILE)
    size = os.path.getsize(settings.COOKIES_FILE) if exists else 0
    return {
        "exists": exists,
        "path": settings.COOKIES_FILE,
        "size_kb": round(size / 1024, 1) if exists else 0,
    }


@router.post("/cookies/upload")
async def upload_cookies(file: UploadFile = File(...)):
    """Upload cookies.txt để bypass Cloudflare."""
    from config import settings
    if not file.filename.endswith(".txt"):
        raise HTTPException(400, "Chỉ chấp nhận file .txt (Netscape cookies format)")
    content = await file.read()
    # Validate basic Netscape cookies format
    text = content.decode("utf-8", errors="ignore")
    if "# Netscape HTTP Cookie File" not in text and "# HTTP Cookie File" not in text:
        raise HTTPException(400, "File không đúng định dạng Netscape cookies. Dùng extension 'Get cookies.txt LOCALLY' để export.")
    with open(settings.COOKIES_FILE, "wb") as f:
        f.write(content)
    return {"message": "Đã lưu cookies.txt", "path": settings.COOKIES_FILE}


@router.delete("/cookies")
async def delete_cookies():
    """Xóa cookies.txt."""
    from config import settings
    if os.path.exists(settings.COOKIES_FILE):
        os.remove(settings.COOKIES_FILE)
    return {"message": "Đã xóa cookies.txt"}
