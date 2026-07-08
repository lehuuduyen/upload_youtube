FROM python:3.11-slim

# System deps: ffmpeg (render video), curl (healthcheck), fonts (drawtext tiếng Việt)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    fonts-noto-core \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright Chromium + system libs — cần cho browser_extractor (site phim nhúng JS/Cloudflare)
RUN python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN mkdir -p /app/storage/downloads /app/storage/processed /app/storage/thumbnails \
    /app/storage/temp /app/storage/logos /app/storage/outros /app/storage/uploads

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8001/api/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
