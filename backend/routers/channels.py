"""
Channel management: CRUD, OAuth2 flow, quota tracking.
"""
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.channel import Channel
from services import youtube_service

router = APIRouter(prefix="/api/channels", tags=["channels"])


# ── Schemas ────────────────────────────────────────────────────────────────

class ChannelCreate(BaseModel):
    name: str
    description: Optional[str] = None
    default_timezone: str = "Asia/Ho_Chi_Minh"
    default_privacy: str = "private"
    default_category_id: str = "22"
    min_upload_interval_minutes: int = 30
    client_secrets_file: Optional[str] = None


class ChannelUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    default_timezone: Optional[str] = None
    default_privacy: Optional[str] = None
    default_category_id: Optional[str] = None
    min_upload_interval_minutes: Optional[int] = None
    is_active: Optional[bool] = None
    daily_quota_limit: Optional[int] = None


class ChannelOut(BaseModel):
    id: int
    name: str
    channel_id: Optional[str]
    email: Optional[str]
    description: Optional[str]
    is_authenticated: bool
    is_active: bool
    daily_quota_used: int
    daily_quota_limit: int
    quota_remaining: int
    default_timezone: str
    default_privacy: str
    default_category_id: str
    min_upload_interval_minutes: int
    last_upload_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/", response_model=list[ChannelOut])
def list_channels(db: Session = Depends(get_db)):
    channels = db.query(Channel).all()
    result = []
    for c in channels:
        d = {**c.__dict__, "quota_remaining": c.quota_remaining()}
        result.append(d)
    return result


@router.get("/client-secrets-files")
def list_client_secrets_files():
    """List available client_secret*.json files in the project root."""
    return youtube_service.list_client_secrets_files()


@router.post("/", response_model=ChannelOut, status_code=201)
def create_channel(body: ChannelCreate, db: Session = Depends(get_db)):
    channel = Channel(**body.model_dump())
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return {**channel.__dict__, "quota_remaining": channel.quota_remaining()}


@router.get("/{channel_id}", response_model=ChannelOut)
def get_channel(channel_id: int, db: Session = Depends(get_db)):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(404, "Channel not found")
    return {**channel.__dict__, "quota_remaining": channel.quota_remaining()}


@router.patch("/{channel_id}", response_model=ChannelOut)
def update_channel(channel_id: int, body: ChannelUpdate, db: Session = Depends(get_db)):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(404, "Channel not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(channel, k, v)
    db.commit()
    db.refresh(channel)
    return {**channel.__dict__, "quota_remaining": channel.quota_remaining()}


@router.delete("/{channel_id}", status_code=204)
def delete_channel(channel_id: int, db: Session = Depends(get_db)):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(404, "Channel not found")
    db.delete(channel)
    db.commit()


# ── OAuth2 Flow ────────────────────────────────────────────────────────────

@router.get("/{channel_id}/oauth/start")
def start_oauth(channel_id: int, db: Session = Depends(get_db)):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(404, "Channel not found")
    try:
        auth_url, state = youtube_service.get_authorization_url(
            state=str(channel_id),
            secrets_file=channel.client_secrets_file,
        )
        return {"auth_url": auth_url, "state": state}
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))


@router.get("/oauth/callback")
def oauth_callback(
    code: str = Query(...),
    state: str = Query(""),
    db: Session = Depends(get_db),
):
    """OAuth2 callback — exchanges code for credentials and saves to channel."""
    channel_id = int(state) if state.isdigit() else None
    if not channel_id:
        raise HTTPException(400, "Invalid state parameter")

    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(404, "Channel not found")

    try:
        creds_dict = youtube_service.exchange_code_for_credentials(code, secrets_file=channel.client_secrets_file)
        channel.credentials_json = json.dumps(creds_dict)
        channel.is_authenticated = True
        db.commit()

        # Fetch actual channel info
        info = youtube_service.fetch_channel_info(channel, db)
        channel.channel_id = info["channel_id"]
        channel.name = info["title"] if not channel.name or channel.name == channel.name else channel.name
        db.commit()

        # Redirect to frontend
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/channels?oauth=success")
    except Exception as e:
        raise HTTPException(400, f"OAuth error: {e}")


@router.post("/{channel_id}/oauth/revoke", status_code=204)
def revoke_oauth(channel_id: int, db: Session = Depends(get_db)):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(404, "Channel not found")
    channel.credentials_json = None
    channel.is_authenticated = False
    channel.channel_id = None
    db.commit()


@router.post("/{channel_id}/quota/reset", status_code=204)
def reset_quota(channel_id: int, db: Session = Depends(get_db)):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(404, "Channel not found")
    channel.daily_quota_used = 0
    channel.quota_reset_date = datetime.utcnow()
    db.commit()


@router.get("/categories/list")
def list_categories():
    return youtube_service.YOUTUBE_CATEGORIES
