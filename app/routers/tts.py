from fastapi import APIRouter
from fastapi.responses import Response, JSONResponse
from app.schemas.tts import TTSRequest
from app.services.tts_service import text_to_speech

router = APIRouter()


@router.post("/tts")
async def tts(req: TTSRequest):
    text = req.text[:1000]  # 截断不报错
    try:
        audio = await text_to_speech(text, req.voice)
        return Response(
            content=audio,
            media_type="audio/mpeg",
            headers={"Cache-Control": "public, max-age=3600"}
        )
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"error": "TTS_FAILED", "fallback": "webspeech", "detail": str(e)}
        )
