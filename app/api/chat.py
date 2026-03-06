from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.models import ChatRequest, ChatResponse, EndSessionRequest, SummaryResponse, ErrorResponse
from app.services.model_client import ClaudeService

router = APIRouter()
claude = ClaudeService()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        history = [msg.model_dump() for msg in req.history]
        reply = claude.chat(req.message, history)
        return ChatResponse(reply=reply, session_id=req.session_id)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(error=str(e), session_id=req.session_id).model_dump(),
        )


@router.post("/chat/summary", response_model=SummaryResponse)
async def chat_summary(req: EndSessionRequest):
    try:
        history = [msg.model_dump() for msg in req.history]
        tip = claude.generate_summary(history)
        return SummaryResponse(tip=tip, session_id=req.session_id)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(error=str(e), session_id=req.session_id).model_dump(),
        )
