"""
Queue management: list jobs, pause/resume, reorder, retry, cancel.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.video_job import VideoJob, JobStatus

router = APIRouter(prefix="/api/queue", tags=["queue"])


class JobUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    category_id: Optional[str] = None
    privacy_status: Optional[str] = None
    upload_at: Optional[str] = None
    priority: Optional[int] = None
    thumbnail_path: Optional[str] = None


@router.get("/")
def list_queue(
    channel_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    query = db.query(VideoJob)
    if channel_id:
        query = query.filter(VideoJob.channel_id == channel_id)
    if status:
        try:
            query = query.filter(VideoJob.status == JobStatus(status))
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")

    total = query.count()
    jobs = (
        query.order_by(VideoJob.priority.desc(), VideoJob.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "items": [_job_dict(j) for j in jobs],
    }


@router.get("/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    return _job_dict(job, include_log=True)


@router.patch("/{job_id}")
def update_job(job_id: int, body: JobUpdateRequest, db: Session = Depends(get_db)):
    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status in (JobStatus.UPLOADING, JobStatus.UPLOADED):
        raise HTTPException(400, "Cannot edit a job that is uploading or completed")

    for k, v in body.model_dump(exclude_none=True).items():
        if k == "upload_at" and v:
            setattr(job, k, datetime.fromisoformat(v))
        else:
            setattr(job, k, v)
    db.commit()
    return _job_dict(job)


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status == JobStatus.UPLOADING:
        raise HTTPException(400, "Cannot delete a job that is currently uploading")
    db.delete(job)
    db.commit()


@router.post("/{job_id}/cancel", status_code=204)
def cancel_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status in (JobStatus.UPLOADED, JobStatus.CANCELLED):
        raise HTTPException(400, f"Job already {job.status}")
    job.status = JobStatus.CANCELLED
    db.commit()


@router.post("/{job_id}/retry")
async def retry_job(job_id: int, db: Session = Depends(get_db)):
    import asyncio
    import os

    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status not in (JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.QUEUED):
        raise HTTPException(400, "Can only retry failed, cancelled or stuck queued jobs")

    job.status = JobStatus.PENDING
    job.error_message = None
    job.retry_count = 0
    job.progress = 0
    job.started_at = None
    job.completed_at = None
    db.commit()

    if job.auto_topic:
        if job.processed_video_path and os.path.exists(job.processed_video_path):
            from workers.job_worker import upload_only
            asyncio.create_task(upload_only(job_id, db))
        elif job.downloaded_video_path and os.path.exists(job.downloaded_video_path):
            from routers.auto_creator import _run_reup_pipeline
            asyncio.create_task(_run_reup_pipeline(job_id, job.auto_topic, None, "", "", False))
        elif job.video_url:
            from routers.auto_creator import _run_reup_pipeline
            asyncio.create_task(_run_reup_pipeline(job_id, job.auto_topic, job.video_url, "", "", False))
        else:
            from routers.auto_creator import _run_auto_pipeline
            asyncio.create_task(_run_auto_pipeline(job_id, job.auto_topic, "", "nu_mien_bac", 60))
    else:
        from workers.job_worker import process_job
        asyncio.create_task(process_job(job_id, db))

    return {"message": "Job restarted", "id": job.id}


@router.post("/{job_id}/queue")
def enqueue_job(job_id: int, db: Session = Depends(get_db)):
    """Move a READY/PENDING job to QUEUED status so the scheduler picks it up."""
    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status not in (JobStatus.PENDING, JobStatus.READY):
        raise HTTPException(400, f"Job must be PENDING or READY to queue, got {job.status}")
    job.status = JobStatus.QUEUED
    db.commit()
    return {"message": "Job queued", "id": job.id}


@router.post("/{job_id}/upload-now")
async def upload_now(job_id: int, db: Session = Depends(get_db)):
    """Immediately trigger upload for a job.
    - If processed_video_path exists → skip to upload step directly.
    - Otherwise → run full pipeline with upload_mode=immediate.
    """
    from workers.job_worker import process_job, upload_only
    import asyncio

    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status == JobStatus.UPLOADING:
        raise HTTPException(400, "Job is already uploading")

    import os
    if job.processed_video_path and os.path.exists(job.processed_video_path):
        # File already processed — go straight to upload
        job.status = JobStatus.PENDING
        job.error_message = None
        job.upload_mode = "immediate"
        db.commit()
        asyncio.create_task(upload_only(job_id, db))
    else:
        # Need full pipeline
        job.status = JobStatus.PENDING
        job.error_message = None
        job.progress = 0
        job.started_at = None
        job.completed_at = None
        job.upload_mode = "immediate"
        db.commit()
        asyncio.create_task(process_job(job_id, db))

    return {"message": "Upload started", "id": job_id}


@router.post("/reorder")
def reorder_queue(
    job_ids: list[int],  # ordered list — first = highest priority
    db: Session = Depends(get_db),
):
    """Reorder the queue by setting priority based on position in the list."""
    total = len(job_ids)
    for idx, job_id in enumerate(job_ids):
        job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
        if job:
            job.priority = total - idx
    db.commit()
    return {"message": "Queue reordered"}


def _job_dict(job: VideoJob, include_log: bool = False) -> dict:
    d = {
        "id": job.id,
        "channel_id": job.channel_id,
        "status": job.status,
        "title": job.title,
        "description": job.description,
        "tags": job.tags,
        "category_id": job.category_id,
        "privacy_status": job.privacy_status,
        "video_url": job.video_url,
        "music_url": job.music_url,
        "video_quality": job.video_quality,
        "output_format": job.output_format,
        "mute_original": job.mute_original,
        "original_volume": job.original_volume,
        "music_volume": job.music_volume,
        "progress": job.progress,
        "error_message": job.error_message,
        "youtube_video_id": job.youtube_video_id,
        "youtube_url": job.youtube_url,
        "tiktok_url": job.tiktok_url,
        "thumbnail_path": job.thumbnail_path,
        "upload_at": job.upload_at.isoformat() if job.upload_at else None,
        "priority": job.priority,
        "retry_count": job.retry_count,
        "platform": job.platform,
        "review_status": job.review_status,
        "upload_mode": job.upload_mode,
        "auto_topic": job.auto_topic,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
    if include_log:
        d["log"] = job.log
    return d
