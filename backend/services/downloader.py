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


_YTDLP_BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "no_color": True,
    "extractor_args": {
        "youtube": {"player_client": ["android_vr", "web"]},
    },
}


def get_video_info(url: str) -> dict:
    """Extract video metadata without downloading."""
    opts = {
        **_YTDLP_BASE_OPTS,
        "skip_download": True,
        "format": "bestvideo+bestaudio/bestvideo*/best",
        "ignore_no_formats_error": True,
    }
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
        "format": _quality_to_format(quality),
        "outtmpl": output_template,
        "progress_hooks": [_progress_hook],
        "merge_output_format": "mp4",
        "extractor_args": {
            "youtube": {"player_client": ["android_vr", "web"]},
            "tiktok": {"webpage_download": True},
        },
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        # Handle merged output
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
