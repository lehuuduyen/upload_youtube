"""
Dọn file video sau khi job đã upload xong — để nhẹ ổ đĩa.

Xoá file gốc tải về (downloads), file đã xử lý (processed) và các file trung gian
(temp) có prefix job_{id}_. Giữ lại thumbnail (rất nhẹ) và clip người dùng upload.
"""
import os
import glob
import logging

from config import settings

logger = logging.getLogger(__name__)


def cleanup_job_files(job, delete_processed: bool = True) -> dict:
    """
    Xoá file video của 1 job đã upload.

    delete_processed=True  → xoá cả file gốc + file đã xử lý (nhẹ tối đa).
    delete_processed=False → chỉ xoá file gốc tải về, giữ file processed.

    Trả về {"removed": [path...], "freed_bytes": int}.
    """
    removed = []
    freed = 0

    def _rm(path):
        nonlocal freed
        if path and os.path.isfile(path):
            try:
                size = os.path.getsize(path)
                os.remove(path)
                removed.append(path)
                freed += size
            except OSError as e:
                logger.warning("Không xoá được %s: %s", path, e)

    # File gốc tải về
    _rm(job.downloaded_video_path)

    # File đã xử lý (đã upload)
    if delete_processed:
        _rm(job.processed_video_path)

    # File trung gian theo prefix job_{id}_ trong downloads/temp/processed
    job_id = job.id
    search_dirs = [settings.DOWNLOADS_DIR, settings.TEMP_DIR]
    if delete_processed:
        search_dirs.append(settings.PROCESSED_DIR)
    for d in search_dirs:
        for path in glob.glob(os.path.join(d, f"job_{job_id}_*")):
            _rm(path)
        for path in glob.glob(os.path.join(d, f"job_{job_id}.*")):
            _rm(path)

    # Cập nhật DB: file không còn → set None để retry chạy lại full pipeline
    job.downloaded_video_path = None
    if delete_processed:
        job.processed_video_path = None

    if removed:
        job.append_log(
            f"Đã dọn {len(removed)} file video ({freed / 1024 / 1024:.1f} MB) sau upload"
        )

    return {"removed": removed, "freed_bytes": freed}
