"""
Fetch trending videos for the inbox.

Sources:
  - instagram_reels : Instagram Reels từ hashtag (Chrome/Firefox cookies)
  - youtube_shorts  : YouTube Shorts qua yt-dlp (không cần login)

Person detection:
  Dùng skin-color ratio trên phần đỉnh thumbnail (9:16 frame).
  Nếu top-25% có >18% pixel da → likely có mặt người → bỏ qua.
"""
import io
import json
import logging
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
logger = logging.getLogger(__name__)

# ── Person detection ──────────────────────────────────────────────────────────

def _skin_ratio_top(image_bytes: bytes, top_fraction: float = 0.25) -> float:
    """
    Tính tỷ lệ pixel màu da trong phần đỉnh của ảnh.
    Ảnh được resize về 200×356 (tỷ lệ 9:16 của Reels).
    """
    try:
        import numpy as np
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((200, 356))
        arr = np.array(img).astype("float32")
        cutoff = int(356 * top_fraction)
        region = arr[:cutoff, :, :]
        R, G, B = region[:, :, 0], region[:, :, 1], region[:, :, 2]
        skin = (
            (R > 95) & (G > 40) & (B > 20)
            & (R > G) & (R > B)
            & ((R - np.minimum(G, B)) > 15)
            & (abs(R.astype("int32") - G.astype("int32")) > 15)
        )
        return float(skin.mean())
    except Exception:
        return 0.0


def thumbnail_has_person(
    thumb_url: str,
    session=None,
    threshold: float = 0.18,
) -> bool:
    """
    Trả về True nếu thumbnail có khả năng có người (mặt/thân trên).
    Sử dụng session (nếu có) để tải ảnh từ Instagram CDN.
    """
    if not thumb_url:
        return False
    try:
        if session is not None:
            r = session.get(thumb_url, timeout=6)
        else:
            import requests
            r = requests.get(thumb_url, timeout=6, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return False
        ratio = _skin_ratio_top(r.content)
        return ratio > threshold
    except Exception:
        return False  # không download được → không lọc


# ── Instagram Reels ───────────────────────────────────────────────────────────

def fetch_instagram_reels(
    hashtag: str,
    max_count: int = 30,
    browser: str = "chrome",
    filter_people: bool = True,
) -> list[dict]:
    """
    Fetch Instagram Reels cho hashtag, tuỳ chọn lọc video có người.
    Yêu cầu login Instagram trên browser.
    """
    try:
        import browser_cookie3
        import requests as req
    except ImportError:
        raise RuntimeError("Thiếu thư viện: pip install browser-cookie3 requests")

    try:
        loader_fn = getattr(browser_cookie3, browser, None)
        if not loader_fn:
            raise RuntimeError(f"Browser không hỗ trợ: {browser}")
        raw_cookies = loader_fn(domain_name=".instagram.com")
    except PermissionError as e:
        raise RuntimeError(f"Không đọc được cookies từ {browser}: {e}")

    session = req.Session()
    for c in raw_cookies:
        session.cookies.set(c.name, c.value, domain=c.domain)

    if not session.cookies.get("sessionid"):
        raise RuntimeError(
            f"Chưa đăng nhập Instagram trên {browser}. Hãy login rồi thử lại."
        )

    csrftoken = session.cookies.get("csrftoken", "")
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "X-CSRFToken": csrftoken,
        "X-IG-App-ID": "936619743392459",
        "Accept": "application/json",
        "Referer": f"https://www.instagram.com/explore/tags/{hashtag}/",
    })

    # Collect raw candidates (up to 2× max_count để sau khi lọc vẫn đủ)
    fetch_limit = max_count * 2 if filter_people else max_count
    candidates = []
    page = 1
    next_media_ids = "[]"

    while len(candidates) < fetch_limit:
        try:
            r = session.post(
                f"https://www.instagram.com/api/v1/tags/{hashtag}/sections/",
                data={"tab": "clips", "page": page, "next_media_ids": next_media_ids, "surface": "grid"},
                timeout=15,
            )
        except Exception as e:
            logger.error(f"[Instagram] Request error #{hashtag}: {e}")
            break

        if r.status_code != 200:
            logger.error(f"[Instagram] API {r.status_code} for #{hashtag}")
            break

        try:
            data = r.json()
        except Exception:
            break

        for sec in data.get("sections", []):
            for item in sec.get("layout_content", {}).get("medias", []):
                m = item.get("media", {})
                if m.get("media_type") != 2:
                    continue
                code = m.get("code", "")
                if not code:
                    continue
                caption_node = m.get("caption") or {}
                caption = (
                    caption_node.get("text", "") if isinstance(caption_node, dict) else ""
                )[:300]
                user = m.get("user", {})
                imgs = m.get("image_versions2", {}).get("candidates", [])
                thumb = imgs[0].get("url") if imgs else None
                candidates.append({
                    "video_url": f"https://www.instagram.com/reel/{code}/",
                    "video_title": caption,
                    "thumbnail_url": thumb,
                    "author": user.get("username"),
                    "view_count": m.get("play_count") or m.get("view_count") or None,
                    "_thumb_for_check": thumb,  # same URL, used for person check
                })
                if len(candidates) >= fetch_limit:
                    break
            if len(candidates) >= fetch_limit:
                break

        if not data.get("more_available"):
            break
        next_media_ids = json.dumps(data.get("next_media_ids", []))
        page = data.get("next_page", page + 1)

    if not filter_people:
        videos = candidates[:max_count]
    else:
        # Parallel thumbnail checks
        person_flags: dict[int, bool] = {}
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {
                pool.submit(thumbnail_has_person, c["_thumb_for_check"], session): i
                for i, c in enumerate(candidates)
                if c.get("_thumb_for_check")
            }
            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    person_flags[idx] = fut.result()
                except Exception:
                    person_flags[idx] = False

        videos = []
        for i, c in enumerate(candidates):
            if not person_flags.get(i, False):
                del c["_thumb_for_check"]
                videos.append(c)
            if len(videos) >= max_count:
                break

    # Remove helper key if filter_people=False
    for v in videos:
        v.pop("_thumb_for_check", None)

    logger.info(
        f"[Instagram] #{hashtag}: {len(videos)} Reels kept "
        f"(from {len(candidates)} fetched, filter_people={filter_people})"
    )
    return videos


# ── YouTube Shorts ────────────────────────────────────────────────────────────

def fetch_youtube_shorts(keyword: str, max_count: int = 30) -> list[dict]:
    """Search YouTube Shorts (no login required). Filters ≤60s."""
    query = f"ytsearch{max_count}:{keyword} shorts"
    cmd = [
        "yt-dlp", "--flat-playlist", "--dump-json", "--no-warnings",
        "--extractor-args", "youtube:player_client=android,web",
        query,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        logger.error(f"[YouTube] Timeout for '{keyword}'")
        return []
    except Exception as e:
        logger.error(f"[YouTube] Error: {e}")
        return []

    videos = []
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        vid_id = entry.get("id", "")
        if not vid_id or (entry.get("duration") or 0) > 60:
            continue
        videos.append({
            "video_url": f"https://www.youtube.com/watch?v={vid_id}",
            "video_title": (entry.get("title") or "")[:300],
            "thumbnail_url": entry.get("thumbnail"),
            "author": entry.get("uploader") or entry.get("channel") or None,
            "view_count": entry.get("view_count"),
        })
    logger.info(f"[YouTube] Shorts '{keyword}': {len(videos)} videos")
    return videos


# ── TikTok Channel ───────────────────────────────────────────────────────────

def fetch_tiktok_channel(
    channel: str,
    max_count: int = 30,
    browser: str = "",
    cookies_file: str = "",
) -> list[dict]:
    """
    Fetch videos từ một kênh TikTok cụ thể dùng yt-dlp.
    `channel` có thể là URL đầy đủ (https://www.tiktok.com/@username)
    hoặc chỉ username (@username / username).
    `browser`: "chrome"|"firefox"|"edge" để lấy cookies từ browser (local dev).
    `cookies_file`: đường dẫn tới file cookies.txt (Netscape format) dùng trong Docker.
    """
    if channel.startswith("http"):
        url = channel.rstrip("/")
    else:
        username = channel.lstrip("@")
        url = f"https://www.tiktok.com/@{username}"

    # Fetch thêm để bù cho các entry bị lỗi parse
    fetch_limit = max_count + 20

    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--dump-json",
        "--no-warnings",
        "--playlist-end", str(fetch_limit),
    ]

    # Cookies: file ưu tiên hơn browser (dùng được trong Docker)
    if cookies_file and os.path.exists(cookies_file):
        cmd += ["--cookies", cookies_file]
        logger.info(f"[TikTok] Using cookies file: {cookies_file}")
    elif browser:
        cmd += ["--cookies-from-browser", browser]
        logger.info(f"[TikTok] Using cookies from browser: {browser}")

    cmd.append(url)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        logger.error(f"[TikTok] Timeout fetching channel: {url}")
        return []
    except Exception as e:
        logger.error(f"[TikTok] Error fetching channel {url}: {e}")
        return []

    if result.returncode != 0 and not result.stdout.strip():
        logger.error(f"[TikTok] yt-dlp failed for {url}: {result.stderr[:500]}")
        return []

    videos = []
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        vid_id = entry.get("id", "")
        if not vid_id:
            continue
        # Build canonical TikTok URL
        webpage_url = entry.get("webpage_url") or f"https://www.tiktok.com/@{entry.get('uploader_id', 'unknown')}/video/{vid_id}"
        # Lấy thumbnail từ `thumbnail` (nếu có) hoặc phần tử đầu trong `thumbnails`
        thumbnail_url = entry.get("thumbnail")
        if not thumbnail_url:
            thumbs = entry.get("thumbnails") or []
            # Ưu tiên cover (preference >= 0) hoặc lấy phần tử đầu
            for t in thumbs:
                if t.get("preference", -99) >= 0:
                    thumbnail_url = t.get("url")
                    break
            if not thumbnail_url and thumbs:
                thumbnail_url = thumbs[0].get("url")

        videos.append({
            "video_url": webpage_url,
            "video_title": (entry.get("title") or "")[:300],
            "thumbnail_url": thumbnail_url,
            "author": entry.get("uploader") or entry.get("channel") or entry.get("uploader_id") or None,
            "view_count": entry.get("view_count"),
        })
    logger.info(f"[TikTok] Channel '{url}': {len(videos)} videos fetched")
    return videos


# ── Manual URL import ─────────────────────────────────────────────────────────

def get_video_metadata(url: str) -> dict:
    """Try to get title/thumbnail via yt-dlp. Falls back to URL-only."""
    cmd = ["yt-dlp", "--dump-json", "--no-warnings", "--skip-download", "--no-playlist", url]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            entry = json.loads(result.stdout.strip().splitlines()[0])
            return {
                "video_url": url,
                "video_title": (entry.get("title") or "")[:300],
                "thumbnail_url": entry.get("thumbnail"),
                "author": entry.get("uploader") or entry.get("channel") or None,
                "view_count": entry.get("view_count"),
            }
    except Exception:
        pass
    return {"video_url": url, "video_title": None, "thumbnail_url": None, "author": None, "view_count": None}


# ── DB helpers ────────────────────────────────────────────────────────────────

async def fetch_and_save(
    hashtag: str,
    platform: str = "instagram_reels",
    max_count: int = 30,
    browser: str = "chrome",
    filter_people: bool = True,
    cookies_file: str = "",
) -> dict:
    """
    Fetch trending videos và lưu entries mới vào DB.
    Returns {"saved": N, "total": N, "error": str|None}
    """
    import asyncio
    from database import SessionLocal
    from models.trending import TrendingVideo

    error_msg = None
    videos = []

    try:
        if platform == "instagram_reels":
            videos = await asyncio.to_thread(
                fetch_instagram_reels, hashtag, max_count, browser, filter_people
            )
        elif platform == "tiktok_channel":
            # browser ở đây là Instagram browser — không dùng cho TikTok (sẽ fail trong Docker)
            # cookies_file là TikTok-specific, pass qua bình thường
            videos = await asyncio.to_thread(fetch_tiktok_channel, hashtag, max_count, "", cookies_file)
        else:
            videos = await asyncio.to_thread(fetch_youtube_shorts, hashtag, max_count)
    except RuntimeError as e:
        error_msg = str(e)
        logger.warning(f"[TrendFetcher] {platform} failed: {e}")
        return {"saved": 0, "total": 0, "error": error_msg}

    if not videos:
        # Phân biệt lỗi thật (exception) vs fetch được 0 video (TikTok rate-limit, v.v.)
        if error_msg:
            return {"saved": 0, "total": 0, "error": error_msg}
        # Không có video nào từ nguồn — không báo lỗi, trả về 0 để frontend vẫn refetch DB
        logger.warning(f"[TrendFetcher] {platform} #{hashtag}: source returned 0 videos")
        return {"saved": 0, "total": 0, "error": None}

    db = SessionLocal()
    saved = 0
    try:
        for v in videos:
            exists = db.query(TrendingVideo).filter(
                TrendingVideo.video_url == v["video_url"]
            ).first()
            if not exists:
                db.add(TrendingVideo(platform=platform, hashtag=hashtag, **v))
                saved += 1
        db.commit()
    finally:
        db.close()

    logger.info(f"[TrendFetcher] {platform} #{hashtag}: saved {saved}/{len(videos)}")
    return {"saved": saved, "total": len(videos), "error": None}


async def fetch_all_active_hashtags(filter_people: bool = True):
    """Fetch tất cả hashtag đang active. Gọi bởi scheduler."""
    from database import SessionLocal
    from models.trending_hashtag import TrendingHashtag

    db = SessionLocal()
    try:
        hashtags = db.query(TrendingHashtag).filter(TrendingHashtag.is_active == True).all()
        if not hashtags:
            # Default fallback
            hashtags_data = [("nailart", "instagram_reels", "chrome")]
        else:
            hashtags_data = [(h.hashtag, h.platform, h.browser) for h in hashtags]
    finally:
        db.close()

    for hashtag, platform, browser in hashtags_data:
        result = await fetch_and_save(hashtag, platform, 30, browser, filter_people)
        if result["error"] and platform == "instagram_reels":
            logger.warning(f"[Scheduler] Instagram failed for #{hashtag}, trying YouTube Shorts")
            await fetch_and_save(hashtag, "youtube_shorts", 20, browser, False)
        elif result["error"] and platform == "tiktok_channel":
            logger.warning(f"[Scheduler] TikTok channel failed for {hashtag}: {result['error']}")


async def import_urls(urls: list[str], hashtag: str, platform: str = "instagram") -> int:
    """Import danh sách URLs thủ công vào inbox."""
    import asyncio
    from database import SessionLocal
    from models.trending import TrendingVideo

    db = SessionLocal()
    saved = 0
    try:
        for url in urls:
            url = url.strip()
            if not url:
                continue
            if db.query(TrendingVideo).filter(TrendingVideo.video_url == url).first():
                continue
            meta = await asyncio.to_thread(get_video_metadata, url)
            db.add(TrendingVideo(platform=platform, hashtag=hashtag, **meta))
            saved += 1
        db.commit()
    finally:
        db.close()

    return saved
