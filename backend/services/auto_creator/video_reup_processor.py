"""
Video Reup Processor — tải video và xử lý nhẹ (watermark / outro / nhạc nền).

Nguyên tắc:
  - Giữ NGUYÊN nội dung video gốc — không cắt, không thay đổi hình ảnh
  - Chỉ cho phép: overlay watermark text/logo, ghép clip outro, trộn nhạc nền
  - Khi không có overlay → dùng stream copy (nhanh, không mất chất lượng)
  - Khi có overlay → re-encode video, copy audio (giữ âm thanh gốc nguyên vẹn)
"""
import os
import subprocess

_COLOR_VF = "eq=contrast=1.05:saturation=1.35:brightness=0.02,unsharp=5:5:1.2:5:5:0.4"

# ── Helpers ──────────────────────────────────────────────────────────────────

def _find_font() -> str:
    for p in [
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]:
        if os.path.exists(p):
            return p
    return ""


def _esc(text: str) -> str:
    """Escape cho FFmpeg drawtext — bỏ emoji, thoát ký tự đặc biệt."""
    text = "".join(c for c in text if ord(c) <= 0xFFFF)
    return (
        text
        .replace("\\", "\\\\")
        .replace("'", "\u2019")
        .replace(":", "\\:")
        .replace("%", "\\%")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("&", "and")
        .replace("!", "")
    )


def _run(cmd: list[str], timeout: int = 600) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        stderr = result.stderr
        snippet = stderr[:2000] + ("\n...\n" + stderr[-500:] if len(stderr) > 2500 else "")
        raise RuntimeError(snippet)


def _probe_duration(path: str) -> float:
    import json
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
        capture_output=True, text=True,
    )
    return float(json.loads(r.stdout)["format"]["duration"])


# ── yt-dlp base flags ─────────────────────────────────────────────────────────

def _yt_dlp_base_args() -> list[str]:
    """Android+web client: không cần JS runtime, ít bị 429 hơn web player."""
    return [
        "--extractor-args", "youtube:player_client=android,web",
        "--retries", "5",
        "--fragment-retries", "5",
        "--retry-sleep", "exp=1:30",
    ]


# ── Download ─────────────────────────────────────────────────────────────────

def download_video(
    url: str,
    output_path: str,
    quality: str = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
) -> str:
    """Tải video YouTube bằng yt-dlp, trả về đường dẫn file thực tế."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    cmd = (
        ["yt-dlp"]
        + _yt_dlp_base_args()
        + [
            "--format", quality,
            "--merge-output-format", "mp4",
            "--output", output_path,
            "--no-playlist",
            "--no-warnings",
            url,
        ]
    )
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp download failed:\n{result.stderr[-1500:]}")

    for candidate in [output_path, output_path + ".mp4"]:
        if os.path.exists(candidate):
            return candidate
    base = os.path.splitext(output_path)[0]
    for ext in (".mp4", ".mkv", ".webm", ".mov"):
        if os.path.exists(base + ext):
            return base + ext
    raise RuntimeError(f"Downloaded file not found at {output_path}")


# ── Processing ────────────────────────────────────────────────────────────────

def process_reup(
    input_path: str,
    output_path: str,
    # Watermark text
    watermark_text: str = "",          # VD: "@KênhCủaTôi" — góc trên trái
    watermark_bottom: str = "",        # VD: "Theo dõi ngay!" — góc dưới phải
    # Logo image overlay
    logo_path: str = "",               # đường dẫn ảnh logo (PNG có alpha)
    logo_position: str = "top-right",  # top-left / top-right / bottom-left / bottom-right
    # Outro clip ghép vào cuối
    outro_path: str = "",              # đường dẫn clip outro (phải cùng độ phân giải)
    # Nhạc nền
    bg_music_path: str = "",           # đường dẫn file nhạc
    bg_music_volume: float = 0.08,     # âm lượng nhạc nền (0.0–1.0), nhỏ để không át giọng
    original_volume: float = 1.0,      # âm lượng video gốc
) -> str:
    """
    Xử lý video reup: giữ nguyên nội dung, chỉ thêm branding nhẹ.

    Thứ tự xử lý:
      1. Watermark text (overlay, không cắt frame nào)
      2. Logo image overlay
      3. Ghép outro clip vào cuối (nếu có)
      4. Mix nhạc nền (nếu có), âm thanh gốc vẫn được giữ
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    font = _find_font()
    font_opt = f":fontfile='{font}'" if font else ""

    has_overlay  = bool(watermark_text or watermark_bottom or logo_path)
    has_outro    = bool(outro_path and os.path.exists(outro_path))
    has_music    = bool(bg_music_path and os.path.exists(bg_music_path))

    # Nếu không có gì cần xử lý — copy thẳng
    if not has_overlay and not has_outro and not has_music:
        _run(["ffmpeg", "-y", "-i", input_path,
              "-c", "copy", "-movflags", "+faststart", output_path])
        return output_path

    # ── Bước 1: Watermark + Logo overlay → video trung gian ─────────────────
    # Chỉ re-encode video stream, copy audio stream nguyên gốc
    step1_path = input_path  # nếu không có overlay, bỏ qua bước này

    if has_overlay:
        step1_path = output_path + ".step1.mp4"

        # Logo image (overlay trước để text đè lên nếu cần)
        if logo_path and os.path.exists(logo_path):
            pad = 16
            pos_map = {
                "top-left":     f"x={pad}:y={pad}",
                "top-right":    f"x=main_w-overlay_w-{pad}:y={pad}",
                "bottom-left":  f"x={pad}:y=main_h-overlay_h-{pad}",
                "bottom-right": f"x=main_w-overlay_w-{pad}:y=main_h-overlay_h-{pad}",
            }
            pos = pos_map.get(logo_position, pos_map["top-right"])
            _run([
                "ffmpeg", "-y",
                "-i", input_path,
                "-i", logo_path,
                "-filter_complex",
                f"[1:v]scale=120:-1:flags=lanczos[logo_s];[0:v][logo_s]overlay={pos}[vlogo];[vlogo]{_COLOR_VF}[out]",
                "-map", "[out]", "-map", "0:a",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-c:a", "copy",
                "-movflags", "+faststart",
                step1_path,
            ])
            # Nếu vẫn cần text overlay, dùng step1 làm input
            if watermark_text or watermark_bottom:
                tmp = step1_path + ".tmp.mp4"
                os.rename(step1_path, tmp)
                _apply_text_overlay(tmp, step1_path, watermark_text, watermark_bottom, font_opt)
                os.remove(tmp)
        else:
            _apply_text_overlay(input_path, step1_path, watermark_text, watermark_bottom, font_opt)

    # ── Bước 2: Ghép outro vào cuối ─────────────────────────────────────────
    step2_path = step1_path

    if has_outro:
        step2_path = output_path + ".step2.mp4"
        # Dùng concat demuxer — nhanh hơn filter_complex với file lớn
        list_file = output_path + ".concat.txt"
        with open(list_file, "w") as f:
            f.write(f"file '{os.path.abspath(step1_path)}'\n")
            f.write(f"file '{os.path.abspath(outro_path)}'\n")
        try:
            _run([
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", list_file,
                "-c", "copy",
                "-movflags", "+faststart",
                step2_path,
            ])
        finally:
            if os.path.exists(list_file):
                os.remove(list_file)

    # ── Bước 3: Mix nhạc nền ─────────────────────────────────────────────────
    final_path = step2_path

    if has_music:
        final_path = output_path
        video_dur = _probe_duration(step2_path)
        # amix: trộn audio gốc + nhạc nền, loop nhạc nền nếu ngắn hơn video
        audio_filter = (
            f"[0:a]volume={original_volume}[orig];"
            f"[1:a]aloop=loop=-1:size=2e+09,atrim=duration={video_dur:.3f},"
            f"volume={bg_music_volume}[music];"
            f"[orig][music]amix=inputs=2:duration=first:dropout_transition=3[aout]"
        )
        _run([
            "ffmpeg", "-y",
            "-i", step2_path,
            "-i", bg_music_path,
            "-filter_complex", audio_filter,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",              # video không đụng tới
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            final_path,
        ])
    elif final_path != output_path:
        # Rename final step → output
        os.rename(final_path, output_path)
        final_path = output_path

    # Dọn file trung gian
    for tmp in [step1_path, step2_path]:
        if tmp != input_path and tmp != output_path and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass

    return output_path


def concat_clips(clip_paths: list[str], output_path: str) -> str:
    """
    Ghép nhiều video clips lại theo thứ tự bằng FFmpeg concat demuxer.
    Dùng stream copy — nhanh, không re-encode. Yêu cầu clips cùng codec/fps.
    Trả về output_path.
    """
    if not clip_paths:
        raise ValueError("Không có clip nào để ghép")
    if len(clip_paths) == 1:
        import shutil
        shutil.copy2(clip_paths[0], output_path)
        return output_path

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    list_file = output_path + ".concat.txt"
    with open(list_file, "w") as f:
        for p in clip_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
    try:
        _run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            "-movflags", "+faststart",
            output_path,
        ])
    finally:
        if os.path.exists(list_file):
            os.remove(list_file)
    return output_path


def concat_clips_reencode(clip_paths: list[str], output_path: str) -> str:
    """
    Ghép nhiều video clips lại — re-encode để xử lý clips có codec/độ phân giải khác nhau.
    Dùng FFmpeg concat filter. Chậm hơn stream copy nhưng tương thích mọi nguồn.
    Trả về output_path.
    """
    if not clip_paths:
        raise ValueError("Không có clip nào để ghép")
    if len(clip_paths) == 1:
        # 1 clip: chuẩn hoá về H.264/AAC để đảm bảo tương thích
        _run([
            "ffmpeg", "-y", "-i", clip_paths[0],
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            output_path,
        ])
        return output_path

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    n = len(clip_paths)

    # Build filter_complex: mỗi clip scale về 1080p, concat lại
    inputs = []
    for p in clip_paths:
        inputs += ["-i", p]

    filter_parts = []
    for i in range(n):
        filter_parts.append(
            f"[{i}:v]scale=1920:1080:flags=lanczos:force_original_aspect_ratio=decrease,"
            f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v{i}];"
            f"[{i}:a]aresample=44100[a{i}]"
        )
    concat_v = "".join(f"[v{i}][a{i}]" for i in range(n))
    filter_parts.append(f"{concat_v}concat=n={n}:v=1:a=1[vconcat][aout]")
    filter_parts.append(f"[vconcat]{_COLOR_VF}[vout]")

    _run([
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", ";".join(filter_parts),
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ], timeout=1800)
    return output_path


def _apply_text_overlay(
    input_path: str,
    output_path: str,
    watermark_text: str,
    watermark_bottom: str,
    font_opt: str,
) -> None:
    """Re-encode video stream với drawtext overlay, copy audio nguyên gốc."""
    vf_parts = []
    if watermark_text:
        t = _esc(watermark_text)
        vf_parts.append(
            f"drawtext=text='{t}':x=20:y=20"
            f":fontsize=38:fontcolor=white@0.88"
            f":borderw=3:bordercolor=black@0.65{font_opt}"
        )
    if watermark_bottom:
        t = _esc(watermark_bottom)
        vf_parts.append(
            f"drawtext=text='{t}':x=w-text_w-20:y=h-text_h-20"
            f":fontsize=30:fontcolor=white@0.75"
            f":borderw=2:bordercolor=black@0.55{font_opt}"
        )
    _run([
        "ffmpeg", "-y", "-i", input_path,
        "-vf", ",".join(vf_parts) + ("," if vf_parts else "") + _COLOR_VF,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "copy",                  # âm thanh gốc giữ nguyên
        "-movflags", "+faststart",
        output_path,
    ])
