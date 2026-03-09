from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from app.services.stt_service import transcribe_audio
from app.config import settings

router = APIRouter()

MAX_SIZE = 25 * 1024 * 1024  # 25 MB


@router.post("/stt")
async def stt(audio: UploadFile = File(...)):
    if not settings.GROQ_API_KEY:
        return JSONResponse(
            status_code=503,
            content={"error": "STT_NOT_CONFIGURED", "fallback": "webspeech"}
        )

    data = await audio.read()
    if len(data) > MAX_SIZE:
        return JSONResponse(status_code=413, content={"error": "FILE_TOO_LARGE"})

    try:
        result = await transcribe_audio(data, audio.filename or "rec.webm")
        return result
    except Exception as e:
        err = str(e)
        if "429" in err or "rate" in err.lower():
            return JSONResponse(
                status_code=429,
                content={"error": "STT_RATE_LIMITED", "retry_after": 60, "fallback": "webspeech"}
            )
        return JSONResponse(
            status_code=503,
            content={"error": "STT_FAILED", "fallback": "webspeech"}
        )
