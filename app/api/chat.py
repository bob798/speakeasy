import os
import uuid

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.models import ChatRequest, ChatResponse, EndSessionRequest, SummaryResponse, ErrorResponse
from app.services.model_client import ClaudeService, PROVIDER_CONFIG
from app.logger import get_logger, request_id_var, LOG_LEVEL
from app.config import MODEL_NAME

router = APIRouter()
claude = ClaudeService()
logger = get_logger("chat")


def _new_request_id() -> str:
    return uuid.uuid4().hex[:8]


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    rid = _new_request_id()
    request_id_var.set(rid)
    logger.info(
        "POST /chat session=%s msg_len=%d history_turns=%d",
        req.session_id,
        len(req.message),
        len(req.history),
    )
    try:
        history = [msg.model_dump() for msg in req.history]
        reply = claude.chat(req.message, history)
        logger.info("POST /chat 完成 session=%s", req.session_id)
        return ChatResponse(reply=reply, session_id=req.session_id, request_id=rid)
    except Exception as e:
        logger.error("POST /chat 异常 session=%s error=%s", req.session_id, e)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(error=str(e), session_id=req.session_id).model_dump(),
        )


@router.post("/chat/summary", response_model=SummaryResponse)
async def chat_summary(req: EndSessionRequest):
    rid = _new_request_id()
    request_id_var.set(rid)
    logger.info(
        "POST /chat/summary session=%s history_turns=%d",
        req.session_id,
        len(req.history),
    )
    try:
        history = [msg.model_dump() for msg in req.history]
        tip = claude.generate_summary(history)
        logger.info("POST /chat/summary 完成 session=%s", req.session_id)
        return SummaryResponse(tip=tip, session_id=req.session_id)
    except Exception as e:
        logger.error("POST /chat/summary 异常 session=%s error=%s", req.session_id, e)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(error=str(e), session_id=req.session_id).model_dump(),
        )


@router.get("/debug/status")
async def debug_status():
    provider = os.getenv("MODEL_PROVIDER", "anthropic").lower()
    env_key = PROVIDER_CONFIG.get(provider, {}).get("env_key", "")
    api_key = os.getenv(env_key, "") if env_key else ""
    api_key_configured = bool(api_key)
    api_key_prefix = (api_key[:8] + "...") if api_key_configured else ""

    return {
        "provider": provider,
        "model": MODEL_NAME,
        "api_key_configured": api_key_configured,
        "api_key_prefix": api_key_prefix,
        "log_level": LOG_LEVEL,
    }
