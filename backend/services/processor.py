"""
FFmpeg-based video processing service.
Handles audio mixing, format conversion, cropping, and more.
"""
import os
import json
import asyncio
import subprocess
from typing import Optional, Callable

from config import settings

# Color/sharpness enhancement applied to every encode pass
_COLOR_VF = "eq=contrast=1.05:saturation=1.35:brightness=0.02,unsharp=5:5:1.2:5:5:0.4"


def run_ffmpeg(args: list[str], progress_callback: Optional[Callable] = None) -> str:
    """Run an ffmpeg command. Returns stderr output. Raises on error.

    FFmpeg writes progress using \\r (not \\n), so we read char-by-char
    to handle both line endings correctly.
    """
    cmd = [settings.FFMPEG_PATH, "-y"] + args
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    stderr_lines = []
    duration_sec = None
    buf = ""

    while True:
        char = process.stderr.read(1)
        if not char:
            break
        if char in ("\r", "\n"):
            line = buf.strip()
            buf = ""
            if not line:
                continue
            stderr_lines.append(line)

            # Parse duration once
            if "Duration:" in line and duration_sec is None:
                try:
                    dur_str = line.split("Duration:")[1].split(",")[0].strip()
                    h, m, s = dur_str.split(":")
                    duration_sec = int(h) * 3600 + int(m) * 60 + float(s)
                except Exception:
                    pass

            # Parse progress
            if progress_callback and duration_sec and "time=" in line:
                try:
                    time_str = line.split("time=")[1].split(" ")[0].strip()
                    h, m, s = time_str.split(":")
                    current_sec = int(h) * 3600 + int(m) * 60 + float(s)
                    pct = min(99, current_sec / duration_sec * 100)
                    progress_callback(pct, f"Processing: {pct:.1f}%")
                except Exception:
                    pass
        else:
            buf += char

    process.wait()
    if process.returncode != 0:
        raise RuntimeError("FFmpeg error:\n" + "\n".join(stderr_lines[-20:]))
    return "\n".join(stderr_lines)


def get_media_info(file_path: str) -> dict:
    """Get media info using ffprobe."""
    cmd = [
        settings.FFPROBE_PATH,
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        file_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe error: {result.stderr}")
    return json.loads(result.stdout)


def get_video_duration(file_path: str) -> float:
    info = get_media_info(file_path)
    return float(info.get("format", {}).get("duration", 0))


def mute_range_audio(
    video_path: str,
    output_path: str,
    mute_start: float,
    mute_end: float,
    progress_callback: Optional[Callable] = None,
) -> str:
    """
    Tắt tiếng gốc trong khoảng [mute_start, mute_end] giây.
    Không cần nhạc nền — chỉ áp dụng volume filter lên audio gốc.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    af = f"volume=0:eval=frame:enable='between(t,{mute_start:.3f},{mute_end:.3f})'"
    args = [
        "-i", video_path,
        "-af", af,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        output_path,
    ]
    run_ffmpeg(args, progress_callback)
    return output_path


def merge_audio_video(
    video_path: str,
    music_path: str,
    output_path: str,
    mute_original: bool = True,
    mute_range_start: Optional[float] = None,
    mute_range_end: Optional[float] = None,
    original_volume: float = 0.2,
    music_volume: float = 0.8,
    loop_music: bool = True,
    fade_in: float = 0.0,
    fade_out: float = 2.0,
    progress_callback: Optional[Callable] = None,
) -> str:
    """
    Merge music into video with volume controls and optional loop/fade.
    Returns output_path.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    video_duration = get_video_duration(video_path)

    inputs = ["-i", video_path, "-i", music_path]
    if loop_music:
        inputs = ["-i", video_path, "-stream_loop", "-1", "-i", music_path]

    # Partial mute expression — áp dụng lên audio gốc nếu có range
    has_range = mute_range_start is not None and mute_range_end is not None
    range_mute = (
        f",volume=0:eval=frame:enable='between(t,{mute_range_start:.3f},{mute_range_end:.3f})'"
        if has_range else ""
    )

    # Build audio filter
    if mute_original:
        # Chỉ dùng nhạc nền, bỏ hoàn toàn audio gốc
        music_filter = f"[1:a]volume={music_volume}"
        if fade_in > 0:
            music_filter += f",afade=t=in:st=0:d={fade_in}"
        if fade_out > 0:
            fade_start = max(0, video_duration - fade_out)
            music_filter += f",afade=t=out:st={fade_start:.2f}:d={fade_out}"
        music_filter += "[aout]"
        filter_complex = music_filter
        audio_map = "[aout]"
    else:
        # Mix original + music; áp dụng range mute vào audio gốc nếu có
        orig_filter = f"[0:a]volume={original_volume}{range_mute}[orig]"
        music_filter = f"[1:a]volume={music_volume}"
        if fade_in > 0:
            music_filter += f",afade=t=in:st=0:d={fade_in}"
        if fade_out > 0:
            fade_start = max(0, video_duration - fade_out)
            music_filter += f",afade=t=out:st={fade_start:.2f}:d={fade_out}"
        music_filter += "[music]"
        mix = "[orig][music]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        filter_complex = f"{orig_filter};{music_filter};{mix}"
        audio_map = "[aout]"

    args = (
        inputs
        + [
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", audio_map,
            "-vf", _COLOR_VF,
            "-t", str(video_duration),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            output_path,
        ]
    )

    run_ffmpeg(args, progress_callback)
    return output_path


def convert_aspect_ratio(
    input_path: str,
    output_path: str,
    target_ratio: str = "9:16",
    width: Optional[int] = None,
    height: Optional[int] = None,
    progress_callback: Optional[Callable] = None,
) -> str:
    """
    Crop/resize video to target aspect ratio.
    Common: '16:9' (landscape), '9:16' (portrait/Shorts), '1:1' (square)
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    info = get_media_info(input_path)
    video_stream = next(
        (s for s in info.get("streams", []) if s["codec_type"] == "video"), None
    )
    if not video_stream:
        raise ValueError("No video stream found")

    src_w = int(video_stream["width"])
    src_h = int(video_stream["height"])

    ratio_map = {
        "16:9": (16, 9),
        "9:16": (9, 16),
        "1:1": (1, 1),
        "4:3": (4, 3),
        "3:4": (3, 4),
    }

    if target_ratio in ratio_map:
        rw, rh = ratio_map[target_ratio]
    else:
        parts = target_ratio.split(":")
        rw, rh = int(parts[0]), int(parts[1])

    # Calculate crop dimensions
    target_aspect = rw / rh
    src_aspect = src_w / src_h

    if src_aspect > target_aspect:
        # Source is wider — crop sides
        crop_h = src_h
        crop_w = int(crop_h * target_aspect)
    else:
        # Source is taller — crop top/bottom
        crop_w = src_w
        crop_h = int(crop_w / target_aspect)

    x = (src_w - crop_w) // 2
    y = (src_h - crop_h) // 2

    # Target output size
    out_w = width or crop_w
    out_h = height or crop_h
    # Ensure even dimensions
    out_w = out_w if out_w % 2 == 0 else out_w - 1
    out_h = out_h if out_h % 2 == 0 else out_h - 1

    vf = f"crop={crop_w}:{crop_h}:{x}:{y},scale={out_w}:{out_h}:flags=lanczos,{_COLOR_VF}"

    args = [
        "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-c:a", "copy",
        output_path,
    ]
    run_ffmpeg(args, progress_callback)
    return output_path


def extract_thumbnail(
    video_path: str,
    output_path: str,
    time_offset: float = 5.0,
) -> str:
    """Extract a frame from the video as thumbnail."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    duration = get_video_duration(video_path)
    t = min(time_offset, duration * 0.1)
    args = [
        "-ss", str(t),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        output_path,
    ]
    run_ffmpeg(args)
    return output_path


async def merge_audio_video_async(
    video_path: str,
    music_path: str,
    output_path: str,
    **kwargs,
) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: merge_audio_video(video_path, music_path, output_path, **kwargs),
    )


async def convert_aspect_ratio_async(
    input_path: str,
    output_path: str,
    target_ratio: str = "9:16",
    **kwargs,
) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: convert_aspect_ratio(input_path, output_path, target_ratio, **kwargs),
    )
