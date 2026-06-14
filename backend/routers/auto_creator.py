"""
Auto Creator — hai chế độ:
  1. AI (cũ): Trend → Script → Voiceover → FFmpeg render
  2. Reup (mới): Tìm video trending YouTube → Download → Watermark → Upload
"""
import asyncio
import json
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from database import get_db, SessionLocal
from models.video_job import VideoJob, JobStatus

router = APIRouter(prefix="/api/auto-creator", tags=["auto-creator"])


# ── Request models ──────────────────────────────────────────────────────────

class TrendRequest(BaseModel):
    topic: str
    audience: str = ""


class SearchVideosRequest(BaseModel):
    query: str
    max_results: int = 10


class ReupRequest(BaseModel):
    """Chế độ Reup: tải video trending về và reup lên kênh."""
    topic: str
    channel_id: int
    source_video_url: Optional[str] = None  # URL cụ thể; nếu None → tự tìm
    # Watermark text
    watermark_text: str = ""               # góc trên trái, VD: "@TênKênh"
    watermark_bottom: str = ""             # góc dưới phải, VD: "Theo dõi ngay!"
    # Logo
    logo_position: str = "top-right"       # top-left/top-right/bottom-left/bottom-right
    # Outro
    outro_path: str = ""                   # đường dẫn file clip outro trên server
    # Nhạc nền
    bg_music_path: str = ""                # đường dẫn file nhạc trên server
    bg_music_volume: float = 0.08          # âm lượng nhạc nền (0.0–1.0)
    original_volume: float = 1.0           # âm lượng video gốc
    tiktok_account_id: Optional[int] = None
    platform: str = "youtube"
    review_before_upload: bool = True
    privacy_status: str = "private"
    category_id: str = "22"


class AICreateRequest(BaseModel):
    """Chế độ AI: tạo video hoàn toàn từ kịch bản."""
    topic: str
    audience: str
    channel_id: int
    tiktok_account_id: Optional[int] = None
    platform: str = "youtube"
    review_before_upload: bool = True
    voice_key: str = "nu_mien_bac"
    duration_seconds: int = 60
    privacy_status: str = "private"
    category_id: str = "22"
    # Branding (giống Reup)
    watermark_text: str = ""
    watermark_bottom: str = ""
    logo_path: str = ""
    logo_position: str = "top-right"
    outro_path: str = ""
    bg_music_path: str = ""
    bg_music_volume: float = 0.08
    original_volume: float = 1.0
    # Clips để ghép (trước / sau video AI)
    clip_paths: Optional[list[str]] = None   # danh sách đường dẫn server
    clip_position: str = "after"             # "before" | "after"


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/search-videos")
async def search_videos(query: str, max_results: int = 10):
    """Tìm kiếm video trending YouTube theo từ khoá."""
    from services.auto_creator.video_finder import search_youtube_videos
    loop = asyncio.get_event_loop()
    try:
        results = await loop.run_in_executor(
            None, lambda: search_youtube_videos(query, max_results)
        )
        return {"query": query, "results": results}
    except Exception as e:
        raise HTTPException(500, f"Tìm video thất bại: {e}")


@router.post("/analyze-trend")
async def analyze_trend(body: TrendRequest):
    """Phân tích trend Google Trends cho chủ đề."""
    loop = asyncio.get_event_loop()
    from services.auto_creator.trend_finder import analyze_trend as _analyze
    try:
        result = await loop.run_in_executor(None, lambda: _analyze(body.topic, body.audience))
        return result
    except Exception as e:
        raise HTTPException(500, f"Trend analysis error: {e}")


@router.post("/reup", status_code=201)
async def reup_video(
    body: ReupRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Chế độ Reup: tìm / tải video trending YouTube và reup lên kênh."""
    job = VideoJob(
        channel_id=body.channel_id,
        tiktok_account_id=body.tiktok_account_id,
        platform=body.platform,
        review_status="pending" if body.review_before_upload else "auto",
        upload_mode="manual" if body.review_before_upload else "immediate",
        auto_topic=body.topic,
        title=f"[Reup] {body.topic}",
        privacy_status=body.privacy_status,
        category_id=body.category_id,
        status=JobStatus.PENDING,
        progress=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(
        _run_reup_pipeline,
        job.id,
        body.topic,
        body.source_video_url,
        body.watermark_text,
        body.watermark_bottom,
        body.logo_position,
        body.outro_path,
        body.bg_music_path,
        body.bg_music_volume,
        body.original_volume,
    )
    return {"id": job.id, "status": "pending", "message": "Reup pipeline started"}


@router.post("/generate", status_code=201)
async def generate_video(
    body: AICreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Chế độ AI: tạo video từ kịch bản Claude → Voiceover → FFmpeg render."""
    job = VideoJob(
        channel_id=body.channel_id,
        tiktok_account_id=body.tiktok_account_id,
        platform=body.platform,
        review_status="pending" if body.review_before_upload else "auto",
        upload_mode="manual" if body.review_before_upload else "immediate",
        auto_topic=body.topic,
        title=f"[Auto] {body.topic}",
        privacy_status=body.privacy_status,
        category_id=body.category_id,
        status=JobStatus.PENDING,
        progress=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(
        _run_auto_pipeline,
        job.id,
        body.topic,
        body.audience,
        body.voice_key,
        body.duration_seconds,
        body.watermark_text,
        body.watermark_bottom,
        body.logo_path,
        body.logo_position,
        body.outro_path,
        body.bg_music_path,
        body.bg_music_volume,
        body.original_volume,
        body.clip_paths or [],
        body.clip_position,
    )
    return {"id": job.id, "status": "pending", "message": "AI pipeline started"}


# ── Reup pipeline ────────────────────────────────────────────────────────────

async def _run_reup_pipeline(
    job_id: int,
    topic: str,
    source_video_url: Optional[str],
    watermark_text: str = "",
    watermark_bottom: str = "",
    logo_position: str = "top-right",
    outro_path: str = "",
    bg_music_path: str = "",
    bg_music_volume: float = 0.08,
    original_volume: float = 1.0,
):
    db = SessionLocal()
    try:
        job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
        if not job:
            return

        def save(pct, msg):
            job.progress = pct
            job.append_log(msg)
            db.commit()

        loop = asyncio.get_event_loop()

        # ── Step 1: Tìm video ─────────────────────────────────────────────
        if not source_video_url:
            job.status = JobStatus.PENDING
            save(10, f"Đang tìm video trending: {topic}")
            from services.auto_creator.video_finder import search_youtube_videos
            results = await loop.run_in_executor(
                None, lambda: search_youtube_videos(f"{topic}", max_results=5)
            )
            if not results:
                raise RuntimeError(f"Không tìm thấy video nào cho chủ đề: {topic}")
            # Auto-chọn video mới nhất (results đã sort theo timestamp mới nhất trước)
            best = results[0]
            source_video_url = best["url"]
            ago = best.get("uploaded_ago") or best.get("upload_date") or ""
            save(20, f"Đã chọn (mới nhất): {best['title']} — {ago}")
            # Dùng title/tags của video gốc
            job.title = best["title"][:100]
            job.description = best.get("description", "")[:500]
            db.commit()
        else:
            save(10, f"Dùng video URL: {source_video_url}")
            # Lấy thông tin video
            try:
                from services.auto_creator.video_finder import get_video_info
                info = await loop.run_in_executor(None, lambda: get_video_info(source_video_url))
                job.title = info["title"][:100]
                job.description = info.get("description", "")[:500]
                if info.get("tags"):
                    job.tags = info["tags"][:15]
                db.commit()
                save(20, f"Video: {info['title']}")
            except Exception:
                save(20, "Lấy thông tin video xong")

        # ── Step 2: Download ──────────────────────────────────────────────
        job.status = JobStatus.DOWNLOADING
        save(25, "Đang tải video từ YouTube...")
        from services.auto_creator.video_reup_processor import download_video

        download_base = os.path.join(settings.DOWNLOADS_DIR, f"reup_{job_id}")
        downloaded_path = await loop.run_in_executor(
            None, lambda: download_video(source_video_url, download_base)
        )
        job.downloaded_video_path = downloaded_path
        db.commit()
        size_mb = os.path.getsize(downloaded_path) / 1024 / 1024
        save(60, f"Tải xong: {os.path.basename(downloaded_path)} ({size_mb:.1f} MB)")

        # ── Step 3: Watermark / outro / nhạc nền ─────────────────────────
        job.status = JobStatus.PROCESSING
        has_processing = bool(
            watermark_text or watermark_bottom or outro_path
            or bg_music_path or logo_position != "top-right"
        )
        out_name = f"reup_{job_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        output_path = os.path.join(settings.PROCESSED_DIR, out_name)

        if has_processing:
            parts = []
            if watermark_text or watermark_bottom:
                parts.append("watermark")
            if outro_path:
                parts.append("outro")
            if bg_music_path:
                parts.append("nhạc nền")
            save(65, f"Đang xử lý: {', '.join(parts)}...")
            from services.auto_creator.video_reup_processor import process_reup
            _dl = downloaded_path
            _op = output_path
            processed_path = await loop.run_in_executor(
                None, lambda: process_reup(
                    _dl, _op,
                    watermark_text=watermark_text,
                    watermark_bottom=watermark_bottom,
                    logo_position=logo_position,
                    outro_path=outro_path,
                    bg_music_path=bg_music_path,
                    bg_music_volume=bg_music_volume,
                    original_volume=original_volume,
                )
            )
        else:
            # Không cần xử lý — copy thẳng sang processed dir
            import shutil
            shutil.copy2(downloaded_path, output_path)
            processed_path = output_path

        job.processed_video_path = processed_path
        db.commit()
        save(78, "Xử lý video xong")

        # ── Step 4: Auto thumbnail ─────────────────────────────────────────
        thumb_path = os.path.join(settings.THUMBNAILS_DIR, f"reup_{job_id}_thumb.jpg")
        try:
            from services.processor import extract_thumbnail
            extract_thumbnail(processed_path, thumb_path)
            job.thumbnail_path = thumb_path
            db.commit()
        except Exception:
            pass

        # ── Step 5: Upload hoặc chờ review ───────────────────────────────
        if job.upload_mode == "manual" or job.review_status == "pending":
            job.status = JobStatus.READY
            save(88, "Video đã sẵn sàng! Vào Hàng Chờ để xem trước và duyệt.")
        else:
            from workers.job_worker import upload_only
            await upload_only(job_id, db)

    except Exception as e:
        import re
        clean = re.sub(r"\x1b\[[0-9;]*[mK]", "", str(e))
        job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
        if job:
            job.status = JobStatus.FAILED
            job.error_message = clean[:500]
            job.append_log(f"ERROR: {clean}")
            db.commit()
    finally:
        db.close()


# ── AI pipeline (giữ nguyên) ─────────────────────────────────────────────────

async def _run_auto_pipeline(
    job_id: int,
    topic: str,
    audience: str,
    voice_key: str,
    duration_seconds: int,
    watermark_text: str = "",
    watermark_bottom: str = "",
    logo_path: str = "",
    logo_position: str = "top-right",
    outro_path: str = "",
    bg_music_path: str = "",
    bg_music_volume: float = 0.08,
    original_volume: float = 1.0,
    clip_paths: list = None,
    clip_position: str = "after",
):
    db = SessionLocal()
    try:
        job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
        if not job:
            return

        def save(pct, msg):
            job.progress = pct
            job.append_log(msg)
            db.commit()

        loop = asyncio.get_event_loop()

        # Step 1: Trend
        job.status = JobStatus.PENDING
        save(5, f"Phân tích trend: {topic}")
        from services.auto_creator.trend_finder import analyze_trend
        trend_data = await loop.run_in_executor(None, lambda: analyze_trend(topic, audience))
        save(15, f"Trend OK — keyword: {trend_data.get('best_keyword')}")

        # Step 2: Script
        save(18, "Đang viết kịch bản với Claude AI...")
        from services.auto_creator.script_generator import generate_script
        script = await loop.run_in_executor(
            None, lambda: generate_script(trend_data, duration_seconds)
        )
        job.auto_script = json.dumps(script, ensure_ascii=False)
        job.title = script.get("title", topic)[:100]
        job.description = script.get("description", "")
        job.tags = script.get("hashtags", [])
        db.commit()
        save(35, f"Script OK — {script.get('title', '')}")

        # Step 3: Voiceover
        save(38, "Tạo voiceover tiếng Việt (Edge TTS)...")
        audio_path = os.path.join(settings.TEMP_DIR, f"auto_{job_id}_voice.mp3")
        voiceover_text = script.get("full_voiceover", "")
        if not voiceover_text:
            parts = [script.get("hook", {}).get("audio", "")]
            for p in script.get("body", []):
                parts.append(p.get("audio", ""))
            parts.append(script.get("cta", {}).get("audio", ""))
            voiceover_text = " ".join(filter(None, parts))

        from services.auto_creator.voiceover_gen import generate_voiceover_async
        await generate_voiceover_async(voiceover_text, audio_path, voice_key)
        save(55, "Voiceover OK")

        # Step 4: Render
        job.status = JobStatus.PROCESSING
        save(58, "Đang render video (FFmpeg)...")
        video_path = os.path.join(
            settings.PROCESSED_DIR,
            f"auto_{job_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        )
        from services.auto_creator.video_renderer import render_video_async
        await render_video_async(script, audio_path, video_path)
        job.processed_video_path = video_path
        db.commit()
        save(80, f"Render OK: {os.path.basename(video_path)}")

        # Step 4b: Branding overlay (watermark / logo / outro / nhạc nền)
        has_branding = bool(
            watermark_text or watermark_bottom or logo_path
            or outro_path or bg_music_path
        )
        if has_branding:
            branded_path = os.path.join(
                settings.PROCESSED_DIR,
                f"auto_{job_id}_branded_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            )
            parts = []
            if watermark_text or watermark_bottom: parts.append("watermark")
            if logo_path: parts.append("logo")
            if outro_path: parts.append("outro")
            if bg_music_path: parts.append("nhạc nền")
            save(83, f"Đang thêm branding: {', '.join(parts)}...")
            from services.auto_creator.video_reup_processor import process_reup
            _vp = video_path
            _bp = branded_path
            branded_path = await loop.run_in_executor(
                None, lambda: process_reup(
                    _vp, _bp,
                    watermark_text=watermark_text,
                    watermark_bottom=watermark_bottom,
                    logo_path=logo_path,
                    logo_position=logo_position,
                    outro_path=outro_path,
                    bg_music_path=bg_music_path,
                    bg_music_volume=bg_music_volume,
                    original_volume=original_volume,
                )
            )
            job.processed_video_path = branded_path
            db.commit()
            video_path = branded_path
            save(86, "Branding xong")

        # Step 4c: Ghép clips upload (trước hoặc sau video AI)
        valid_clips = [p for p in (clip_paths or []) if os.path.exists(p)]
        if valid_clips:
            merged_path = os.path.join(
                settings.PROCESSED_DIR,
                f"auto_{job_id}_merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            )
            save(87, f"Ghép {len(valid_clips)} clip(s) ({clip_position} video AI)...")
            from services.auto_creator.video_reup_processor import concat_clips_reencode
            if clip_position == "before":
                all_clips = valid_clips + [video_path]
            else:
                all_clips = [video_path] + valid_clips
            _clips = all_clips
            _mp = merged_path
            merged_path = await loop.run_in_executor(
                None, lambda: concat_clips_reencode(_clips, _mp)
            )
            job.processed_video_path = merged_path
            db.commit()
            video_path = merged_path
            save(89, "Ghép clip xong")

        # Auto thumbnail
        thumb_path = os.path.join(settings.THUMBNAILS_DIR, f"auto_{job_id}_thumb.jpg")
        try:
            from services.processor import extract_thumbnail
            extract_thumbnail(video_path, thumb_path)
            job.thumbnail_path = thumb_path
            db.commit()
        except Exception:
            pass

        # Step 5: Upload hoặc chờ review
        if job.upload_mode == "manual" or job.review_status == "pending":
            job.status = JobStatus.READY
            save(88, "Video đã tạo xong! Vào Hàng Chờ để xem trước và duyệt.")
        else:
            from workers.job_worker import upload_only
            await upload_only(job_id, db)

    except Exception as e:
        import re
        clean = re.sub(r"\x1b\[[0-9;]*[mK]", "", str(e))
        job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
        if job:
            job.status = JobStatus.FAILED
            job.error_message = clean[:500]
            job.append_log(f"ERROR: {clean}")
            db.commit()
    finally:
        db.close()
