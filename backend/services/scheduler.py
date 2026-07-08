"""
APScheduler-based upload scheduler.
Manages cron jobs for each channel's upload schedule.
"""
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from config import settings

scheduler = AsyncIOScheduler(timezone=settings.SCHEDULER_TIMEZONE)


def start_scheduler():
    if not scheduler.running:
        scheduler.start()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)


def parse_cron(expression: str, timezone: str = None) -> CronTrigger:
    """Parse a 5-field cron expression into a CronTrigger."""
    parts = expression.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: '{expression}'. Must have 5 fields.")
    minute, hour, day, month, day_of_week = parts
    return CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
        timezone=timezone or settings.SCHEDULER_TIMEZONE,
    )


async def _run_upload_schedule(schedule_id: int):
    """Called by APScheduler — processes the next queued video for the schedule's channel."""
    import os

    from database import SessionLocal
    from models.schedule import UploadSchedule
    from models.video_job import VideoJob, JobStatus
    from workers.job_worker import process_job, upload_only

    db = SessionLocal()
    try:
        schedule = db.query(UploadSchedule).filter(UploadSchedule.id == schedule_id).first()
        if not schedule or not schedule.is_active:
            return

        schedule.last_run_at = datetime.utcnow()
        db.commit()

        # Pick the next QUEUED job for this channel
        job = (
            db.query(VideoJob)
            .filter(
                VideoJob.channel_id == schedule.channel_id,
                VideoJob.status == JobStatus.QUEUED,
            )
            .order_by(VideoJob.priority.desc(), VideoJob.created_at.asc())
            .first()
        )

        if not job:
            return  # nothing to upload

        # Đã vào hàng đợi = người dùng đã duyệt — bỏ gate manual để cron upload
        # được (process_job gặp upload_mode="manual" sẽ trả job về READY mãi mãi).
        if job.upload_mode == "manual":
            job.upload_mode = "immediate"
            db.commit()

        if job.processed_video_path and os.path.exists(job.processed_video_path):
            # Video đã xử lý xong → upload thẳng, không chạy lại FFmpeg pipeline
            await upload_only(job.id, db)
        else:
            await process_job(job.id, db)
    finally:
        db.close()


def add_schedule(schedule_id: int, cron_expression: str, timezone: str):
    job_id = f"schedule_{schedule_id}"
    trigger = parse_cron(cron_expression, timezone)
    scheduler.add_job(
        _run_upload_schedule,
        trigger=trigger,
        id=job_id,
        args=[schedule_id],
        replace_existing=True,
    )
    return job_id


def remove_schedule(schedule_id: int):
    job_id = f"schedule_{schedule_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


def update_schedule(schedule_id: int, cron_expression: str, timezone: str):
    remove_schedule(schedule_id)
    return add_schedule(schedule_id, cron_expression, timezone)


def get_next_run_time(cron_expression: str, timezone: str) -> Optional[datetime]:
    try:
        trigger = parse_cron(cron_expression, timezone)
        return trigger.get_next_fire_time(None, datetime.utcnow())
    except Exception:
        return None


def load_all_schedules(db: Session):
    """Called on startup to restore all active schedules."""
    from models.schedule import UploadSchedule

    schedules = db.query(UploadSchedule).filter(UploadSchedule.is_active == True).all()
    for s in schedules:
        try:
            add_schedule(s.id, s.cron_expression, s.timezone)
        except Exception as e:
            print(f"Failed to load schedule {s.id}: {e}")


async def _run_trending_fetch():
    """Called by APScheduler every hour — fetch all active hashtags."""
    from services.trend_fetcher import fetch_all_active_hashtags
    await fetch_all_active_hashtags(filter_people=True)


def start_trending_scheduler():
    """Register hourly trending fetch job. Called once on app startup."""
    job_id = "trending_fetch_nailart"
    if not scheduler.get_job(job_id):
        scheduler.add_job(
            _run_trending_fetch,
            trigger="interval",
            hours=1,
            id=job_id,
            replace_existing=True,
        )


async def _run_queue_jobs():
    """Called every minute — process QUEUED jobs whose upload_at has arrived."""
    from database import SessionLocal
    from workers.job_worker import run_pending_jobs

    db = SessionLocal()
    try:
        await run_pending_jobs(db)
    finally:
        db.close()


def start_queue_scheduler():
    """Register per-minute queue processor. Called once on app startup."""
    job_id = "queue_processor"
    if not scheduler.get_job(job_id):
        scheduler.add_job(
            _run_queue_jobs,
            trigger="interval",
            minutes=1,
            id=job_id,
            replace_existing=True,
        )
