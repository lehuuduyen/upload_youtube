"""
YouTube Auto Uploader — FastAPI entry point.
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from database import init_db
from services.scheduler import start_scheduler, stop_scheduler, load_all_schedules, start_trending_scheduler, start_queue_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    os.makedirs(settings.DOWNLOADS_DIR, exist_ok=True)
    os.makedirs(settings.PROCESSED_DIR, exist_ok=True)
    os.makedirs(settings.THUMBNAILS_DIR, exist_ok=True)
    os.makedirs(settings.TEMP_DIR, exist_ok=True)
    os.makedirs(settings.LOGOS_DIR, exist_ok=True)
    os.makedirs(settings.OUTROS_DIR, exist_ok=True)
    os.makedirs(settings.UPLOADS_DIR, exist_ok=True)

    init_db()

    start_scheduler()
    from database import SessionLocal
    db = SessionLocal()
    try:
        load_all_schedules(db)
    finally:
        db.close()
    start_trending_scheduler()
    start_queue_scheduler()

    yield

    # Shutdown
    stop_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
from routers.channels import router as channels_router
from routers.downloads import router as downloads_router
from routers.queue import router as queue_router
from routers.schedules import router as schedules_router
from routers.dashboard import router as dashboard_router
from routers.auto_creator import router as auto_creator_router
from routers.tiktok_accounts import router as tiktok_router
from routers.media import router as media_router
from routers.trending import router as trending_router

app.include_router(channels_router)
app.include_router(downloads_router)
app.include_router(queue_router)
app.include_router(schedules_router)
app.include_router(dashboard_router)
app.include_router(auto_creator_router)
app.include_router(tiktok_router)
app.include_router(media_router)
app.include_router(trending_router)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": settings.APP_VERSION}


if __name__ == "__main__":
    import uvicorn
    reload = os.getenv("RELOAD", "true").lower() == "true"
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=reload)
