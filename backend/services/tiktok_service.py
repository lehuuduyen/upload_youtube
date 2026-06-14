"""
TikTok Content Posting API v2
Docs: https://developers.tiktok.com/doc/content-posting-api-get-started

Setup:
1. Vào https://developers.tiktok.com/ → tạo app
2. Bật "Content Posting API"
3. Lưu Client Key + Client Secret vào .env
"""
import json
import os
from datetime import datetime, timedelta
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from config import settings
from models.tiktok_account import TikTokAccount


TIKTOK_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_USER_URL = "https://open.tiktokapis.com/v2/user/info/"
TIKTOK_UPLOAD_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
TIKTOK_UPLOAD_STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"

TIKTOK_SCOPES = "user.info.basic,video.publish,video.upload"


def get_authorization_url(state: str = "") -> str:
    params = {
        "client_key": settings.TIKTOK_CLIENT_KEY,
        "scope": TIKTOK_SCOPES,
        "response_type": "code",
        "redirect_uri": settings.TIKTOK_REDIRECT_URI,
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{TIKTOK_AUTH_URL}?{query}"


def exchange_code_for_token(code: str) -> dict:
    resp = httpx.post(
        TIKTOK_TOKEN_URL,
        data={
            "client_key": settings.TIKTOK_CLIENT_KEY,
            "client_secret": settings.TIKTOK_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.TIKTOK_REDIRECT_URI,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    data = resp.json()
    if "error" in data:
        raise ValueError(f"TikTok OAuth error: {data}")
    return data


def refresh_token(account: TikTokAccount, db: Session) -> TikTokAccount:
    resp = httpx.post(
        TIKTOK_TOKEN_URL,
        data={
            "client_key": settings.TIKTOK_CLIENT_KEY,
            "client_secret": settings.TIKTOK_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": account.refresh_token,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    data = resp.json()
    if "access_token" in data:
        account.access_token = data["access_token"]
        account.refresh_token = data.get("refresh_token", account.refresh_token)
        expires_in = data.get("expires_in", 86400)
        account.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        db.commit()
    return account


def get_user_info(access_token: str) -> dict:
    resp = httpx.get(
        TIKTOK_USER_URL,
        params={"fields": "open_id,display_name,avatar_url"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    data = resp.json()
    return data.get("data", {}).get("user", {})


def _ensure_fresh_token(account: TikTokAccount, db: Session) -> str:
    if account.token_expires_at and datetime.utcnow() >= account.token_expires_at:
        account = refresh_token(account, db)
    return account.access_token


def upload_video(
    account: TikTokAccount,
    db: Session,
    video_path: str,
    title: str,
    privacy: str = "SELF_ONLY",  # PUBLIC_TO_EVERYONE / MUTUAL_FOLLOW_FRIENDS / FOLLOWER_OF_CREATOR / SELF_ONLY
    disable_comment: bool = False,
    disable_duet: bool = False,
    disable_stitch: bool = False,
) -> dict:
    """
    Upload video lên TikTok qua Content Posting API.
    Returns: {"publish_id": ..., "tiktok_url": ...}
    """
    token = _ensure_fresh_token(account, db)
    file_size = os.path.getsize(video_path)

    # Step 1: Init upload
    init_resp = httpx.post(
        TIKTOK_UPLOAD_INIT_URL,
        json={
            "post_info": {
                "title": title[:2200],
                "privacy_level": privacy,
                "disable_comment": disable_comment,
                "disable_duet": disable_duet,
                "disable_stitch": disable_stitch,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": file_size,
                "total_chunk_count": 1,
            },
        },
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"},
    )
    init_data = init_resp.json()
    if init_data.get("error", {}).get("code") != "ok":
        raise ValueError(f"TikTok init upload error: {init_data}")

    upload_url = init_data["data"]["upload_url"]
    publish_id = init_data["data"]["publish_id"]

    # Step 2: Upload file
    with open(video_path, "rb") as f:
        video_bytes = f.read()

    upload_resp = httpx.put(
        upload_url,
        content=video_bytes,
        headers={
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
            "Content-Length": str(file_size),
        },
        timeout=300,
    )
    if upload_resp.status_code not in (200, 201, 206):
        raise ValueError(f"TikTok upload failed: {upload_resp.status_code}")

    return {
        "publish_id": publish_id,
        "tiktok_url": f"https://www.tiktok.com/@{account.display_name or account.open_id}",
    }
