import io
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
