import io
import hashlib
import json
import os
import re
import logging
from typing import Optional
from xml.sax.saxutils import escape, quoteattr

import edge_tts
import httpx

from app.config import settings

logger = logging.getLogger("tts_service")

VOICES = {
    "jenny":    "en-US-JennyNeural",
    "guy":      "en-US-GuyNeural",
    "sonia":    "en-GB-SoniaNeural",
    # 讲解用中文声音（edge-tts 对混合中英文本容错较好）
    "xiaoxiao": "zh-CN-XiaoxiaoNeural",
    "yunxi":    "zh-CN-YunxiNeural",
}

_DEFAULT_VOICE = "en-US-JennyNeural"
_DEFAULT_RATE  = "+0%"

_cache: dict = {}
_CACHE_MAX = 50

TTS_CACHE_DIR = "static/tts_cache"
os.makedirs(TTS_CACHE_DIR, exist_ok=True)


# ── Azure TTS ──────────────────────────────────────────────

def _build_ssml(text: str, voice: str, rate: str,
                phoneme_map: Optional[dict] = None) -> str:
    """构建 SSML，支持 phoneme_map 逐词 IPA 纠音。

    phoneme_map 示例: {"crisis": "ˈkraɪsɪs", "worries": "ˈwʌriz"}
    """
    content = escape(text)
    if phoneme_map:
        for word, ipa in phoneme_map.items():
            pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
            replacement = f'<phoneme alphabet="ipa" ph={quoteattr(ipa)}>{escape(word)}</phoneme>'
            content = pattern.sub(replacement, content)

    return (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        f'xml:lang="en-US"><voice name={quoteattr(voice)}>'
        f'<prosody rate={quoteattr(rate)}>{content}</prosody>'
        '</voice></speak>'
    )


async def _azure_tts(text: str, voice: str = "en-US-JennyNeural",
                     rate: str = "+0%", phoneme_map: dict = None) -> tuple:
    """Azure TTS REST API 调用"""
    key = settings.AZURE_TTS_KEY
    region = settings.AZURE_TTS_REGION
    if not key:
        raise RuntimeError("AZURE_TTS_KEY not configured")

    ssml = _build_ssml(text, voice, rate, phoneme_map)
    async with httpx.AsyncClient(trust_env=False) as client:
        resp = await client.post(
            f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
            headers={
                "Ocp-Apim-Subscription-Key": key,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "audio-24khz-96kbitrate-mono-mp3",
            },
            content=ssml.encode("utf-8"),
            timeout=10,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Azure TTS failed: HTTP {resp.status_code}")
        audio = resp.content
        if not audio:
            raise RuntimeError("Azure TTS returned empty audio")
    return audio, "audio/mpeg"


# ── Edge TTS ───────────────────────────────────────────────

async def _edge_tts(text: str, voice: str = _DEFAULT_VOICE,
                    rate: str = _DEFAULT_RATE) -> tuple:
    """edge-tts 调用"""
    buf = io.BytesIO()
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
    except Exception:
        buf = io.BytesIO()
        communicate = edge_tts.Communicate(text, _DEFAULT_VOICE, rate=_DEFAULT_RATE)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])

    audio = buf.getvalue()
    if not audio:
        raise RuntimeError("edge-tts returned empty audio")
    return audio, "audio/mpeg"


# ── Google Cloud Text-to-Speech ────────────────────────────

# Edge/Azure voice 名 → Google voice (languageCode, name)
# Google 的 Neural2 / Wavenet 是 premium tier, 收费但效果优于 Standard
_GOOGLE_VOICE_MAP = {
    "en-US-JennyNeural":    ("en-US", "en-US-Neural2-F"),  # 女声
    "en-US-GuyNeural":      ("en-US", "en-US-Neural2-D"),  # 男声
    "en-GB-SoniaNeural":    ("en-GB", "en-GB-Neural2-A"),  # 英国女声
    "zh-CN-XiaoxiaoNeural": ("cmn-CN", "cmn-CN-Wavenet-A"),
    "zh-CN-YunxiNeural":    ("cmn-CN", "cmn-CN-Wavenet-C"),
}


def _parse_speed_to_rate(speed: str) -> float:
    """Edge 风格 speed (+20% / -40%) → Google speakingRate (1.2 / 0.6)."""
    s = (speed or "+0%").strip().rstrip("%")
    try:
        pct = float(s)
    except (TypeError, ValueError):
        return 1.0
    return max(0.25, min(4.0, 1.0 + pct / 100))


async def _google_tts(text: str, voice: str = "en-US-JennyNeural",
                      speed: str = "+0%") -> tuple:
    """Google Cloud TTS REST API · auth via API key."""
    import base64
    api_key = settings.GOOGLE_TTS_API_KEY
    if not api_key:
        raise RuntimeError("GOOGLE_TTS_API_KEY not configured")
    lang, voice_name = _GOOGLE_VOICE_MAP.get(voice, ("en-US", "en-US-Neural2-F"))
    body = {
        "input": {"text": text},
        "voice": {"languageCode": lang, "name": voice_name},
        "audioConfig": {
            "audioEncoding": "MP3",
            "speakingRate": _parse_speed_to_rate(speed),
        },
    }
    async with httpx.AsyncClient(trust_env=False) as client:
        resp = await client.post(
            "https://texttospeech.googleapis.com/v1/text:synthesize",
            params={"key": api_key},
            json=body,
            timeout=10,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Google TTS failed: HTTP {resp.status_code} {resp.text[:200]}"
            )
        audio_b64 = (resp.json() or {}).get("audioContent")
        if not audio_b64:
            raise RuntimeError("Google TTS returned empty audioContent")
        audio = base64.b64decode(audio_b64)
    return audio, "audio/mpeg"


# ── OpenAI TTS ─────────────────────────────────────────────

async def _openai_tts(text: str, voice: str = "alloy") -> tuple:
    """OpenAI TTS (requires OPENAI_API_KEY in env)."""
    from openai import OpenAI
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not configured")
    env_backup = {}
    for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
        if k in os.environ:
            env_backup[k] = os.environ.pop(k)
    try:
        client = OpenAI(api_key=api_key)
        response = client.audio.speech.create(model="tts-1", voice=voice, input=text, response_format="mp3")
        audio = response.read()
    finally:
        os.environ.update(env_backup)
    return audio, "audio/mpeg"


# ── Multi TTS 统一入口 ────────────────────────────────────

async def multi_tts(text: str, provider: str = None, voice: str = "jenny",
                    speed: str = "+0%", phoneme_map: dict = None) -> tuple:
    """Multi-source TTS with disk caching. Returns (audio_bytes, media_type)."""
    import time
    if provider is None:
        provider = settings.TTS_DEFAULT_PROVIDER

    pm_key = json.dumps(phoneme_map, sort_keys=True) if phoneme_map else ""
    cache_key = hashlib.md5(f"{provider}:{voice}:{speed}:{pm_key}:{text}".encode()).hexdigest()
    cache_path = os.path.join(TTS_CACHE_DIR, f"{cache_key}.mp3")
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            audio = f.read()
        logger.info("multi_tts cache hit provider=%s voice=%s bytes=%d", provider, voice, len(audio))
        return audio, "audio/mpeg"

    voice_name = VOICES.get(voice, voice)
    t_start = time.time()
    logger.info("multi_tts start provider=%s voice=%s(%s) speed=%s phoneme=%s text_len=%d",
                provider, voice, voice_name, speed, bool(phoneme_map), len(text))

    if provider == "azure":
        try:
            audio, media_type = await _azure_tts(text, voice_name, speed, phoneme_map)
        except Exception as e:
            logger.warning("Azure TTS 失败，降级 edge-tts: %s: %s", type(e).__name__, e, exc_info=True)
            audio, media_type = await _edge_tts(text, voice_name, speed)
    elif provider == "google":
        try:
            audio, media_type = await _google_tts(text, voice_name, speed)
        except Exception as e:
            logger.warning("Google TTS 失败，降级 edge-tts: %s: %s", type(e).__name__, e, exc_info=True)
            audio, media_type = await _edge_tts(text, voice_name, speed)
    elif provider == "edge":
        audio, media_type = await _edge_tts(text, voice_name, speed)
    elif provider == "openai":
        audio, media_type = await _openai_tts(text, voice)
    else:
        raise ValueError(f"Unknown provider: {provider}")

    elapsed_ms = int((time.time() - t_start) * 1000)
    logger.info("multi_tts done provider=%s bytes=%d ms=%d", provider, len(audio), elapsed_ms)

    with open(cache_path, "wb") as f:
        f.write(audio)
    return audio, media_type


# ── 兼容旧接口 ────────────────────────────────────────────

async def text_to_speech(text: str, voice_key: str = "jenny") -> bytes:
    voice = VOICES.get(voice_key, VOICES["jenny"])
    return await text_to_speech_with_params(text, voice, _DEFAULT_RATE)


async def text_to_speech_with_params(
    text: str,
    voice: str = _DEFAULT_VOICE,
    rate: str = _DEFAULT_RATE,
) -> bytes:
    """主 TTS 入口：azure -> edge -> raise"""
    cache_key = f"{voice}::{rate}::{text}"

    if cache_key in _cache:
        return _cache[cache_key]

    # 优先 Azure（如已配置 key）
    if settings.AZURE_TTS_KEY:
        try:
            audio, _ = await _azure_tts(text, voice, rate)
        except Exception as e:
            logger.warning("Azure TTS 失败，降级 edge-tts: %s", e)
            audio, _ = await _edge_tts(text, voice, rate)
    else:
        audio, _ = await _edge_tts(text, voice, rate)

    if len(_cache) >= _CACHE_MAX:
        for k in list(_cache)[:10]:
            del _cache[k]
    _cache[cache_key] = audio
    return audio
