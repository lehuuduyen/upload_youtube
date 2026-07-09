"""
TikTok account management — OAuth2 connect/disconnect, list accounts.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.tiktok_account import TikTokAccount
from services import tiktok_service
from config import settings

router = APIRouter(prefix="/api/tiktok", tags=["tiktok"])


class CreateAccountRequest(BaseModel):
    name: str


@router.get("/accounts")
def list_accounts(db: Session = Depends(get_db)):
    accounts = db.query(TikTokAccount).all()
    return [_account_dict(a) for a in accounts]


@router.post("/accounts", status_code=201)
def create_account(body: CreateAccountRequest, db: Session = Depends(get_db)):
    acc = TikTokAccount(name=body.name)
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return _account_dict(acc)


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(account_id: int, db: Session = Depends(get_db)):
    acc = db.query(TikTokAccount).filter(TikTokAccount.id == account_id).first()
    if not acc:
        raise HTTPException(404, "Account not found")
    db.delete(acc)
    db.commit()


@router.get("/accounts/{account_id}/oauth/start")
def start_oauth(account_id: int, db: Session = Depends(get_db)):
    if not settings.TIKTOK_CLIENT_KEY:
        raise HTTPException(400, "TIKTOK_CLIENT_KEY chưa cấu hình trong .env")
    acc = db.query(TikTokAccount).filter(TikTokAccount.id == account_id).first()
    if not acc:
        raise HTTPException(404, "Account not found")
    url = tiktok_service.get_authorization_url(state=str(account_id))
    return {"auth_url": url}


@router.get("/oauth/callback")
def oauth_callback(code: str, state: str, db: Session = Depends(get_db)):
    """TikTok redirects here after user approves."""
    try:
        account_id = int(state)
        acc = db.query(TikTokAccount).filter(TikTokAccount.id == account_id).first()
        if not acc:
            return RedirectResponse(f"{settings.FRONTEND_URL}/tiktok?oauth=error&msg=account_not_found")

        token_data = tiktok_service.exchange_code_for_token(code)
        acc.access_token = token_data["access_token"]
        acc.refresh_token = token_data.get("refresh_token")
        from datetime import datetime, timedelta
        expires_in = token_data.get("expires_in", 86400)
        acc.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        acc.is_authenticated = True

        # Fetch user info
        try:
            user = tiktok_service.get_user_info(acc.access_token)
            acc.open_id = user.get("open_id")
            acc.display_name = user.get("display_name")
            acc.avatar_url = user.get("avatar_url")
        except Exception:
            pass

        db.commit()
        return RedirectResponse(f"{settings.FRONTEND_URL}/tiktok?oauth=success")

    except Exception as e:
        return RedirectResponse(f"{settings.FRONTEND_URL}/tiktok?oauth=error&msg={str(e)[:100]}")


def _account_dict(a: TikTokAccount) -> dict:
    return {
        "id": a.id,
        "name": a.name,
        "open_id": a.open_id,
        "display_name": a.display_name,
        "avatar_url": a.avatar_url,
        "is_authenticated": a.is_authenticated,
        "token_expires_at": a.token_expires_at.isoformat() if a.token_expires_at else None,
        "created_at": a.created_at.isoformat(),
    }
