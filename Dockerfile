# ── Stage 1 · 构建前端 SPA ───────────────────────────────────
FROM node:20-slim AS frontend-build

WORKDIR /build

# 依赖单独 COPY · 利用 Docker layer cache
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

# 源码再 COPY + build
COPY frontend/ ./
RUN npm run build


# ── Stage 2 · 后端运行时 ─────────────────────────────────────
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端源码（含 frontend/ 但 dist/ 会被下面覆盖）
COPY . .

# 版本标签（构建时可通过 --build-arg 覆盖）
ARG APP_VERSION=""
LABEL app.version="${APP_VERSION}"

# 用 Stage 1 构建好的 dist 覆盖 frontend/dist
COPY --from=frontend-build /build/dist ./frontend/dist

# 数据目录（挂载 volume 也行 · 这里兜底）
RUN mkdir -p static/tts_cache static/audio_cache

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=3 --start-period=10s \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
