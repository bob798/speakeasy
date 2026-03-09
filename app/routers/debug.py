import os
from fastapi import APIRouter
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.services.model_client import PROVIDER_CONFIG

router = APIRouter()


@router.get("/debug/status")
async def debug_status():
    provider = os.getenv("MODEL_PROVIDER", "anthropic").lower()
    env_key  = PROVIDER_CONFIG.get(provider, {}).get("env_key", "")
    api_key  = os.getenv(env_key, "") if env_key else ""

    # 检查 DB 连通性
    db_status = "disconnected"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        pass

    return {
        "status":              "ok",
        "model":               settings.MODEL_NAME,
        "provider":            provider,
        "api_key_configured":  bool(api_key),
        "db":                  db_status,
        "stt_available":       bool(settings.GROQ_API_KEY),
        "tts_available":       True,
        "groq_key_configured": bool(settings.GROQ_API_KEY),
    }
