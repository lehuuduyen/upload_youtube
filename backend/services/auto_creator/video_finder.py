"""
Video Finder — tìm video YouTube trending theo chủ đề dùng yt-dlp (không cần API key).
"""
import json
import subprocess
from datetime import datetime, timezone


def _relative_time_from_timestamp(ts) -> str:
    """Unix timestamp → '3 giờ trước', '2 ngày trước', v.v."""
    if not ts:
        return ""
    try:
        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
    except Exception:
        return ""
    now = datetime.now(timezone.utc)
    diff = now - dt
    total_seconds = int(diff.total_seconds())

    if total_seconds < 60:
        return "Vừa xong"
    if total_seconds < 3600:
        minutes = total_seconds // 60
        return f"{minutes} phút trước"
    if total_seconds < 86400:
        hours = total_seconds // 3600
        return f"{hours} giờ trước"
    days = diff.days
    if days == 1:
        return "Hôm qua"
    if days < 7:
        return f"{days} ngày trước"
    if days < 14:
        return "1 tuần trước"
    if days < 30:
        return f"{days // 7} tuần trước"
    if days < 60:
        return "1 tháng trước"
    if days < 365:
        return f"{days // 30} tháng trước"
    return f"{days // 365} năm trước"


def _parse_upload_date(raw_date: str) -> str:
    """'20260416' → '16/04/2026'"""
    if not raw_date or len(raw_date) != 8:
        return ""
    try:
        return datetime.strptime(raw_date, "%Y%m%d").strftime("%d/%m/%Y")
    except ValueError:
        return raw_date


def search_youtube_videos(query: str, max_results: int = 10) -> list[dict]:
    """
    Dùng yt-dlp để tìm video YouTube theo từ khoá.
    Dùng URL search với sp=CAI%3D (sort by upload date — mới nhất trước).
    Trả về list video sắp xếp theo thời gian đăng (mới nhất → cũ nhất).
    """
    import urllib.parse
    # sp=CAI%3D = sort by upload date on YouTube search
    search_url = (
        "https://www.youtube.com/results?search_query="
        + urllib.parse.quote(query)
        + "&sp=CAI%3D"
    )
    cmd = [
        "yt-dlp",
        search_url,
        "--dump-json",
        "--no-download",
        "--playlist-end", str(max_results),
        "--no-warnings",
        "--extractor-args", "youtube:player_client=android,web",
        "--retries", "3",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        return []

    # Fallback: nếu URL search thất bại, thử lại với ytsearch
    if not result.stdout.strip():
        cmd_fallback = [
            "yt-dlp",
            f"ytsearch{max_results}:{query}",
            "--dump-json",
            "--no-download",
            "--no-playlist",
            "--no-warnings",
            "--extractor-args", "youtube:player_client=android,web",
            "--retries", "3",
        ]
        try:
            result = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=90)
        except subprocess.TimeoutExpired:
            return []

    videos = []
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        vid_id = data.get("id") or ""
        if not vid_id:
            continue

        # duration: seconds → mm:ss
        dur_sec = data.get("duration")
        dur_str = ""
        if dur_sec:
            m, s = divmod(int(dur_sec), 60)
            dur_str = f"{m}:{s:02d}" if m < 60 else f"{m//60}:{m%60:02d}:{s:02d}"

        # thumbnail
        thumbnails = data.get("thumbnails") or []
        thumb_url = thumbnails[-1].get("url", "") if thumbnails else ""
        if not thumb_url:
            thumb_url = data.get("thumbnail") or f"https://img.youtube.com/vi/{vid_id}/hqdefault.jpg"

        # time: prefer unix timestamp (precise) over upload_date (day-only)
        ts = data.get("timestamp") or data.get("release_timestamp")
        uploaded_ago = _relative_time_from_timestamp(ts)
        upload_date = _parse_upload_date(data.get("upload_date", ""))

        # fallback timestamp: derive from upload_date string YYYYMMDD
        if not ts and data.get("upload_date"):
            try:
                dt = datetime.strptime(data["upload_date"], "%Y%m%d").replace(tzinfo=timezone.utc)
                ts = dt.timestamp()
                if not uploaded_ago:
                    uploaded_ago = _relative_time_from_timestamp(ts)
            except Exception:
                pass

        videos.append({
            "id": vid_id,
            "title": data.get("title", ""),
            "url": f"https://www.youtube.com/watch?v={vid_id}",
            "thumbnail": thumb_url,
            "view_count": data.get("view_count") or 0,
            "like_count": data.get("like_count") or 0,
            "duration_sec": dur_sec or 0,
            "duration": dur_str,
            "uploader": data.get("uploader") or data.get("channel", ""),
            "upload_date": upload_date,
            "uploaded_ago": uploaded_ago,
            "_ts": float(ts) if ts else 0,
            "description": (data.get("description") or "")[:300],
        })

    # Sắp xếp theo thời gian đăng mới nhất trước
    return sorted(videos, key=lambda v: v.get("_ts") or 0, reverse=True)


def get_video_info(url: str) -> dict:
    """Lấy thông tin chi tiết của một video YouTube cụ thể."""
    cmd = [
        "yt-dlp",
        url,
        "--dump-json",
        "--no-download",
        "--no-playlist",
        "--quiet",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        data = json.loads(result.stdout.strip())
    except Exception as e:
        raise RuntimeError(f"Không lấy được thông tin video: {e}")

    vid_id = data.get("id", "")
    dur_sec = data.get("duration", 0)
    m, s = divmod(int(dur_sec or 0), 60)

    return {
        "id": vid_id,
        "title": data.get("title", ""),
        "url": url,
        "thumbnail": data.get("thumbnail", f"https://img.youtube.com/vi/{vid_id}/hqdefault.jpg"),
        "view_count": data.get("view_count") or 0,
        "duration_sec": dur_sec,
        "duration": f"{m}:{s:02d}",
        "uploader": data.get("uploader") or data.get("channel", ""),
        "description": (data.get("description") or "")[:500],
        "tags": data.get("tags") or [],
    }
