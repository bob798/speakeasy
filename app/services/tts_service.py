import io
import hashlib
import os

import edge_tts

VOICES = {
    "jenny": "en-US-JennyNeural",
    "guy":   "en-US-GuyNeural",
    "sonia": "en-GB-SoniaNeural",
}

_DEFAULT_VOICE = "en-US-JennyNeural"
_DEFAULT_RATE  = "+0%"

_cache: dict = {}
_CACHE_MAX = 50

TTS_CACHE_DIR = "static/tts_cache"
os.makedirs(TTS_CACHE_DIR, exist_ok=True)


async def multi_tts(text: str, provider: str = "edge", voice: str = "jenny", speed: str = "+0%") -> tuple:
    """Multi-source TTS with disk caching. Returns (audio_bytes, media_type)."""
    cache_key = hashlib.md5(f"{provider}:{voice}:{speed}:{text}".encode()).hexdigest()
    cache_path = os.path.join(TTS_CACHE_DIR, f"{cache_key}.mp3")
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            return f.read(), "audio/mpeg"

    if provider == "edge":
        voice_name = VOICES.get(voice, VOICES["jenny"])
        audio = await text_to_speech_with_params(text, voice_name, speed)
        media_type = "audio/mpeg"
    elif provider == "openai":
        audio, media_type = await _openai_tts(text, voice)
    else:
        raise ValueError(f"Unknown provider: {provider}")

    with open(cache_path, "wb") as f:
        f.write(audio)
    return audio, media_type


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


async def text_to_speech(text: str, voice_key: str = "jenny") -> bytes:
    voice = VOICES.get(voice_key, VOICES["jenny"])
    return await text_to_speech_with_params(text, voice, _DEFAULT_RATE)


async def text_to_speech_with_params(
    text: str,
    voice: str = _DEFAULT_VOICE,
    rate: str = _DEFAULT_RATE,
) -> bytes:
    """edge-tts 调用，支持显式指定完整 voice 名称和 rate（来自用户设置）"""
    cache_key = f"{voice}::{rate}::{text}"

    if cache_key in _cache:
        return _cache[cache_key]

    buf = io.BytesIO()
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
    except Exception:
        # 降级到默认音色
        communicate = edge_tts.Communicate(text, _DEFAULT_VOICE, rate=_DEFAULT_RATE)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])

    audio = buf.getvalue()
    if not audio:
        raise RuntimeError("edge-tts returned empty audio")

    if len(_cache) >= _CACHE_MAX:
        for k in list(_cache)[:10]:
            del _cache[k]
    _cache[cache_key] = audio
    return audio
