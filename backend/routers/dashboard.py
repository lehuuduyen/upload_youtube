"""
Dashboard: stats, activity log, and thumbnail upload endpoint.
"""
import os
import shutil
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.channel import Channel
from models.video_job import VideoJob, JobStatus

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """Overall system statistics."""
    channels = db.query(Channel).count()
    authenticated = db.query(Channel).filter(Channel.is_authenticated == True).count()

    job_counts = (
        db.query(VideoJob.status, func.count(VideoJob.id))
        .group_by(VideoJob.status)
        .all()
    )
    by_status = {str(s): c for s, c in job_counts}

    today = datetime.utcnow().date()
    uploaded_today = (
        db.query(VideoJob)
        .filter(
            VideoJob.status == JobStatus.UPLOADED,
            VideoJob.completed_at >= datetime(today.year, today.month, today.day),
        )
        .count()
    )

    failed_jobs = by_status.get(JobStatus.FAILED, 0)

    return {
        "channels": {
            "total": channels,
            "authenticated": authenticated,
        },
        "jobs": {
            "total": sum(by_status.values()),
            "by_status": by_status,
            "uploaded_today": uploaded_today,
            "failed": failed_jobs,
        },
    }


@router.get("/channels/quota")
def get_quota_overview(db: Session = Depends(get_db)):
    channels = db.query(Channel).filter(Channel.is_active == True).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "quota_used": c.daily_quota_used,
            "quota_limit": c.daily_quota_limit,
            "quota_remaining": c.quota_remaining(),
            "quota_pct": round(c.daily_quota_used / max(c.daily_quota_limit, 1) * 100, 1),
            "can_upload": c.can_upload(),
        }
        for c in channels
    ]


@router.get("/activity")
def get_activity(
    limit: int = 20,
    channel_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Recent job activity."""
    query = db.query(VideoJob).order_by(VideoJob.updated_at.desc())
    if channel_id:
        query = query.filter(VideoJob.channel_id == channel_id)
    jobs = query.limit(limit).all()
    return [
        {
            "id": j.id,
            "channel_id": j.channel_id,
            "title": j.title,
            "status": j.status,
            "progress": j.progress,
            "youtube_url": j.youtube_url,
            "error_message": j.error_message,
            "updated_at": j.updated_at.isoformat() if j.updated_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        }
        for j in jobs
    ]


@router.get("/queue/upcoming")
def upcoming_uploads(
    hours: int = 24,
    db: Session = Depends(get_db),
):
    """Jobs scheduled to upload in the next N hours."""
    until = datetime.utcnow() + timedelta(hours=hours)
    jobs = (
        db.query(VideoJob)
        .filter(
            VideoJob.status == JobStatus.QUEUED,
            VideoJob.upload_at <= until,
        )
        .order_by(VideoJob.upload_at.asc())
        .all()
    )
    return [
        {
            "id": j.id,
            "title": j.title,
            "channel_id": j.channel_id,
            "upload_at": j.upload_at.isoformat() if j.upload_at else None,
            "status": j.status,
        }
        for j in jobs
    ]


@router.post("/thumbnail/upload")
async def upload_thumbnail(
    job_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a custom thumbnail image for a job."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "File must be an image")

    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")

    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    thumb_path = os.path.join(settings.THUMBNAILS_DIR, f"job_{job_id}_custom.{ext}")
    os.makedirs(settings.THUMBNAILS_DIR, exist_ok=True)

    with open(thumb_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    job.thumbnail_path = thumb_path
    db.commit()

    return {"thumbnail_path": thumb_path, "job_id": job_id}


@router.delete("/cleanup")
def cleanup_files(
    older_than_days: int = 7,
    db: Session = Depends(get_db),
):
    """Delete downloaded/processed files for completed/failed jobs older than N days."""
    cutoff = datetime.utcnow() - timedelta(days=older_than_days)
    jobs = (
        db.query(VideoJob)
        .filter(
            VideoJob.status.in_([JobStatus.UPLOADED, JobStatus.FAILED, JobStatus.CANCELLED]),
            VideoJob.completed_at <= cutoff,
        )
        .all()
    )

    deleted_count = 0
    freed_bytes = 0

    for job in jobs:
        for path_attr in ("downloaded_video_path", "downloaded_music_path", "processed_video_path"):
            path = getattr(job, path_attr)
            if path and os.path.exists(path):
                size = os.path.getsize(path)
                os.remove(path)
                freed_bytes += size
                deleted_count += 1
                setattr(job, path_attr, None)

    db.commit()

    return {
        "deleted_files": deleted_count,
        "freed_mb": round(freed_bytes / 1024 / 1024, 2),
        "jobs_cleaned": len(jobs),
    }
