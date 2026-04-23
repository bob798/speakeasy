"""通用追问（Ask）路由 — 跨页面复用"""
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.routers.auth import get_current_user_id
from app.services.ask_service import (
    AskError,
    append_message,
    create_thread,
    delete_thread,
    get_thread,
    list_threads,
)
from app.logger import get_logger

logger = get_logger("ask")

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────

class CreateThreadRequest(BaseModel):
    scope: str
    ref_type: str
    ref_id: str
    context: Optional[dict[str, Any]] = None
    question: str


class AppendMessageRequest(BaseModel):
    question: str


# ── Endpoints ──────────────────────────────────────────────

@router.post("/ask/threads", status_code=201)
async def create_thread_endpoint(
    req: CreateThreadRequest,
    user_id: str = Depends(get_current_user_id),
):
    try:
        return await create_thread(
            user_id=user_id,
            scope=req.scope,
            ref_type=req.ref_type,
            ref_id=req.ref_id,
            context_payload=req.context,
            first_question=req.question,
        )
    except AskError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("create_thread 失败: %s", e, exc_info=True)
        raise HTTPException(503, "追问服务暂时不可用")


@router.post("/ask/threads/{thread_id}/messages")
async def append_message_endpoint(
    thread_id: int,
    req: AppendMessageRequest,
    user_id: str = Depends(get_current_user_id),
):
    try:
        return await append_message(
            user_id=user_id,
            thread_id=thread_id,
            question=req.question,
        )
    except AskError as e:
        # 404 vs 403 vs 400：统一 400 即可，前端按消息展示
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("append_message 失败: %s", e, exc_info=True)
        raise HTTPException(503, "追问服务暂时不可用")


@router.get("/ask/threads")
async def list_threads_endpoint(
    user_id: str = Depends(get_current_user_id),
    scope: Optional[str] = Query(None),
    ref_type: Optional[str] = Query(None),
    ref_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    items = list_threads(
        user_id=user_id,
        scope=scope,
        ref_type=ref_type,
        ref_id=ref_id,
        limit=limit,
    )
    return {"items": items, "count": len(items)}


@router.get("/ask/threads/{thread_id}")
async def get_thread_endpoint(
    thread_id: int,
    user_id: str = Depends(get_current_user_id),
):
    t = get_thread(user_id=user_id, thread_id=thread_id)
    if not t:
        raise HTTPException(404, "thread 不存在")
    return t


@router.delete("/ask/threads/{thread_id}")
async def delete_thread_endpoint(
    thread_id: int,
    user_id: str = Depends(get_current_user_id),
):
    ok = delete_thread(user_id=user_id, thread_id=thread_id)
    if not ok:
        raise HTTPException(404, "thread 不存在")
    return {"deleted": True, "id": thread_id}
