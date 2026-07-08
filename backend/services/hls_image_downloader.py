"""
Tải HLS có segment bị "bọc ảnh giả" (image-wrapped TS).

Một số site phim (vd phimbom.us) chống tải bằng cách bọc mỗi segment MPEG-TS
trong một header ảnh giả (PNG/JPEG 1x1) và serve qua CDN ảnh với Content-Type
image/*. Player của họ cắt bỏ header rồi phát phần TS.

yt-dlp/ffmpeg tải về sẽ ra file rác (ffprobe đọc nhầm là "png 1x1"). Module này:
  1. Tải m3u8, lấy danh sách segment
  2. Tải từng segment, cắt bỏ header ảnh (tìm điểm bắt đầu MPEG-TS)
  3. Ghép phần TS sạch lại
  4. Remux ra mp4 (H.264/AAC giữ nguyên, +faststart)
"""
import os
import re
import shutil
import tempfile
import subprocess
import concurrent.futures
from typing import Optional, Callable
from urllib.parse import urljoin

import curl_cffi.requests as cffi_req

from config import settings


_TS_PACKET = 188
_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _ts_offset(data: bytes) -> Optional[int]:
    """
    Tìm offset bắt đầu của MPEG-TS trong segment (sau header ảnh giả).
    TS chuẩn: byte 0x47 lặp lại đều mỗi 188 byte.
    Trả về offset, hoặc None nếu segment không chứa TS (ảnh thật → bỏ qua).
    """
    if len(data) < _TS_PACKET * 8:
        return None
    # Đã là TS thuần?
    if data[0] == 0x47 and all(data[i * _TS_PACKET] == 0x47 for i in range(8)):
        return 0
    # Segment bọc ảnh: quét header (giới hạn 8KB) tìm điểm TS bắt đầu
    limit = min(len(data) - _TS_PACKET * 8, 8192)
    for off in range(limit):
        if all(data[off + i * _TS_PACKET] == 0x47 for i in range(8)):
            return off
    return None


def looks_image_wrapped(first_segment: bytes) -> bool:
    """Segment có bị bọc ảnh giả không (header ảnh nhưng chứa TS bên trong)?"""
    if not first_segment:
        return False
    is_image = (
        first_segment[:8].hex().startswith("89504e47")  # PNG
        or first_segment[:3] == b"\xff\xd8\xff"          # JPEG
        or first_segment[:4] == b"GIF8"                   # GIF
    )
    if not is_image:
        return False
    off = _ts_offset(first_segment)
    return off is not None and off > 0


def fetch_segments_list(m3u8_url: str, headers: dict) -> list[str]:
    """Tải m3u8, trả về danh sách URL segment tuyệt đối (xử lý cả master playlist)."""
    text = cffi_req.get(m3u8_url, headers=headers, impersonate="chrome").text
    if "#EXTM3U" not in text:
        raise RuntimeError("Không phải m3u8 hợp lệ")

    lines = [l.strip() for l in text.splitlines()]
    segs = [urljoin(m3u8_url, l) for l in lines if l and not l.startswith("#")]

    # Nếu là master playlist (các dòng trỏ tới .m3u8 khác) → lấy variant đầu
    if segs and all(".m3u8" in s.lower() for s in segs):
        return fetch_segments_list(segs[0], headers)
    return segs


def download_image_wrapped_hls(
    m3u8_url: str,
    output_path: str,
    referer: str = "",
    user_agent: str = "",
    cookies_file: Optional[str] = None,
    max_workers: int = 8,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> str:
    """
    Tải HLS image-wrapped → mp4. Trả về đường dẫn file mp4.
    """
    headers = {
        "Referer": referer or "",
        "User-Agent": user_agent or _DEFAULT_UA,
    }

    cookies = None
    if cookies_file and os.path.exists(cookies_file):
        cookies = _load_cookies_dict(cookies_file)

    if progress_callback:
        progress_callback(0, "Đọc danh sách segment...")
    segs = fetch_segments_list(m3u8_url, headers)
    total = len(segs)
    if total == 0:
        raise RuntimeError("m3u8 không có segment")

    tmpdir = tempfile.mkdtemp(prefix="hls_iw_")
    done = {"n": 0, "skipped": 0}

    def _dl_one(idx_url):
        idx, url = idx_url
        try:
            data = cffi_req.get(
                url, headers=headers, cookies=cookies, impersonate="chrome", timeout=60
            ).content
            off = _ts_offset(data)
            seg_path = os.path.join(tmpdir, f"seg_{idx:06d}.ts")
            if off is None:
                done["skipped"] += 1
                return None  # segment không chứa TS (ảnh quảng cáo thật) → bỏ
            with open(seg_path, "wb") as f:
                f.write(data[off:])
            return seg_path
        except Exception:
            return None
        finally:
            done["n"] += 1
            if progress_callback and done["n"] % 5 == 0:
                pct = done["n"] / total * 100
                progress_callback(pct, f"Tải segment: {done['n']}/{total} ({pct:.0f}%)")

    try:
        # Tải song song nhưng giữ thứ tự bằng index
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            list(ex.map(_dl_one, enumerate(segs)))

        # Ghép TS sạch theo đúng thứ tự
        if progress_callback:
            progress_callback(99, "Ghép & remux video...")
        merged_ts = os.path.join(tmpdir, "merged.ts")
        with open(merged_ts, "wb") as out:
            for idx in range(total):
                seg_path = os.path.join(tmpdir, f"seg_{idx:06d}.ts")
                if os.path.exists(seg_path):
                    with open(seg_path, "rb") as sf:
                        shutil.copyfileobj(sf, out)

        if os.path.getsize(merged_ts) == 0:
            raise RuntimeError("Không tải được segment video nào")

        # Remux TS → mp4 (giữ nguyên codec, +faststart cho YouTube)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cmd = [
            settings.FFMPEG_PATH, "-y",
            "-i", merged_ts,
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
            "-movflags", "+faststart",
            output_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0 or not os.path.exists(output_path):
            raise RuntimeError(f"ffmpeg remux lỗi: {proc.stderr[-500:]}")

        return output_path
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _load_cookies_dict(path: str) -> dict:
    """Parse cookies.txt (Netscape) → dict {name: value} cho curl_cffi."""
    out = {}
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    out[parts[5]] = parts[6]
    except Exception:
        pass
    return out
