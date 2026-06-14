"""
Video Renderer — Gen Z style (1080x1920 vertical).
Kỹ thuật:
  • Animated background (geq slow-moving color wave)
  • Hard color cuts giữa các segment (dark tinted overlay)
  • White flash 2-frame tại mỗi cut (phong cách fast-edit)
  • Text slide-up animation 0.18s
  • Neon accent bars + section numbers faded
  • Progress bar dưới cùng
"""
import os
import asyncio
import subprocess
import json


# Gen Z palette: (dark_bg hex, neon_accent hex)
_PALETTES = [
    ("0F0010", "FF006E"),  # hook   – dark purple / hot pink
    ("00101A", "00D4FF"),  # body1  – dark navy  / electric cyan
    ("001400", "39FF14"),  # body2  – dark green / neon green
    ("180800", "FF6B35"),  # body3  – dark amber / vibrant orange
    ("0A0018", "FFD700"),  # cta    – dark violet/ gold
]


def _find_font() -> str:
    candidates = [
        "/Library/Fonts/Arial Bold.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return ""


def _esc(text: str) -> str:
    """Escape text for FFmpeg drawtext."""
    # Strip emoji (codepoints > U+FFFF) — most TTF fonts can't render them
    text = "".join(c for c in text if ord(c) <= 0xFFFF)
    return (
        text
        .replace("\\", "\\\\")
        .replace("'", "\u2019")   # curly apostrophe avoids shell quoting issues
        .replace(":", "\\:")
        .replace("%", "\\%")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("&", "\\&")
        .replace("!", "\\!")
    )


def _wrap(text: str, max_chars: int = 24) -> str:
    """Word-wrap to max_chars per line."""
    words = text.split()
    lines, cur = [], []
    for w in words:
        if sum(len(x) for x in cur) + len(cur) + len(w) > max_chars:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(" ".join(cur))
    return "\\n".join(lines)


def _audio_duration(path: str) -> float:
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(probe.stdout)["format"]["duration"])


def render_with_ffmpeg(
    script: dict,
    voiceover_path: str,
    output_path: str,
    width: int = 1080,
    height: int = 1920,
) -> str:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    duration = _audio_duration(voiceover_path)
    font = _find_font()
    font_opt = f":fontfile='{font}'" if font else ""

    # ── Build segment timing ────────────────────────────────────────────────
    hook      = script.get("hook", {})
    body      = script.get("body", [])
    cta       = script.get("cta", {})

    hook_dur  = float(hook.get("duration", 3))
    body_durs = [float(p.get("duration", 12)) for p in body]
    cta_dur   = float(cta.get("duration", 5))

    # Normalise: distribute actual audio duration proportionally
    raw_total  = hook_dur + sum(body_durs) + cta_dur
    scale      = duration / raw_total if raw_total > 0 else 1.0

    t = 0.0
    segs = []  # (start, end, text, palette_index, seg_type)

    hook_end = t + hook_dur * scale
    hook_text = _wrap(hook.get("audio", script.get("title", ""))[:80])
    segs.append((t, hook_end, hook_text, 0, "hook"))
    t = hook_end

    for i, point in enumerate(body[:3]):
        end = t + body_durs[i] * scale
        txt = _wrap((point.get("text_overlay") or point.get("audio", ""))[:70])
        segs.append((t, end, txt, i + 1, f"body{i+1}"))
        t = end

    cta_end = min(t + cta_dur * scale, duration)
    cta_text = _wrap((cta.get("text_overlay") or cta.get("audio", ""))[:50])
    segs.append((t, cta_end, cta_text, 4, "cta"))

    # ── Build filter chain ──────────────────────────────────────────────────
    # Start with format normalization to ensure yuv420p for libx264
    filters = ["format=yuv420p"]

    for idx, (ts, te, text, pal_idx, seg_type) in enumerate(segs):
        bg_hex, acc_hex = _PALETTES[pal_idx % len(_PALETTES)]
        ts_f, te_f = f"{ts:.3f}", f"{te:.3f}"
        en = f"between(t,{ts_f},{te_f})"

        # ── Background panel (dark tinted) ─────────────────────────────────
        filters.append(
            f"drawbox=x=0:y=0:w=iw:h=ih"
            f":color=0x{bg_hex}@0.92:t=fill:enable='{en}'"
        )

        # ── Flash frame at segment start (2-frame white burst) ─────────────
        if idx > 0:
            flash_end = f"{ts + 0.07:.3f}"
            filters.append(
                f"drawbox=x=0:y=0:w=iw:h=ih"
                f":color=white@0.55:t=fill:enable='between(t,{ts_f},{flash_end})'"
            )

        # ── Faded section number in background ─────────────────────────────
        if seg_type.startswith("body"):
            num = seg_type[-1]  # "1", "2", "3"
            filters.append(
                f"drawtext=text='{num}'"
                f":x=(w-text_w)/2:y=h*0.12"
                f":fontsize=380:fontcolor=0x{acc_hex}@0.08"
                f"{font_opt}:enable='{en}'"
            )

        # ── Accent top bar ──────────────────────────────────────────────────
        filters.append(
            f"drawbox=x=0:y=0:w=iw:h=12"
            f":color=0x{acc_hex}:t=fill:enable='{en}'"
        )

        # ── Accent bottom bar ───────────────────────────────────────────────
        filters.append(
            f"drawbox=x=0:y=ih-12:w=iw:h=12"
            f":color=0x{acc_hex}:t=fill:enable='{en}'"
        )

        # ── Text box background for readability ─────────────────────────────
        filters.append(
            f"drawbox=x=40:y=(ih-ih*0.38)/2:w=iw-80:h=ih*0.38"
            f":color=black@0.45:t=fill:enable='{en}'"
        )

        # ── Main text (static centered — dynamic y + enable= crashes FFmpeg reinit) ──
        filters.append(
            f"drawtext=text='{_esc(text)}'"
            f":x=(w-text_w)/2:y=(h-text_h)/2"
            f":fontsize=72:fontcolor=white"
            f":borderw=4:bordercolor=black@0.9"
            f":line_spacing=16"
            f"{font_opt}:enable='{en}'"
        )

        # ── Accent underline below text ─────────────────────────────────────
        filters.append(
            f"drawbox=x=iw*0.15:y=ih*0.62:w=iw*0.70:h=5"
            f":color=0x{acc_hex}:t=fill:enable='{en}'"
        )

        # ── For CTA: add a big bold call-to-action label ────────────────────
        if seg_type == "cta":
            filters.append(
                f"drawtext=text='Like va Follow ngay'"
                f":x=(w-text_w)/2:y=h*0.72"
                f":fontsize=52:fontcolor=0x{acc_hex}"
                f":borderw=3:bordercolor=black@0.8"
                f"{font_opt}:enable='{en}'"
            )

    # ── Progress bar (white, bottom 8px) ────────────────────────────────────
    # Do NOT use min(a,b) — the comma inside function args breaks drawbox's option parser.
    # Since the video is limited to `duration` by -t, t never exceeds duration, so
    # w=iw*t/duration is safe and equivalent to iw*min(1, t/duration).
    filters.append(
        f"drawbox=x=0:y=ih-8:w=iw*t/{duration:.3f}:h=8"
        f":color=white@0.35:t=fill"
    )

    vf = ",".join(filters)

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=black:s={width}x{height}:r=30",
        "-i", voiceover_path,
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Show the FIRST 3000 chars (real error) + LAST 1000 chars (filter chain)
        stderr = result.stderr
        snippet = stderr[:3000] + ("\n...\n" + stderr[-1000:] if len(stderr) > 4000 else "")
        raise RuntimeError(f"FFmpeg render failed:\n{snippet}")

    return output_path


async def render_video_async(script: dict, voiceover_path: str, output_path: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: render_with_ffmpeg(script, voiceover_path, output_path)
    )
