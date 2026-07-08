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

_cors_origins = ["http://localhost:5173", "http://localhost:3000"]
_cors_origins += [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
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


# Serve built frontend (production single-port deploy).
# `setup.sh` builds the SPA to frontend/dist; if present, mount it at root so the
# whole app is served from one PORT. SPA fallback returns index.html for client routes.
_FRONTEND_DIST = os.getenv(
    "FRONTEND_DIST",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist"),
)
if os.path.isdir(_FRONTEND_DIST):
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=os.path.join(_FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        candidate = os.path.join(_FRONTEND_DIST, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(_FRONTEND_DIST, "index.html"))


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8002"))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    uvicorn.run("main:app", host=host, port=port, reload=reload)
