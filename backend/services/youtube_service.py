"""
YouTube Data API v3 service.
Handles OAuth2 authentication, token refresh, upload, and quota tracking.
"""
import json
import logging
import os
import re
from datetime import datetime, date
from typing import Optional

logger = logging.getLogger(__name__)

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from sqlalchemy.orm import Session

from config import settings
from models.channel import Channel


YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

# YouTube category IDs
YOUTUBE_CATEGORIES = {
    "1": "Film & Animation",
    "2": "Autos & Vehicles",
    "10": "Music",
    "15": "Pets & Animals",
    "17": "Sports",
    "19": "Travel & Events",
    "20": "Gaming",
    "22": "People & Blogs",
    "23": "Comedy",
    "24": "Entertainment",
    "25": "News & Politics",
    "26": "Howto & Style",
    "27": "Education",
    "28": "Science & Technology",
    "29": "Nonprofits & Activism",
}


def _resolve_secrets_file(filename: Optional[str] = None) -> str:
    """Resolve a client secrets filename to full path. Falls back to global setting."""
    from config import BASE_DIR
    if filename:
        path = os.path.join(str(BASE_DIR), filename)
        if os.path.exists(path):
            return path
    return settings.GOOGLE_CLIENT_SECRETS_FILE


def list_client_secrets_files() -> list[str]:
    """Scan BASE_DIR for client_secret*.json files."""
    from config import BASE_DIR
    import glob
    pattern = os.path.join(str(BASE_DIR), "client_secret*.json")
    return [os.path.basename(f) for f in sorted(glob.glob(pattern))]


def get_oauth_flow(redirect_uri: Optional[str] = None, secrets_file: Optional[str] = None) -> Flow:
    path = _resolve_secrets_file(secrets_file)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Client secrets file not found: {path}\n"
            "Download it from Google Cloud Console → APIs & Services → Credentials"
        )
    flow = Flow.from_client_secrets_file(
        path,
        scopes=YOUTUBE_SCOPES,
        redirect_uri=redirect_uri or settings.OAUTH_REDIRECT_URI,
    )
    return flow


def get_authorization_url(state: str = "", secrets_file: Optional[str] = None) -> tuple[str, str]:
    flow = get_oauth_flow(secrets_file=secrets_file)
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=state,
    )
    return auth_url, state


def exchange_code_for_credentials(code: str, secrets_file: Optional[str] = None) -> dict:
    flow = get_oauth_flow(secrets_file=secrets_file)
    flow.fetch_token(code=code)
    creds = flow.credentials
    return credentials_to_dict(creds)


def credentials_to_dict(creds: Credentials) -> dict:
    return {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else [],
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
    }


def load_credentials(channel: Channel) -> Optional[Credentials]:
    if not channel.credentials_json:
        return None
    data = json.loads(channel.credentials_json)
    expiry = datetime.fromisoformat(data["expiry"]) if data.get("expiry") else None
    creds = Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=data.get("scopes"),
        expiry=expiry,
    )
    return creds


def refresh_credentials(channel: Channel, db: Session) -> Credentials:
    from google.auth.transport.requests import Request

    creds = load_credentials(channel)
    if not creds:
        raise ValueError("No credentials found for channel")

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        channel.credentials_json = json.dumps(credentials_to_dict(creds))
        db.commit()

    return creds


def get_youtube_service(channel: Channel, db: Session):
    creds = refresh_credentials(channel, db)
    return build("youtube", "v3", credentials=creds)


def fetch_channel_info(channel: Channel, db: Session) -> dict:
    service = get_youtube_service(channel, db)
    response = service.channels().list(part="snippet,statistics", mine=True).execute()
    items = response.get("items", [])
    if not items:
        raise ValueError("No YouTube channel found for these credentials")
    item = items[0]
    return {
        "channel_id": item["id"],
        "title": item["snippet"]["title"],
        "description": item["snippet"].get("description", ""),
        "thumbnail": item["snippet"]["thumbnails"].get("default", {}).get("url"),
        "subscriber_count": item["statistics"].get("subscriberCount", 0),
    }


def reset_quota_if_needed(channel: Channel, db: Session):
    today = date.today()
    if channel.quota_reset_date and channel.quota_reset_date.date() < today:
        channel.daily_quota_used = 0
        channel.quota_reset_date = datetime.utcnow()
        db.commit()


def upload_video(
    channel: Channel,
    db: Session,
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
    category_id: str = "22",
    privacy_status: str = "private",
    thumbnail_path: Optional[str] = None,
    scheduled_publish_at: Optional[datetime] = None,
    language: str = "vi",
    on_progress=None,
) -> dict:
    """
    Upload a video to YouTube.
    Returns dict with videoId, url, etc.
    Raises HttpError on failure.
    """
    reset_quota_if_needed(channel, db)

    if not channel.can_upload():
        raise ValueError(
            f"Channel cannot upload: quota_remaining={channel.quota_remaining()}, "
            f"authenticated={channel.is_authenticated}"
        )

    service = get_youtube_service(channel, db)

    # Sanitize metadata — YouTube rejects <>, null bytes, and empty titles
    def _clean(s: str) -> str:
        return re.sub(r"[<>]", "", s.replace("\x00", "")).strip() if s else ""

    clean_title = _clean(title)[:100] or "Untitled Video"
    clean_desc = _clean(description or "")[:5000]
    clean_tags = [t.strip() for t in (tags or []) if isinstance(t, str) and t.strip()]

    body = {
        "snippet": {
            "title": clean_title,
            "description": clean_desc,
            "tags": clean_tags,
            "categoryId": category_id or "22",
        },
        "status": {
            "privacyStatus": privacy_status or "private",
            "selfDeclaredMadeForKids": False,
        },
    }

    # publishAt phải là thời điểm trong tương lai; bỏ qua nếu đã qua
    if scheduled_publish_at and scheduled_publish_at > datetime.utcnow():
        body["status"]["publishAt"] = scheduled_publish_at.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    logger.info(
        "[YouTube] Uploading: title=%r privacy=%s publishAt=%s tags=%d",
        clean_title, body["status"]["privacyStatus"],
        body["status"].get("publishAt", "none"), len(clean_tags),
    )

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=5 * 1024 * 1024,  # 5MB chunks — nhỏ hơn để dễ retry
    )

    request = service.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    # Retry với exponential backoff khi gặp lỗi mạng hoặc server 5xx
    import socket, time
    RETRIABLE_STATUS = {500, 502, 503, 504}
    RETRIABLE_EXC = (OSError, IOError, socket.error, socket.timeout)
    MAX_RETRIES = 10

    response = None
    retry = 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status and on_progress:
                on_progress(int(status.progress() * 100))
            retry = 0  # reset sau mỗi chunk thành công
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS:
                retry += 1
                if retry > MAX_RETRIES:
                    raise
                wait = min(2 ** retry, 60)
                logger.warning("[YouTube] Server error %d, retry %d/%d in %ds", e.resp.status, retry, MAX_RETRIES, wait)
                time.sleep(wait)
            else:
                raise
        except RETRIABLE_EXC as e:
            retry += 1
            if retry > MAX_RETRIES:
                raise
            wait = min(2 ** retry, 60)
            logger.warning("[YouTube] Network error: %s, retry %d/%d in %ds", e, retry, MAX_RETRIES, wait)
            time.sleep(wait)

    video_id = response["id"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"

    # Upload thumbnail
    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            service.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path),
            ).execute()
            channel.daily_quota_used += 50  # thumbnail costs 50 units
        except HttpError as e:
            pass  # thumbnail failure is non-fatal

    # Deduct quota (upload ≈ 1600 units)
    channel.daily_quota_used += 1600
    channel.last_upload_at = datetime.utcnow()
    db.commit()

    return {
        "video_id": video_id,
        "url": video_url,
        "title": response["snippet"]["title"],
        "privacy": response["status"]["privacyStatus"],
    }
