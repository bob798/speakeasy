import io
from groq import AsyncGroq
from app.config import settings

MIME_MAP = {
    "webm": "audio/webm", "mp4": "audio/mp4", "m4a": "audio/mp4",
    "wav":  "audio/wav",  "ogg": "audio/ogg", "mp3": "audio/mpeg"
}


async def transcribe_audio(audio_bytes: bytes, filename: str) -> dict:
    if not settings.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not configured")

    ext  = filename.rsplit(".", 1)[-1].lower()
    mime = MIME_MAP.get(ext, "audio/webm")

    client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    result = await client.audio.transcriptions.create(
        model="whisper-large-v3",
        file=(filename, io.BytesIO(audio_bytes), mime),
        language="en",
        response_format="verbose_json"
    )
    return {
        "text":     result.text.strip(),
        "duration": getattr(result, "duration", 0.0)
    }
