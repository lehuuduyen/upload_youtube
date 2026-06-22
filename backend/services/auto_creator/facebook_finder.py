"""
Facebook Finder — liệt kê reels từ một profile/page Facebook.

yt-dlp KHÔNG có extractor cho trang reels_tab của profile (báo "Unsupported URL"),
nên ta tự scrape HTML trang reels (cần cookies đăng nhập) để lấy các reel ID,
sau đó enrich metadata từng reel qua yt-dlp (yt-dlp tải/đọc được reel đơn lẻ).

Cấu hình cookies trong .env:
  FACEBOOK_COOKIES_FILE         — đường dẫn cookies.txt (Netscape) export từ trình duyệt đã login
  FACEBOOK_COOKIES_FROM_BROWSER — "chrome" | "firefox" | "edge" | "safari" (thay cho file)
"""
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from http.cookiejar import MozillaCookieJar

import requests

from config import settings
from services.auto_creator.video_finder import (
    _parse_upload_date,
    _relative_time_from_timestamp,
)

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# reel id xuất hiện trong HTML dưới dạng /reel/<digits>
_REEL_ID_RE = re.compile(r"/reel/(\d+)")


def is_facebook_url(url: str) -> bool:
    return "facebook.com" in (url or "") or "fb.watch" in (url or "")


def cookie_args(url: str = "") -> list[str]:
    """Args cookies cho yt-dlp khi thao tác với URL Facebook."""
    if url and not is_facebook_url(url):
        return []
    if settings.FACEBOOK_COOKIES_FROM_BROWSER:
        return ["--cookies-from-browser", settings.FACEBOOK_COOKIES_FROM_BROWSER]
    f = settings.FACEBOOK_COOKIES_FILE
    if f and os.path.exists(f):
        return ["--cookies", f]
    return []


def has_cookies() -> bool:
    if settings.FACEBOOK_COOKIES_FROM_BROWSER:
        return True
    f = settings.FACEBOOK_COOKIES_FILE
    return bool(f and os.path.exists(f))


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": _UA,
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        # Thiếu các header sec-fetch-* → facebook.com trả 400. Bắt buộc phải có.
        "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
    })
    f = settings.FACEBOOK_COOKIES_FILE
    if f and os.path.exists(f):
        cj = MozillaCookieJar(f)
        try:
            cj.load(ignore_discard=True, ignore_expires=True)
            s.cookies = cj
        except Exception:
            pass
    elif settings.FACEBOOK_COOKIES_FROM_BROWSER:
        try:
            import browser_cookie3  # type: ignore
            loader = getattr(browser_cookie3, settings.FACEBOOK_COOKIES_FROM_BROWSER, None)
            if loader:
                s.cookies = loader(domain_name="facebook.com")
        except Exception:
            pass
    return s


def _fetch_html(url: str) -> str:
    """Tải HTML trang reels. Thử cả bản www và mbasic (mbasic dễ parse hơn)."""
    sess = _session()
    html = ""
    for candidate in (url, _to_mbasic(url)):
        if not candidate:
            continue
        try:
            r = sess.get(candidate, timeout=30, allow_redirects=True)
            if r.status_code == 200 and r.text:
                html = r.text
                # nếu đã thấy reel id thì dừng sớm
                if _REEL_ID_RE.search(html):
                    return html
        except requests.RequestException:
            continue
    return html


def _to_mbasic(url: str) -> str:
    if "facebook.com" not in url:
        return ""
    return url.replace("://www.facebook.com", "://mbasic.facebook.com") \
              .replace("://m.facebook.com", "://mbasic.facebook.com") \
              .replace("://facebook.com", "://mbasic.facebook.com")


def _extract_reel_ids(html: str, limit: int) -> list[str]:
    seen = []
    for m in _REEL_ID_RE.finditer(html):
        rid = m.group(1)
        if rid not in seen:
            seen.append(rid)
        if len(seen) >= limit * 3:  # lấy dư để bù những reel enrich lỗi
            break
    return seen


def _reel_info(reel_url: str) -> dict | None:
    """Lấy metadata 1 reel qua yt-dlp (kèm cookies). None nếu thất bại."""
    cmd = (
        ["yt-dlp", reel_url, "--dump-json", "--no-download", "--no-playlist",
         "--no-warnings", "--quiet"]
        + cookie_args(reel_url)
    )
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
        if r.returncode != 0 or not r.stdout.strip():
            return None
        data = json.loads(r.stdout.strip().splitlines()[0])
    except Exception:
        return None

    vid_id = data.get("id", "")
    dur_sec = data.get("duration") or 0
    dur_str = ""
    if dur_sec:
        m, s = divmod(int(dur_sec), 60)
        dur_str = f"{m}:{s:02d}" if m < 60 else f"{m//60}:{m%60:02d}:{s:02d}"
    thumbs = data.get("thumbnails") or []
    thumb = thumbs[-1].get("url", "") if thumbs else (data.get("thumbnail") or "")
    ts = data.get("timestamp") or data.get("release_timestamp")

    return {
        "id": vid_id or reel_url,
        "title": (data.get("title") or data.get("description") or "Reel Facebook")[:120],
        "url": data.get("webpage_url") or reel_url,
        "thumbnail": thumb,
        "view_count": data.get("view_count") or 0,
        "like_count": data.get("like_count") or 0,
        "duration_sec": dur_sec,
        "duration": dur_str,
        "uploader": data.get("uploader") or data.get("channel") or "",
        "upload_date": _parse_upload_date(data.get("upload_date", "")),
        "uploaded_ago": _relative_time_from_timestamp(ts),
        "_ts": float(ts) if ts else 0,
        "description": (data.get("description") or "")[:300],
    }


def list_facebook_reels(profile_url: str, max_results: int = 12) -> list[dict]:
    """Scrape danh sách reels của 1 profile/page Facebook → list video card."""
    if not has_cookies():
        raise RuntimeError(
            "Chưa cấu hình cookies Facebook. Export cookies.txt từ trình duyệt đã đăng nhập "
            "rồi đặt đường dẫn vào FACEBOOK_COOKIES_FILE (hoặc set FACEBOOK_COOKIES_FROM_BROWSER)."
        )

    html = _fetch_html(profile_url)
    if not html:
        raise RuntimeError("Không tải được trang Facebook (kiểm tra cookies/đăng nhập).")

    reel_ids = _extract_reel_ids(html, max_results)
    if not reel_ids:
        raise RuntimeError(
            "Không tìm thấy reel nào trong trang. Có thể cookies hết hạn, profile không có "
            "reels công khai, hoặc Facebook đã đổi giao diện."
        )

    # chừa buffer gấp đôi để bù reel enrich lỗi, nhưng giới hạn số tiến trình yt-dlp
    reel_urls = [f"https://www.facebook.com/reel/{rid}" for rid in reel_ids][: max_results * 2]

    # Enrich song song; bỏ reel lỗi, giữ tối đa max_results reel hợp lệ
    videos: list[dict] = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        for info in ex.map(_reel_info, reel_urls):
            if info:
                videos.append(info)
            if len(videos) >= max_results:
                break

    if not videos:
        raise RuntimeError(
            "Tìm thấy reel nhưng không đọc được metadata (yt-dlp cần cookies hợp lệ để xem reel)."
        )

    if any(v["_ts"] for v in videos):
        videos = sorted(videos, key=lambda v: v.get("_ts") or 0, reverse=True)
    return videos
