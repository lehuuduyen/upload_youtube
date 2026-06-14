"""
Media router — stream video files for in-browser preview.
Supports HTTP Range requests (needed for <video> element).
Also handles logo / outro file uploads.
"""
import os
import mimetypes
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.video_job import VideoJob

router = APIRouter(prefix="/api/media", tags=["media"])

CHUNK_SIZE = 1024 * 1024  # 1MB


@router.get("/preview/{job_id}")
async def preview_video(job_id: int, request: Request, db: Session = Depends(get_db)):
    """Stream processed video for browser preview. Supports Range requests."""
    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")

    video_path = job.processed_video_path
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(404, "Video file not found. Job may not be processed yet.")

    file_size = os.path.getsize(video_path)
    mime_type = mimetypes.guess_type(video_path)[0] or "video/mp4"

    range_header = request.headers.get("range")

    if range_header:
        # Parse: "bytes=start-end"
        try:
            range_val = range_header.replace("bytes=", "")
            start_str, end_str = range_val.split("-")
            start = int(start_str)
            end = int(end_str) if end_str else file_size - 1
        except ValueError:
            raise HTTPException(400, "Invalid Range header")

        end = min(end, file_size - 1)
        length = end - start + 1

        def iter_file():
            with open(video_path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            iter_file(),
            status_code=206,
            media_type=mime_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(length),
            },
        )

    # Full file
    def iter_full():
        with open(video_path, "rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                yield chunk

    return StreamingResponse(
        iter_full(),
        media_type=mime_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
        },
    )


@router.post("/review/{job_id}/approve")
async def approve_video(job_id: int, db: Session = Depends(get_db)):
    """Duyệt video — cho phép upload lên platform."""
    import asyncio
    from models.video_job import JobStatus
    from workers.job_worker import upload_only

    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status not in ("ready",):
        raise HTTPException(400, f"Job must be READY to approve, got {job.status}")

    job.review_status = "approved"
    job.upload_mode = "immediate"
    db.commit()

    asyncio.create_task(upload_only(job_id, db))
    return {"message": "Approved — uploading now", "id": job_id}


@router.post("/review/{job_id}/reject")
def reject_video(job_id: int, db: Session = Depends(get_db)):
    """Từ chối video — giữ nguyên ở READY."""
    from models.video_job import JobStatus
    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    job.review_status = "rejected"
    db.commit()
    return {"message": "Rejected — video stays at READY", "id": job_id}


# ── File uploads ──────────────────────────────────────────────────────────────

LOGO_ALLOWED  = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
OUTRO_ALLOWED = {".mp4", ".mov", ".mkv", ".webm"}
VIDEO_ALLOWED = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


@router.post("/upload/logo")
async def upload_logo(file: UploadFile = File(...)):
    """Upload ảnh logo (PNG/JPG). Trả về đường dẫn server để dùng trong pipeline."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in LOGO_ALLOWED:
        raise HTTPException(400, f"Định dạng không hỗ trợ. Chấp nhận: {', '.join(LOGO_ALLOWED)}")

    os.makedirs(settings.LOGOS_DIR, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = os.path.join(settings.LOGOS_DIR, filename)

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10 MB
        raise HTTPException(400, "File quá lớn (tối đa 10 MB)")

    with open(dest, "wb") as f:
        f.write(content)

    return {"path": dest, "filename": filename, "original_name": file.filename}


@router.post("/upload/outro")
async def upload_outro(file: UploadFile = File(...)):
    """Upload clip outro video (MP4/MOV). Trả về đường dẫn server để dùng trong pipeline."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in OUTRO_ALLOWED:
        raise HTTPException(400, f"Định dạng không hỗ trợ. Chấp nhận: {', '.join(OUTRO_ALLOWED)}")

    os.makedirs(settings.OUTROS_DIR, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = os.path.join(settings.OUTROS_DIR, filename)

    # Stream write — outro có thể lớn
    with open(dest, "wb") as f:
        while chunk := await file.read(1024 * 1024):  # 1 MB chunks
            f.write(chunk)

    size_mb = os.path.getsize(dest) / 1024 / 1024
    return {"path": dest, "filename": filename, "original_name": file.filename, "size_mb": round(size_mb, 1)}


@router.get("/files/logos")
def list_logo_files():
    """Liệt kê các file logo đã upload trong LOGOS_DIR."""
    os.makedirs(settings.LOGOS_DIR, exist_ok=True)
    IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    files = []
    for fname in sorted(os.listdir(settings.LOGOS_DIR)):
        ext = os.path.splitext(fname)[1].lower()
        if ext not in IMAGE_EXT:
            continue
        fpath = os.path.join(settings.LOGOS_DIR, fname)
        size_kb = round(os.path.getsize(fpath) / 1024, 1)
        files.append({"path": fpath, "filename": fname, "size_kb": size_kb})
    return files


@router.get("/files/outros")
def list_outro_files():
    """Liệt kê các file outro đã upload trong OUTROS_DIR."""
    os.makedirs(settings.OUTROS_DIR, exist_ok=True)
    files = []
    for fname in sorted(os.listdir(settings.OUTROS_DIR)):
        ext = os.path.splitext(fname)[1].lower()
        if ext not in VIDEO_ALLOWED:
            continue
        fpath = os.path.join(settings.OUTROS_DIR, fname)
        size_mb = round(os.path.getsize(fpath) / 1024 / 1024, 1)
        files.append({"path": fpath, "filename": fname, "size_mb": size_mb})
    return files


@router.get("/files/videos")
def list_video_files():
    """Liệt kê các file video đã upload trong UPLOADS_DIR để chọn lại mà không cần upload."""
    os.makedirs(settings.UPLOADS_DIR, exist_ok=True)
    files = []
    for fname in sorted(os.listdir(settings.UPLOADS_DIR)):
        ext = os.path.splitext(fname)[1].lower()
        if ext not in VIDEO_ALLOWED:
            continue
        fpath = os.path.join(settings.UPLOADS_DIR, fname)
        size_mb = round(os.path.getsize(fpath) / 1024 / 1024, 1)
        files.append({
            "path": fpath,
            "filename": fname,
            "size_mb": size_mb,
        })
    return files


@router.post("/upload/video")
async def upload_video_clip(file: UploadFile = File(...)):
    """Upload video clip để ghép (MP4/MOV/MKV). Trả về đường dẫn server."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in VIDEO_ALLOWED:
        raise HTTPException(400, f"Định dạng không hỗ trợ. Chấp nhận: {', '.join(VIDEO_ALLOWED)}")

    os.makedirs(settings.UPLOADS_DIR, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = os.path.join(settings.UPLOADS_DIR, filename)

    with open(dest, "wb") as f:
        while chunk := await file.read(2 * 1024 * 1024):  # 2 MB chunks
            f.write(chunk)

    size_mb = os.path.getsize(dest) / 1024 / 1024
    return {
        "path": dest,
        "filename": filename,
        "original_name": file.filename,
        "size_mb": round(size_mb, 1),
    }
