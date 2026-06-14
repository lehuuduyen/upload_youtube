"""
Background job worker.
Processes VideoJob records through the full pipeline:
  download video → download music → process (FFmpeg) → upload to YouTube
"""
import os
import re
import asyncio
from datetime import datetime


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[mK]", "", str(text))

from sqlalchemy.orm import Session

from config import settings
from models.video_job import VideoJob, JobStatus


async def process_job(job_id: int, db: Session):
    """
    Main pipeline for a single video job.
    Updates job status and log at each step.
    """
    from services.downloader import download_video_async, download_music_async
    from services.processor import merge_audio_video_async, convert_aspect_ratio_async, extract_thumbnail
    from services.youtube_service import upload_video

    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        return

    def save_progress(pct: float, message: str):
        job.progress = pct
        job.append_log(message)
        db.commit()

    try:
        job.started_at = datetime.utcnow()

        # ── Step 1: Download video từ URL ──────────────────────────────────
        if job.video_url and not job.downloaded_video_path:
            job.status = JobStatus.DOWNLOADING
            save_progress(5, f"Starting video download: {job.video_url}")

            def video_progress(pct, msg):
                save_progress(5 + pct * 0.25, msg)

            video_path = await download_video_async(
                url=job.video_url,
                output_dir=settings.DOWNLOADS_DIR,
                quality=job.video_quality or "1080p",
                job_id=job.id,
                progress_callback=video_progress,
            )
            job.downloaded_video_path = video_path
            db.commit()
            save_progress(30, f"Video downloaded: {os.path.basename(video_path)}")

        # ── Step 1b: Ghép uploaded clips ────────────────────────────────────
        raw_clips = job.clip_paths  # None or list
        if raw_clips:
            valid_clips = [p for p in raw_clips if os.path.exists(p)]
            missing    = [p for p in raw_clips if not os.path.exists(p)]
            if missing:
                save_progress(31, f"WARN: {len(missing)} clip không tìm thấy trên disk: {missing}")

            if valid_clips:
                concat_out = os.path.join(settings.TEMP_DIR, f"job_{job.id}_concat.mp4")
                if job.downloaded_video_path and os.path.exists(job.downloaded_video_path):
                    all_clips = [job.downloaded_video_path] + valid_clips
                    save_progress(32, f"Ghép video nguồn + {len(valid_clips)} clip(s) upload...")
                else:
                    all_clips = valid_clips
                    save_progress(10, f"Ghép {len(valid_clips)} clip(s) upload (không có URL)...")

                save_progress(33, f"Clips: {[os.path.basename(p) for p in all_clips]}")
                from services.auto_creator.video_reup_processor import concat_clips_reencode
                await asyncio.to_thread(concat_clips_reencode, all_clips, concat_out)
                job.downloaded_video_path = concat_out
                db.commit()
                save_progress(40, f"Ghép xong: {os.path.basename(concat_out)}")
            else:
                save_progress(10, "clip_paths có giá trị nhưng tất cả đều không tồn tại trên disk")

        # ── Step 2: Download music ──────────────────────────────────────────
        if job.music_url and not job.downloaded_music_path:
            save_progress(30, f"Starting music download: {job.music_url}")

            def music_progress(pct, msg):
                save_progress(30 + pct * 0.1, msg)

            music_path = await download_music_async(
                url=job.music_url,
                output_dir=settings.DOWNLOADS_DIR,
                job_id=job.id,
                start_time=job.music_start_time,
                end_time=job.music_end_time,
                progress_callback=music_progress,
            )
            job.downloaded_music_path = music_path
            db.commit()
            save_progress(40, f"Music downloaded: {os.path.basename(music_path)}")
        elif job.music_file_path:
            job.downloaded_music_path = job.music_file_path
            db.commit()

        # ── Step 3: Process (FFmpeg) ────────────────────────────────────────
        job.status = JobStatus.PROCESSING
        db.commit()

        source_video = job.downloaded_video_path
        if not source_video or not os.path.exists(source_video):
            raise FileNotFoundError(f"Source video not found: {source_video}")

        processed_path = os.path.join(
            settings.PROCESSED_DIR, f"job_{job.id}_processed.mp4"
        )

        has_mute_range = (
            job.mute_range_start is not None
            and job.mute_range_end is not None
            and job.mute_range_end > job.mute_range_start
        )

        if job.downloaded_music_path and os.path.exists(job.downloaded_music_path):
            save_progress(42, "Merging audio and video...")

            def proc_progress(pct, msg):
                save_progress(42 + pct * 0.3, msg)

            merged_path = os.path.join(settings.TEMP_DIR, f"job_{job.id}_merged.mp4")
            await merge_audio_video_async(
                video_path=source_video,
                music_path=job.downloaded_music_path,
                output_path=merged_path,
                mute_original=job.mute_original,
                mute_range_start=job.mute_range_start if not job.mute_original else None,
                mute_range_end=job.mute_range_end if not job.mute_original else None,
                original_volume=job.original_volume or 0.2,
                music_volume=job.music_volume or 0.8,
                loop_music=job.loop_music,
                fade_in=job.fade_in_duration or 0.0,
                fade_out=job.fade_out_duration or 2.0,
                progress_callback=proc_progress,
            )
            source_video = merged_path
        elif has_mute_range and not job.mute_original:
            # Không có nhạc nền nhưng cần tắt tiếng trong khoảng thời gian
            save_progress(42, f"Muting original audio {job.mute_range_start:.1f}s–{job.mute_range_end:.1f}s...")
            from services.processor import mute_range_audio
            muted_path = os.path.join(settings.TEMP_DIR, f"job_{job.id}_muted.mp4")
            await asyncio.to_thread(
                mute_range_audio,
                source_video,
                muted_path,
                job.mute_range_start,
                job.mute_range_end,
            )
            source_video = muted_path
        else:
            save_progress(42, "No music — skipping audio merge")

        # Optional crop/resize
        if job.output_format and job.output_format not in ("16:9", "original"):
            save_progress(72, f"Converting aspect ratio to {job.output_format}...")

            def crop_progress(pct, msg):
                save_progress(72 + pct * 0.15, msg)

            await convert_aspect_ratio_async(
                input_path=source_video,
                output_path=processed_path,
                target_ratio=job.output_format,
                width=job.output_width,
                height=job.output_height,
                progress_callback=crop_progress,
            )
        else:
            import shutil
            shutil.copy2(source_video, processed_path)

        job.processed_video_path = processed_path
        db.commit()
        save_progress(86, f"Processing complete: {os.path.basename(processed_path)}")

        # ── Step 3b: Logo overlay ────────────────────────────────────────────
        if job.logo_path and os.path.exists(job.logo_path):
            save_progress(86, f"Thêm logo: {os.path.basename(job.logo_path)}")
            logo_out = os.path.join(settings.TEMP_DIR, f"job_{job.id}_with_logo.mp4")
            size = job.logo_size or 80
            pos_map = {
                "top-left":     f"x=20:y=20",
                "top-right":    f"x=main_w-overlay_w-20:y=20",
                "bottom-left":  f"x=20:y=main_h-overlay_h-20",
                "bottom-right": f"x=main_w-overlay_w-20:y=main_h-overlay_h-20",
            }
            pos = pos_map.get(job.logo_position or "top-left", "x=20:y=20")
            from services.processor import run_ffmpeg, _COLOR_VF
            run_ffmpeg([
                "-i", job.processed_video_path,
                "-i", job.logo_path,
                "-filter_complex",
                f"[1:v]scale={size}:-1:flags=lanczos[logo];[0:v][logo]overlay={pos}[vl];[vl]{_COLOR_VF}[vout]",
                "-map", "[vout]", "-map", "0:a",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-c:a", "copy", logo_out,
            ])
            job.processed_video_path = logo_out
            db.commit()
            save_progress(87, "Đã thêm logo")

        # ── Step 3c: Ghép outro vào cuối ────────────────────────────────────
        if job.outro_path and os.path.exists(job.outro_path):
            save_progress(87, f"Ghép outro: {os.path.basename(job.outro_path)}")
            from services.auto_creator.video_reup_processor import concat_clips_reencode
            outro_out = os.path.join(settings.TEMP_DIR, f"job_{job.id}_with_outro.mp4")
            await asyncio.to_thread(concat_clips_reencode, [job.processed_video_path, job.outro_path], outro_out)
            job.processed_video_path = outro_out
            db.commit()
            save_progress(88, "Đã ghép outro")

        # Auto-generate thumbnail if not set
        if not job.thumbnail_path:
            thumb_path = os.path.join(settings.THUMBNAILS_DIR, f"job_{job.id}_thumb.jpg")
            try:
                from services.processor import extract_thumbnail
                extract_thumbnail(processed_path, thumb_path)
                job.thumbnail_path = thumb_path
                db.commit()
            except Exception:
                pass

        # ── Step 4: Upload to YouTube ───────────────────────────────────────
        # If manual mode: stop here, wait for user to trigger upload
        if job.upload_mode == "manual":
            job.status = JobStatus.READY
            save_progress(88, "Video đã xử lý xong. Nhấn 'Upload ngay' để đăng lên YouTube.")
            return

        job.status = JobStatus.UPLOADING
        save_progress(90, "Uploading to YouTube...")

        def upload_progress(pct):
            save_progress(90 + pct * 0.09, f"Uploading: {pct}%")

        result = upload_video(
            channel=job.channel,
            db=db,
            video_path=job.processed_video_path,
            title=job.title or "Untitled Video",
            description=job.description or "",
            tags=job.tags or [],
            category_id=job.category_id or "22",
            privacy_status=job.privacy_status or "private",
            thumbnail_path=job.thumbnail_path,
            scheduled_publish_at=job.scheduled_publish_at,
            language=job.language or "vi",
            on_progress=upload_progress,
        )

        # ── Done ────────────────────────────────────────────────────────────
        job.youtube_video_id = result["video_id"]
        job.youtube_url = result["url"]
        job.status = JobStatus.UPLOADED
        job.completed_at = datetime.utcnow()
        save_progress(100, f"Upload complete! {result['url']}")

    except Exception as e:
        clean_err = _strip_ansi(e)
        job.status = JobStatus.FAILED
        job.error_message = clean_err
        job.append_log(f"ERROR: {clean_err}")
        db.commit()

        # Auto-retry
        if job.retry_count < job.max_retries:
            job.retry_count += 1
            job.status = JobStatus.QUEUED
            job.append_log(f"Scheduled retry {job.retry_count}/{job.max_retries}")
            db.commit()


async def upload_only(job_id: int, db: Session):
    """Skip download/processing — go straight to YouTube upload using existing processed file."""
    from services.youtube_service import upload_video

    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        return

    def save_progress(pct: float, message: str):
        job.progress = pct
        job.append_log(message)
        db.commit()

    try:
        import os
        if not job.processed_video_path or not os.path.exists(job.processed_video_path):
            raise FileNotFoundError(f"Processed video not found: {job.processed_video_path}")

        job.status = JobStatus.UPLOADING
        job.started_at = datetime.utcnow()
        save_progress(90, "Uploading to YouTube...")

        def upload_progress(pct):
            save_progress(90 + pct * 0.09, f"Uploading: {pct}%")

        result = upload_video(
            channel=job.channel,
            db=db,
            video_path=job.processed_video_path,
            title=job.title or "Untitled Video",
            description=job.description or "",
            tags=job.tags or [],
            category_id=job.category_id or "22",
            privacy_status=job.privacy_status or "private",
            thumbnail_path=job.thumbnail_path,
            scheduled_publish_at=job.scheduled_publish_at,
            language=job.language or "vi",
            on_progress=upload_progress,
        )

        job.youtube_video_id = result["video_id"]
        job.youtube_url = result["url"]
        job.status = JobStatus.UPLOADED
        job.completed_at = datetime.utcnow()
        save_progress(100, f"Upload complete! {result['url']}")

    except Exception as e:
        clean_err = _strip_ansi(e)
        job.status = JobStatus.FAILED
        job.error_message = clean_err
        job.append_log(f"ERROR: {clean_err}")
        db.commit()


async def run_pending_jobs(db: Session, max_concurrent: int = 2):
    """
    Process all PENDING jobs that have reached their upload_at time.
    Called periodically by the scheduler.
    """
    from models.video_job import VideoJob, JobStatus
    from datetime import datetime

    now = datetime.utcnow()
    ready_jobs = (
        db.query(VideoJob)
        .filter(
            VideoJob.status == JobStatus.PENDING,
            (VideoJob.upload_at <= now) | (VideoJob.upload_at == None),
        )
        .order_by(VideoJob.priority.desc(), VideoJob.created_at.asc())
        .limit(max_concurrent)
        .all()
    )

    tasks = [process_job(job.id, db) for job in ready_jobs]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
