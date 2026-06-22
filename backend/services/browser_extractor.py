"""
Browser-based stream extractor (Playwright).

Dùng cho các site phim nhúng video qua JavaScript (m3u8/mp4) và/hoặc bị
Cloudflare chặn request thẳng. Mở headless Chromium, chờ trang load + bấm play,
rồi bắt URL stream từ network traffic.

Chạy trên server có IP truy cập được site (vd: server Việt Nam cho site phim VN).
sync_playwright được chạy trong thread riêng để an toàn khi gọi từ event loop async.
"""
import os
import re
import time
import concurrent.futures
from typing import Optional


# Pattern nhận diện URL stream video
_STREAM_PATTERNS = (".m3u8", ".mp4", "/master", "/playlist", ".mpd")

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Init script ẩn dấu hiệu automation (giảm khả năng bị Cloudflare flag)
_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['vi-VN', 'vi', 'en-US', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = window.chrome || { runtime: {} };
"""


def _parse_netscape_cookies(path: str) -> list[dict]:
    """Parse cookies.txt (Netscape format) → list dict cho Playwright add_cookies."""
    cookies = []
    if not path or not os.path.exists(path):
        return cookies
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                # yt-dlp dùng "#HttpOnly_" prefix cho httpOnly cookies
                if line.startswith("#HttpOnly_"):
                    line = line[len("#HttpOnly_"):]
                else:
                    continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            domain, _flag, cpath, secure, expiry, name, value = parts[:7]
            cookie = {
                "name": name,
                "value": value,
                "domain": domain,
                "path": cpath or "/",
                "secure": secure.upper() == "TRUE",
            }
            try:
                exp = int(expiry)
                if exp > 0:
                    cookie["expires"] = exp
            except ValueError:
                pass
            cookies.append(cookie)
    return cookies


def _score_stream(url: str) -> int:
    """Ưu tiên: master m3u8 > m3u8 > mpd > mp4. Số càng cao càng ưu tiên."""
    u = url.lower()
    if "master" in u and ".m3u8" in u:
        return 5
    if ".m3u8" in u:
        return 4
    if ".mpd" in u:
        return 3
    if ".mp4" in u:
        return 2
    return 1


def _extract_blocking(
    page_url: str,
    cookies_file: Optional[str],
    timeout_ms: int,
    channel: Optional[str],
    headless: bool,
) -> dict:
    from playwright.sync_api import sync_playwright

    found: list[str] = []
    captured_headers: dict = {}

    def _on_request(req):
        u = req.url
        if any(p in u.lower() for p in _STREAM_PATTERNS):
            found.append(u)
            # Lưu headers của request stream đầu tiên để dùng khi tải lại
            if not captured_headers:
                try:
                    h = req.headers
                    captured_headers["referer"] = h.get("referer", "")
                    captured_headers["user_agent"] = h.get("user-agent", "")
                except Exception:
                    pass

    launch_kwargs = {
        "headless": headless,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-infobars",
        ],
    }
    if channel:
        launch_kwargs["channel"] = channel

    title = ""
    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kwargs)
        ctx = browser.new_context(
            user_agent=_DEFAULT_UA,
            viewport={"width": 1366, "height": 768},
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
            ignore_https_errors=True,
        )
        ctx.add_init_script(_STEALTH_JS)

        cookies = _parse_netscape_cookies(cookies_file) if cookies_file else []
        if cookies:
            try:
                ctx.add_cookies(cookies)
            except Exception:
                pass

        page = ctx.new_page()
        page.on("request", _on_request)
        # Bắt cả stream nằm trong iframe
        page.on("frameattached", lambda fr: None)

        deadline = time.time() + timeout_ms / 1000.0
        try:
            page.goto(page_url, wait_until="domcontentloaded", timeout=timeout_ms)
        except Exception:
            pass

        try:
            title = page.title()
        except Exception:
            title = ""

        # Thử bấm các nút play phổ biến để kích hoạt load stream
        play_selectors = [
            ".jw-icon-display", ".vjs-big-play-button", ".play-button",
            "button[aria-label*='play' i]", ".ytp-large-play-button",
            "[class*='play']", "video",
        ]
        for sel in play_selectors:
            if found:
                break
            try:
                el = page.query_selector(sel)
                if el:
                    el.click(timeout=2000)
                    page.wait_for_timeout(1500)
            except Exception:
                continue

        # Chờ tới khi bắt được stream hoặc hết giờ
        while not found and time.time() < deadline:
            page.wait_for_timeout(1000)

        # Cho thêm 1.5s để bắt được master playlist (thường load ngay sau)
        if found:
            page.wait_for_timeout(1500)

        try:
            browser.close()
        except Exception:
            pass

    if not found:
        raise RuntimeError(
            f"Không bắt được link video từ trang (title: {title!r}). "
            "Có thể bị Cloudflare chặn — thử cung cấp cookies.txt, "
            "hoặc IP server không truy cập được site này."
        )

    # Chọn stream tốt nhất, ưu tiên master m3u8
    best = sorted(dict.fromkeys(found), key=_score_stream, reverse=True)[0]
    referer = _clean_referer(captured_headers.get("referer"), page_url, best)
    return {
        "stream_url": best,
        "referer": referer,
        "user_agent": captured_headers.get("user_agent") or _DEFAULT_UA,
        "title": title,
        "page_url": page_url,
        "all_streams": list(dict.fromkeys(found)),
    }


def _clean_referer(captured: Optional[str], page_url: str, stream_url: str) -> str:
    """Chọn referer hợp lệ (http/https, không ký tự lạ). Fallback: page_url → origin stream."""
    from urllib.parse import urlparse

    for cand in (captured, page_url):
        if cand and cand.startswith(("http://", "https://")) and not re.search(r"\s", cand):
            return cand
    # Fallback: origin của stream URL
    try:
        p = urlparse(stream_url)
        if p.scheme and p.netloc:
            return f"{p.scheme}://{p.netloc}/"
    except Exception:
        pass
    return ""


def extract_stream(
    page_url: str,
    cookies_file: Optional[str] = None,
    timeout_ms: int = 45000,
) -> dict:
    """
    Mở browser, bắt URL stream (m3u8/mp4) từ trang phim.

    Trả về dict: {stream_url, referer, user_agent, title, page_url, all_streams}.
    Raise RuntimeError nếu không bắt được.

    Chạy sync_playwright trong thread riêng → an toàn khi gọi từ async event loop.
    """
    from config import settings

    channel = getattr(settings, "BROWSER_CHANNEL", "") or None
    headless = getattr(settings, "BROWSER_HEADLESS", True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(
            _extract_blocking, page_url, cookies_file, timeout_ms, channel, headless
        )
        return future.result(timeout=timeout_ms / 1000.0 + 30)
