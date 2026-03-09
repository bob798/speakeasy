import json
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db, AsyncSessionLocal
from app.models.db import Session, Message
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.model_client import get_model_client
from app.logger import get_logger

router = APIRouter()
logger = get_logger("chat")


def _new_request_id() -> str:
    return uuid.uuid4().hex[:8]


async def upsert_session(db: AsyncSession, session_id: str, user_id: str) -> Session:
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        session = Session(id=session_id, user_id=user_id)
        db.add(session)
        await db.flush()
    return session


async def save_message(db: AsyncSession, session_id: str, role: str, content: str) -> Message:
    msg = Message(session_id=session_id, role=role, content=content)
    db.add(msg)
    await db.flush()
    return msg


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    rid = _new_request_id()
    logger.info("POST /chat session=%s", req.session_id)

    if req.user_id and req.session_id:
        await upsert_session(db, req.session_id, req.user_id)
        await save_message(db, req.session_id, "user", req.message)

    try:
        client = get_model_client()
        history = [msg.model_dump() for msg in req.history]
        reply   = client.chat(req.message, history)

        if req.session_id:
            await save_message(db, req.session_id, "assistant", reply)

        return ChatResponse(reply=reply, session_id=req.session_id, request_id=rid)
    except Exception as e:
        logger.error("POST /chat error: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    if req.user_id and req.session_id:
        await upsert_session(db, req.session_id, req.user_id)
        await save_message(db, req.session_id, "user", req.message)
        await db.commit()  # release write lock before streaming starts

    client     = get_model_client()
    history    = [msg.model_dump() for msg in req.history]
    session_id = req.session_id

    async def generate():
        full = []
        try:
            async for chunk in client.chat_stream(req.message, history):
                full.append(chunk)
                yield f"data: {json.dumps({'type': 'delta', 'content': chunk})}\n\n"

            content = "".join(full)
            msg_id  = None
            if session_id:
                async with AsyncSessionLocal() as save_db:
                    msg    = await save_message(save_db, session_id, "assistant", content)
                    await save_db.commit()
                    msg_id = msg.id

            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'message_id': msg_id})}\n\n"

        except Exception as e:
            logger.error("chat_stream error: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
