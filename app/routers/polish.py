"""写作教练路由 — V0.11

- POST /polish/text         一次性润色
- POST /polish/chat         多轮对话润色
- GET  /polish/cards        列表
- POST /polish/cards        保存为 polish_card
- DELETE /polish/cards/{id} 软删
- POST /polish/cards/{id}/rate FSRS 评分
- GET  /polish/due          到期复习卡（P1 用）
"""
import asyncio
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel

from app.routers.auth import get_current_user_id
from app.services import polish_service
from app.services import polish_facts as polish_facts_service
from app.logger import get_logger

logger = get_logger("polish")

router = APIRouter()


class PolishTextRequest(BaseModel):
    text: str


class PolishChatTurn(BaseModel):
    role: str
    content: str


class PolishChatRequest(BaseModel):
    original: str
    current_polished: str
    instruction: str
    history: Optional[List[PolishChatTurn]] = None


class PolishCardCreate(BaseModel):
    original: str
    polished: str
    explanation: str = ""
    context: Optional[str] = None
    category: str = ""
    init_fsrs: bool = True   # P1 · 默认入 FSRS 队列


class RateRequest(BaseModel):
    rating: str  # again/hard/good/easy


@router.post("/polish/text")
async def polish_text(
    req: PolishTextRequest,
    user_id: str = Depends(get_current_user_id),
):
    try:
        return await polish_service.polish_text(req.text, user_id=user_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("polish_text 失败: %s", e, exc_info=True)
        raise HTTPException(503, "润色服务暂时不可用，请稍后重试")


@router.post("/polish/chat")
async def polish_chat(
    req: PolishChatRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
):
    try:
        history = [t.model_dump() for t in (req.history or [])]
        result = await polish_service.polish_chat_once(
            original=req.original,
            current_polished=req.current_polished,
            user_instruction=req.instruction,
            history=history,
            user_id=user_id,
        )
        # P1 · 后台异步抽取写作偏好（≥2 轮才会真正抽 · 见 polish_facts.MIN_HISTORY_FOR_EXTRACTION）
        next_history = list(history) + [
            {"role": "user", "content": req.instruction},
            {"role": "assistant", "content": result.get("summary", "")},
        ]
        background_tasks.add_task(
            _safe_extract_facts,
            user_id,
            req.original,
            result.get("polished", req.current_polished),
            next_history,
        )
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("polish_chat 失败: %s", e, exc_info=True)
        raise HTTPException(503, "润色服务暂时不可用，请稍后重试")


async def _safe_extract_facts(user_id: str, original: str, polished: str, history: list):
    """背景任务包装 · 任何异常吃掉，不影响主请求"""
    try:
        await polish_facts_service.extract_and_save_writing_facts(
            user_id=user_id,
            original=original,
            polished=polished,
            chat_history=history,
        )
    except Exception as e:
        logger.warning("polish facts background extraction failed: %s", e)


@router.post("/polish/cards", status_code=201)
async def create_card(
    req: PolishCardCreate,
    user_id: str = Depends(get_current_user_id),
):
    try:
        return polish_service.save_card(
            user_id=user_id,
            original=req.original,
            polished=req.polished,
            explanation=req.explanation,
            context=req.context,
            category=req.category,
            init_fsrs=req.init_fsrs,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/polish/cards")
async def list_cards(
    user_id: str = Depends(get_current_user_id),
    category: Optional[str] = Query(None),
    due: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    items = polish_service.list_cards(
        user_id=user_id,
        category=category,
        due_only=due,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "count": len(items)}


@router.delete("/polish/cards/{card_id}")
async def remove_card(
    card_id: int,
    user_id: str = Depends(get_current_user_id),
):
    if not polish_service.delete_card(card_id, user_id):
        raise HTTPException(404, "polish_card 不存在")
    return {"deleted": True, "id": card_id}


@router.post("/polish/cards/{card_id}/rate")
async def rate_card(
    card_id: int,
    req: RateRequest,
    user_id: str = Depends(get_current_user_id),
):
    try:
        return polish_service.rate_card(card_id, user_id, req.rating)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except LookupError as e:
        raise HTTPException(404, str(e))


@router.get("/polish/due")
async def due_cards(user_id: str = Depends(get_current_user_id)):
    items = polish_service.list_cards(user_id=user_id, due_only=True, limit=200)
    return {"items": items, "count": len(items)}
