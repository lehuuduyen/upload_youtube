"""
Upload schedule management (cron jobs) and metadata templates.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.schedule import UploadSchedule, MetadataTemplate
from services import scheduler as sched_service

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


# ── Schedule schemas ───────────────────────────────────────────────────────

class ScheduleCreate(BaseModel):
    channel_id: int
    name: str
    cron_expression: str
    timezone: str = "Asia/Ho_Chi_Minh"
    min_interval_minutes: int = 30


class ScheduleUpdate(BaseModel):
    name: Optional[str] = None
    cron_expression: Optional[str] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None
    min_interval_minutes: Optional[int] = None


# ── Template schemas ───────────────────────────────────────────────────────

class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    title_template: Optional[str] = None
    description_template: Optional[str] = None
    tags: Optional[list[str]] = None
    category_id: str = "22"
    privacy_status: str = "private"
    language: str = "vi"
    default_music_volume: str = "0.8"
    default_original_volume: str = "0.2"


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    title_template: Optional[str] = None
    description_template: Optional[str] = None
    tags: Optional[list[str]] = None
    category_id: Optional[str] = None
    privacy_status: Optional[str] = None
    language: Optional[str] = None
    default_music_volume: Optional[str] = None
    default_original_volume: Optional[str] = None
    is_active: Optional[bool] = None


# ── Schedule endpoints ─────────────────────────────────────────────────────

@router.get("/")
def list_schedules(
    channel_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    query = db.query(UploadSchedule)
    if channel_id:
        query = query.filter(UploadSchedule.channel_id == channel_id)
    schedules = query.all()
    return [_schedule_dict(s) for s in schedules]


@router.post("/", status_code=201)
def create_schedule(body: ScheduleCreate, db: Session = Depends(get_db)):
    # Validate cron expression
    try:
        sched_service.parse_cron(body.cron_expression, body.timezone)
    except ValueError as e:
        raise HTTPException(400, str(e))

    schedule = UploadSchedule(**body.model_dump())
    db.add(schedule)
    db.commit()
    db.refresh(schedule)

    # Register with scheduler
    job_id = sched_service.add_schedule(schedule.id, body.cron_expression, body.timezone)
    next_run = sched_service.get_next_run_time(body.cron_expression, body.timezone)
    schedule.scheduler_job_id = job_id
    schedule.next_run_at = next_run
    db.commit()

    return _schedule_dict(schedule)


@router.get("/{schedule_id}")
def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    s = db.query(UploadSchedule).filter(UploadSchedule.id == schedule_id).first()
    if not s:
        raise HTTPException(404, "Schedule not found")
    return _schedule_dict(s)


@router.patch("/{schedule_id}")
def update_schedule(schedule_id: int, body: ScheduleUpdate, db: Session = Depends(get_db)):
    s = db.query(UploadSchedule).filter(UploadSchedule.id == schedule_id).first()
    if not s:
        raise HTTPException(404, "Schedule not found")

    updates = body.model_dump(exclude_none=True)
    for k, v in updates.items():
        setattr(s, k, v)
    db.commit()

    # Re-register if cron or timezone changed
    cron = updates.get("cron_expression", s.cron_expression)
    tz = updates.get("timezone", s.timezone)
    if s.is_active:
        sched_service.update_schedule(s.id, cron, tz)
    else:
        sched_service.remove_schedule(s.id)

    s.next_run_at = sched_service.get_next_run_time(cron, tz)
    db.commit()

    return _schedule_dict(s)


@router.delete("/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    s = db.query(UploadSchedule).filter(UploadSchedule.id == schedule_id).first()
    if not s:
        raise HTTPException(404, "Schedule not found")
    sched_service.remove_schedule(schedule_id)
    db.delete(s)
    db.commit()


@router.post("/{schedule_id}/pause", status_code=204)
def pause_schedule(schedule_id: int, db: Session = Depends(get_db)):
    s = db.query(UploadSchedule).filter(UploadSchedule.id == schedule_id).first()
    if not s:
        raise HTTPException(404, "Schedule not found")
    s.is_active = False
    sched_service.remove_schedule(schedule_id)
    db.commit()


@router.post("/{schedule_id}/resume", status_code=204)
def resume_schedule(schedule_id: int, db: Session = Depends(get_db)):
    s = db.query(UploadSchedule).filter(UploadSchedule.id == schedule_id).first()
    if not s:
        raise HTTPException(404, "Schedule not found")
    s.is_active = True
    sched_service.add_schedule(s.id, s.cron_expression, s.timezone)
    s.next_run_at = sched_service.get_next_run_time(s.cron_expression, s.timezone)
    db.commit()


# ── Template endpoints ─────────────────────────────────────────────────────

@router.get("/templates/")
def list_templates(db: Session = Depends(get_db)):
    return db.query(MetadataTemplate).filter(MetadataTemplate.is_active == True).all()


@router.post("/templates/", status_code=201)
def create_template(body: TemplateCreate, db: Session = Depends(get_db)):
    tmpl = MetadataTemplate(**body.model_dump())
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return tmpl


@router.get("/templates/{template_id}")
def get_template(template_id: int, db: Session = Depends(get_db)):
    tmpl = db.query(MetadataTemplate).filter(MetadataTemplate.id == template_id).first()
    if not tmpl:
        raise HTTPException(404, "Template not found")
    return tmpl


@router.patch("/templates/{template_id}")
def update_template(template_id: int, body: TemplateUpdate, db: Session = Depends(get_db)):
    tmpl = db.query(MetadataTemplate).filter(MetadataTemplate.id == template_id).first()
    if not tmpl:
        raise HTTPException(404, "Template not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(tmpl, k, v)
    db.commit()
    return tmpl


@router.delete("/templates/{template_id}", status_code=204)
def delete_template(template_id: int, db: Session = Depends(get_db)):
    tmpl = db.query(MetadataTemplate).filter(MetadataTemplate.id == template_id).first()
    if not tmpl:
        raise HTTPException(404, "Template not found")
    db.delete(tmpl)
    db.commit()


def _schedule_dict(s: UploadSchedule) -> dict:
    return {
        "id": s.id,
        "channel_id": s.channel_id,
        "name": s.name,
        "cron_expression": s.cron_expression,
        "timezone": s.timezone,
        "is_active": s.is_active,
        "min_interval_minutes": s.min_interval_minutes,
        "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
        "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None,
        "created_at": s.created_at.isoformat(),
    }
