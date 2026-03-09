import io
import edge_tts

VOICES = {
    "jenny": "en-US-JennyNeural",
    "guy":   "en-US-GuyNeural",
    "sonia": "en-GB-SoniaNeural",
}

_cache: dict = {}
_CACHE_MAX = 50


async def text_to_speech(text: str, voice_key: str = "jenny") -> bytes:
    voice     = VOICES.get(voice_key, VOICES["jenny"])
    cache_key = f"{voice}::{text}"

    if cache_key in _cache:
        return _cache[cache_key]

    buf = io.BytesIO()
    async for chunk in edge_tts.Communicate(text, voice).stream():
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
