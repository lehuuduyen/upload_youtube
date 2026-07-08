"""
yt-dlp based downloader for video and music.
Supports YouTube, TikTok, SoundCloud, and direct links.
"""
import os
import re
import asyncio
from typing import Optional, Callable

import yt_dlp


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    return name[:100].strip()


def _make_base_opts() -> dict:
    from yt_dlp.networking.impersonate import ImpersonateTarget
    return {
        "quiet": True,
        "no_warnings": True,
        "no_color": True,
        "extractor_args": {
            "youtube": {"player_client": ["android_vr", "web"]},
            "generic": {"impersonate": ["chrome"]},
        },
        "impersonate": ImpersonateTarget("chrome"),
    }

_YTDLP_BASE_OPTS = _make_base_opts()


def _should_browser_fallback(err: Exception) -> bool:
    """Xác định lỗi yt-dlp có nên thử lại bằng browser extractor không."""
    from config import settings
    if not getattr(settings, "BROWSER_EXTRACT_ENABLED", True):
        return False
    msg = str(err).lower()
    triggers = (
        "unsupported url",
        "403",
        "forbidden",
        "cloudflare",
        "unable to download webpage",
        "unable to extract",
        "no video formats",
        "no suitable",
    )
    return any(t in msg for t in triggers)


def _cookies_file_or_none() -> Optional[str]:
    from config import settings
    f = settings.COOKIES_FILE
    return f if f and os.path.exists(f) else None


def _get_cookie_opts(url: str) -> dict:
    """Trả về cookie opts cho yt-dlp: ưu tiên Facebook cookies, fallback sang cookies.txt chung."""
    from config import settings

    # Facebook: dùng cookie riêng
    try:
        from services.auto_creator.facebook_finder import is_facebook_url
        if is_facebook_url(url):
            return _facebook_cookie_opts(url)
    except Exception:
        pass

    # General cookies.txt — bypass Cloudflare, site cần login
    f = settings.COOKIES_FILE
    if f and os.path.exists(f):
        return {"cookiefile": f}
    return {}


def _facebook_cookie_opts(url: str) -> dict:
    """Trả về yt-dlp opts cookies khi URL là Facebook (cần đăng nhập).

    Dùng chung config với facebook_finder: FACEBOOK_COOKIES_FILE hoặc
    FACEBOOK_COOKIES_FROM_BROWSER trong .env.
    """
    from services.auto_creator.facebook_finder import is_facebook_url
    from config import settings

    if not is_facebook_url(url):
        return {}
    if settings.FACEBOOK_COOKIES_FROM_BROWSER:
        return {"cookiesfrombrowser": (settings.FACEBOOK_COOKIES_FROM_BROWSER,)}
    f = settings.FACEBOOK_COOKIES_FILE
    if f and os.path.exists(f):
        return {"cookiefile": f}
    return {}


def get_video_info(url: str) -> dict:
    """Extract video metadata without downloading.

    Thử yt-dlp trước; nếu fail (site nhúng JS / Cloudflare) thì fallback sang
    browser extractor để bắt link stream rồi probe lại.
    """
    opts = {
        **_YTDLP_BASE_OPTS,
        **_get_cookie_opts(url),
        "skip_download": True,
        "format": "bestvideo+bestaudio/bestvideo*/best",
        "ignore_no_formats_error": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return {
            "id": info.get("id"),
            "title": info.get("title"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader"),
            "thumbnail": info.get("thumbnail"),
            "formats": [
                {
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "height": f.get("height"),
                    "filesize": f.get("filesize"),
                }
                for f in info.get("formats", [])
                if f.get("height")
            ],
        }
    except Exception as e:
        if not _should_browser_fallback(e):
            raise
        return _get_video_info_via_browser(url)


def _get_video_info_via_browser(url: str) -> dict:
    """Fallback: dùng browser bắt stream rồi probe metadata bằng yt-dlp."""
    from services.browser_extractor import extract_stream
    from config import settings

    res = extract_stream(
        url,
        cookies_file=_cookies_file_or_none(),
        timeout_ms=getattr(settings, "BROWSER_TIMEOUT_MS", 45000),
    )
    stream_url = res["stream_url"]
    headers = {"Referer": res["referer"], "User-Agent": res["user_agent"]}

    # Probe stream m3u8/mp4 — opts sạch, plain headers (không impersonate/curl_cffi)
    probe_opts = {
        "quiet": True,
        "no_warnings": True,
        "no_color": True,
        "skip_download": True,
        "http_headers": headers,
        "ignore_no_formats_error": True,
    }
    try:
        with yt_dlp.YoutubeDL(probe_opts) as ydl:
            info = ydl.extract_info(stream_url, download=False)
        formats = [
            {
                "format_id": f.get("format_id"),
                "ext": f.get("ext"),
                "height": f.get("height"),
                "filesize": f.get("filesize"),
            }
            for f in info.get("formats", [])
            if f.get("height")
        ]
        duration = info.get("duration")
    except Exception:
        formats, duration = [], None

    return {
        "id": None,
        "title": res.get("title") or "Video",
        "duration": duration,
        "uploader": res.get("page_url"),
        "thumbnail": None,
        "formats": formats,
        "_via_browser": True,
        "_stream_url": stream_url,
    }


def _quality_to_format(quality: str) -> str:
    # Each entry: try bestvideo+bestaudio first, fallback to combined format, then any best
    mapping = {
        "best":  "bestvideo+bestaudio/bestvideo*+bestaudio/best",
        "4k":    "bestvideo[height<=2160]+bestaudio/bestvideo[height<=2160]/best[height<=2160]/best",
        "1080p": "bestvideo[height<=1080]+bestaudio/bestvideo[height<=1080]/best[height<=1080]/best",
        "720p":  "bestvideo[height<=720]+bestaudio/bestvideo[height<=720]/best[height<=720]/best",
        "480p":  "bestvideo[height<=480]+bestaudio/bestvideo[height<=480]/best[height<=480]/best",
    }
    return mapping.get(quality, mapping["1080p"])


def download_video(
    url: str,
    output_dir: str,
    quality: str = "1080p",
    job_id: Optional[int] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> str:
    """
    Download a video. Returns the output file path.
    """
    os.makedirs(output_dir, exist_ok=True)
    prefix = f"job_{job_id}_" if job_id else ""
    output_template = os.path.join(output_dir, f"{prefix}%(id)s.%(ext)s")

    def _progress_hook(d):
        if progress_callback and d["status"] == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 1)
            pct = (downloaded / total * 100) if total else 0
            speed = d.get("speed", 0)
            speed_str = f"{speed/1024/1024:.1f} MB/s" if speed else "..."
            progress_callback(pct, f"Downloading: {pct:.1f}% @ {speed_str}")

    opts = {
        **_YTDLP_BASE_OPTS,
        **_get_cookie_opts(url),
        "format": _quality_to_format(quality),
        "outtmpl": output_template,
        "progress_hooks": [_progress_hook],
        "merge_output_format": "mp4",
        "extractor_args": {
            "youtube": {"player_client": ["android_vr", "web"]},
            "tiktok": {"webpage_download": True},
        },
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            # Handle merged output
            if not os.path.exists(filename):
                filename = filename.rsplit(".", 1)[0] + ".mp4"
            return filename
    except Exception as e:
        if not _should_browser_fallback(e):
            raise
        return _download_video_via_browser(
            url, output_dir, quality, job_id, progress_callback, _progress_hook
        )


def _try_image_wrapped_download(
    stream_url: str,
    headers: dict,
    cookies_file: Optional[str],
    output_dir: str,
    out_name: str,
    progress_callback,
) -> Optional[str]:
    """
    Kiểm tra m3u8 có segment bọc ảnh giả không; nếu có thì tải bằng
    hls_image_downloader. Trả về path mp4, hoặc None nếu không phải kiểu này.
    """
    try:
        import curl_cffi.requests as cffi_req
        from services.hls_image_downloader import (
            fetch_segments_list, looks_image_wrapped, download_image_wrapped_hls,
        )

        segs = fetch_segments_list(stream_url, headers)
        if not segs:
            return None
        first = cffi_req.get(
            segs[0], headers=headers, impersonate="chrome", timeout=60
        ).content
        if not looks_image_wrapped(first):
            return None

        if progress_callback:
            progress_callback(0, "Phát hiện segment bọc ảnh — tải kiểu chuyên dụng...")
        output_path = os.path.join(output_dir, out_name)
        return download_image_wrapped_hls(
            stream_url,
            output_path,
            referer=headers.get("Referer", ""),
            user_agent=headers.get("User-Agent", ""),
            cookies_file=cookies_file,
            progress_callback=progress_callback,
        )
    except Exception:
        return None  # lỗi → để yt-dlp thử cách thường


def _download_video_via_browser(
    url: str,
    output_dir: str,
    quality: str,
    job_id: Optional[int],
    progress_callback,
    progress_hook,
) -> str:
    """Fallback: bắt link stream bằng browser rồi tải m3u8/mp4 qua yt-dlp + ffmpeg."""
    from services.browser_extractor import extract_stream
    from config import settings

    if progress_callback:
        progress_callback(0, "Mở browser bắt link video...")

    cookies_file = _cookies_file_or_none()
    res = extract_stream(
        url,
        cookies_file=cookies_file,
        timeout_ms=getattr(settings, "BROWSER_TIMEOUT_MS", 45000),
    )
    stream_url = res["stream_url"]
    headers = {"Referer": res["referer"], "User-Agent": res["user_agent"]}

    # Cảnh báo sớm nếu phát hiện DRM (Widevine/PlayReady) — không tải được
    enc = res.get("encryption")
    if enc == "drm":
        raise ValueError(
            "Nguồn dùng DRM (Widevine/PlayReady) — không thể tải bản xem được. "
            "Hãy dùng nguồn khác không mã hoá DRM."
        )

    prefix = f"job_{job_id}_" if job_id else ""
    out_id = job_id or "video"

    # Phát hiện segment bị bọc ảnh giả (image-wrapped TS) — vd phimbom.us
    if ".m3u8" in stream_url.lower():
        wrapped_out = _try_image_wrapped_download(
            stream_url, headers, cookies_file, output_dir,
            f"{prefix}{out_id}.mp4", progress_callback,
        )
        if wrapped_out:
            return wrapped_out

    output_template = os.path.join(output_dir, f"{prefix}{out_id}.%(ext)s")

    # opts sạch cho m3u8 trực tiếp — plain headers, không impersonate/curl_cffi
    opts = {
        "quiet": True,
        "no_warnings": True,
        "no_color": True,
        "format": _quality_to_format(quality),
        "outtmpl": output_template,
        "progress_hooks": [progress_hook],
        "merge_output_format": "mp4",
        "http_headers": headers,
        "hls_use_mpegts": False,
    }
    # Truyền cookies để yt-dlp lấy được AES-128 key (key URI thường cần session/cookies)
    if cookies_file:
        opts["cookiefile"] = cookies_file

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(stream_url, download=True)
        filename = ydl.prepare_filename(info)
        if not os.path.exists(filename):
            filename = filename.rsplit(".", 1)[0] + ".mp4"
        return filename


def download_music(
    url: str,
    output_dir: str,
    job_id: Optional[int] = None,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> str:
    """
    Download audio as MP3. Returns the output file path.
    Optionally trim to [start_time, end_time] in seconds.
    """
    os.makedirs(output_dir, exist_ok=True)
    prefix = f"job_{job_id}_music_" if job_id else "music_"
    output_template = os.path.join(output_dir, f"{prefix}%(id)s.%(ext)s")

    def _progress_hook(d):
        if progress_callback and d["status"] == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 1)
            pct = (downloaded / total * 100) if total else 0
            progress_callback(pct, f"Downloading music: {pct:.1f}%")

    postprocessors = [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }
    ]

    # Add trim if requested
    if start_time is not None or end_time is not None:
        section = {}
        if start_time is not None:
            section["start_time"] = start_time
        if end_time is not None:
            section["end_time"] = end_time
        postprocessors.append({"key": "FFmpegMetadata"})

    opts = {
        **_YTDLP_BASE_OPTS,
        **_get_cookie_opts(url),
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "progress_hooks": [_progress_hook],
        "postprocessors": postprocessors,
    }

    if start_time is not None or end_time is not None:
        opts["download_ranges"] = yt_dlp.utils.download_range_func(
            None,
            [(start_time or 0, end_time or float("inf"))],
        )
        opts["force_keyframes_at_cuts"] = True

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        # yt-dlp converts to mp3
        filename = ydl.prepare_filename(info)
        mp3_path = filename.rsplit(".", 1)[0] + ".mp3"
        return mp3_path


async def download_video_async(
    url: str,
    output_dir: str,
    quality: str = "1080p",
    job_id: Optional[int] = None,
    progress_callback=None,
) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: download_video(url, output_dir, quality, job_id, progress_callback),
    )


async def download_music_async(
    url: str,
    output_dir: str,
    job_id: Optional[int] = None,
    start_time=None,
    end_time=None,
    progress_callback=None,
) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: download_music(url, output_dir, job_id, start_time, end_time, progress_callback),
    )
