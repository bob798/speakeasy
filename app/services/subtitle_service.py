"""B站字幕提取服务 — 链接解析 + SSRF 防护 + 手动粘贴兜底"""

import re
from urllib.parse import urlparse

import httpx

from app.logger import get_logger

logger = get_logger("subtitle_service")

_BV_PATTERN = re.compile(r"(BV[a-zA-Z0-9]{10,12})")
_YT_PATTERN = re.compile(
    r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)"
    r"([a-zA-Z0-9_-]{11})"
)
_BILIBILI_API = "https://api.bilibili.com"
_ALLOWED_SUBTITLE_HOSTS = (".bilibili.com", ".hdslb.com")
_MAX_SUBTITLE_SIZE = 500 * 1024  # 500KB
_TIMEOUT = 10.0
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com",
}


from typing import Optional, List, Dict


_SHORT_URL_PATTERN = re.compile(r"https?://(b23\.tv|bili\d*\.com)/\w+")


def extract_bvid(url: str) -> Optional[str]:
    m = _BV_PATTERN.search(url)
    return m.group(1) if m else None


async def resolve_short_url(url: str) -> str:
    """跟随 b23.tv 等短链接重定向，返回真实 URL"""
    if not _SHORT_URL_PATTERN.search(url):
        return url
    try:
        async with httpx.AsyncClient(
            trust_env=False, timeout=5.0, follow_redirects=True, headers=_HEADERS,
        ) as client:
            resp = await client.head(url)
            return str(resp.url)
    except Exception:
        return url


async def fetch_bilibili_subtitles(bvid: str) -> dict:
    if not _BV_PATTERN.fullmatch(bvid):
        return {"error": "BV号格式无效", "segments": []}

    try:
        async with httpx.AsyncClient(
            trust_env=False, timeout=_TIMEOUT, headers=_HEADERS
        ) as client:
            # Step 2: 获取 cid
            resp = await client.get(
                f"{_BILIBILI_API}/x/web-interface/view",
                params={"bvid": bvid},
            )
            data = resp.json()
            if data.get("code") != 0:
                return {"error": "视频不存在或无法访问", "segments": []}

            cid = data["data"]["cid"]
            title = data["data"].get("title", "")

            # Step 3: 获取字幕列表
            resp = await client.get(
                f"{_BILIBILI_API}/x/player/wbi/v2",
                params={"bvid": bvid, "cid": cid},
            )
            player_data = resp.json()
            if player_data.get("code") != 0:
                return {"error": "无法获取播放器信息", "segments": []}

            subtitles = (
                player_data.get("data", {})
                .get("subtitle", {})
                .get("subtitles", [])
            )
            if not subtitles:
                return {"error": "该视频无字幕，请手动粘贴文本", "segments": []}

            # 优先选英文字幕
            sub = next(
                (s for s in subtitles if s.get("lan", "").startswith("en")),
                subtitles[0],
            )
            sub_url = sub.get("subtitle_url", "")
            if sub_url.startswith("//"):
                sub_url = "https:" + sub_url

            # SSRF 防护: 域名白名单
            parsed = urlparse(sub_url)
            if not any(parsed.hostname and parsed.hostname.endswith(h) for h in _ALLOWED_SUBTITLE_HOSTS):
                return {"error": "字幕 URL 不在可信域名范围", "segments": []}

            # Step 4: 获取字幕内容
            resp = await client.get(sub_url)
            if len(resp.content) > _MAX_SUBTITLE_SIZE:
                return {"error": "字幕内容超过大小限制", "segments": []}

            sub_json = resp.json()
            segments = [
                {
                    "from": item.get("from", 0),
                    "to": item.get("to", 0),
                    "content": item.get("content", ""),
                }
                for item in sub_json.get("body", [])
            ]

            return {"title": title, "bvid": bvid, "segments": segments}

    except httpx.TimeoutException:
        logger.warning("B站 API 请求超时: %s", bvid)
        return {"error": "请求超时，请稍后重试或手动粘贴文本", "segments": []}
    except Exception as e:
        logger.error("字幕提取失败: %s — %s", bvid, e)
        return {"error": f"字幕提取失败: {e}", "segments": []}


def extract_youtube_id(url: str) -> Optional[str]:
    m = _YT_PATTERN.search(url)
    return m.group(1) if m else None


async def fetch_youtube_subtitles(video_id: str) -> dict:
    """通过 youtube-transcript-api 提取 YouTube 字幕"""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            TranscriptsDisabled, NoTranscriptFound, VideoUnavailable,
        )
        ytt_api = YouTubeTranscriptApi()

        # 先列出所有可用字幕
        try:
            transcript_list = ytt_api.list(video_id)
        except TranscriptsDisabled:
            return {"error": "该视频已禁用字幕，请手动粘贴文本", "segments": []}
        except VideoUnavailable:
            return {"error": "视频不可用或已被删除", "segments": []}

        # 优先手动英文字幕，其次自动生成
        transcript = None
        try:
            transcript = transcript_list.find_transcript(["en", "en-US", "en-GB"])
        except NoTranscriptFound:
            # 尝试自动生成的字幕
            try:
                generated = transcript_list.find_generated_transcript(["en", "en-US", "en-GB"])
                transcript = generated
            except NoTranscriptFound:
                return {"error": "该视频无英文字幕（手动和自动生成均无）", "segments": []}

        fetched = transcript.fetch()
        segments = [
            {
                "from": snippet.start,
                "to": snippet.start + snippet.duration,
                "content": snippet.text,
            }
            for snippet in fetched
        ]
        if not segments:
            return {"error": "字幕内容为空", "segments": []}
        return {"title": f"YouTube ({video_id})", "video_id": video_id, "segments": segments}

    except Exception as e:
        logger.warning("YouTube 字幕提取失败: %s — %s", video_id, e)
        return {"error": f"YouTube 字幕提取失败: {e}", "segments": []}


def _clear_proxy_env() -> dict:
    """临时清除代理环境变量，返回备份（用于 Groq 等不兼容 SOCKS 的客户端）"""
    import os
    backup = {}
    for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
        if k in os.environ:
            backup[k] = os.environ.pop(k)
    return backup


def _restore_proxy_env(backup: dict):
    import os
    os.environ.update(backup)


async def fetch_audio_subtitles(url: str) -> dict:
    """通过 yt-dlp 下载音频 + Groq Whisper 转字幕（适用于无字幕的视频）"""
    import tempfile
    import os

    tmp_path = None
    try:
        import yt_dlp

        # 解析 B站短链接
        resolved = await resolve_short_url(url)

        # 下载音频到临时目录（yt-dlp 自己管理文件名）
        tmp_dir = tempfile.mkdtemp(prefix="speakeasy_audio_")
        tmp_template = os.path.join(tmp_dir, "audio.%(ext)s")

        ydl_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": tmp_template,
            "quiet": True,
            "no_warnings": True,
            "cookiesfrombrowser": ("safari",),  # B站 412 反爬需要浏览器 Cookie
        }

        # yt-dlp 阶段：保留代理环境变量
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(resolved, download=True)
            title = info.get("title", "")
            duration = info.get("duration", 0)

        # 找到下载的音频文件（yt-dlp 可能用不同扩展名）
        tmp_path = None
        for f in os.listdir(tmp_dir):
            fpath = os.path.join(tmp_dir, f)
            if os.path.isfile(fpath) and os.path.getsize(fpath) > 0:
                tmp_path = fpath
                break

        if not tmp_path:
            return {"error": "音频下载失败", "segments": []}

        # 限制时长 (20 分钟)
        if duration and duration > 1200:
            return {"error": "视频超过 20 分钟，请手动粘贴文本", "segments": []}

        # Groq Whisper 阶段：必须清除 SOCKS 代理（Groq SDK 不兼容）
        from dotenv import load_dotenv
        load_dotenv()

        proxy_backup = _clear_proxy_env()
        try:
            from groq import Groq
            groq_key = os.environ.get("GROQ_API_KEY")
            if not groq_key:
                return {"error": "未配置 GROQ_API_KEY，无法进行语音识别", "segments": []}

            client = Groq(api_key=groq_key)
            with open(tmp_path, "rb") as f:
                result = client.audio.transcriptions.create(
                    file=("audio.m4a", f),
                    model="whisper-large-v3",
                    response_format="verbose_json",
                    language="en",
                )
        finally:
            _restore_proxy_env(proxy_backup)

        segments = []
        for s in (result.segments or []):
            seg = s if isinstance(s, dict) else s.__dict__
            text = seg.get("text", "").strip()
            if text:
                segments.append({
                    "from": seg.get("start", 0),
                    "to": seg.get("end", 0),
                    "content": text,
                })

        if not segments:
            return {"error": "语音识别未产生结果", "segments": []}

        # Save audio to persistent cache for original audio playback
        audio_cache_dir = os.path.join("static", "audio_cache")
        os.makedirs(audio_cache_dir, exist_ok=True)
        # Use a stable ID from the URL for caching
        import hashlib as _hashlib
        source_hash = _hashlib.md5(url.encode()).hexdigest()[:16]
        ext = os.path.splitext(tmp_path)[1] or ".m4a"
        cached_audio_path = os.path.join(audio_cache_dir, f"{source_hash}{ext}")

        import shutil
        try:
            shutil.copy2(tmp_path, cached_audio_path)
        except Exception as copy_err:
            logger.warning("音频缓存失败: %s", copy_err)
            cached_audio_path = None

        result = {"title": title, "segments": segments, "source": "whisper"}
        if cached_audio_path:
            result["audio_file"] = f"/static/audio_cache/{source_hash}{ext}"
        return result

    except Exception as e:
        logger.error("音频字幕提取失败: %s", e)
        return {"error": f"音频字幕提取失败: {e}", "segments": []}
    finally:
        import shutil as _shutil
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        if 'tmp_dir' in dir() and tmp_dir and os.path.exists(tmp_dir):
            _shutil.rmtree(tmp_dir, ignore_errors=True)


def parse_manual_text(text: str) -> list[dict]:
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    return [{"from": 0, "to": 0, "content": line} for line in lines]
