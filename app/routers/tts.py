from fastapi import APIRouter
from fastapi.responses import Response, JSONResponse
from sqlalchemy.orm import Session

from app.models.db import engine
from app.schemas.tts import TTSRequest
from app.services.tts_service import text_to_speech, text_to_speech_with_params
from app.services.settings_service import get_tts_params

router = APIRouter()


@router.post("/tts")
async def tts(req: TTSRequest):
    text = req.text[:1000]  # 截断不报错
    try:
        if req.user_id:
            with Session(engine) as db:
                params = get_tts_params(db, req.user_id)
            audio = await text_to_speech_with_params(text, params["voice"], params["rate"])
        else:
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
