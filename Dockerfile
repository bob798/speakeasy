FROM python:3.11-slim

# 安装 ffmpeg（音频处理需要）
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 创建缓存目录
RUN mkdir -p static/tts_cache static/audio_cache

# 数据路径（Fly.io 挂载卷 /data）
ENV SPEAKEASY_DB_PATH=/data/speakeasy.db

# 暴露端口
EXPOSE 8000

# 启动（数据目录自动创建）
CMD ["sh", "-c", "mkdir -p /data && uvicorn main:app --host 0.0.0.0 --port 8000"]
