"""生词本路由 — V0.10

POST   /vocab            创建/复活
GET    /vocab            列表（item_type / source_ref / due / 分页）
DELETE /vocab/{id}       软删
POST   /vocab/{id}/rate  FSRS 评分

旧 /translate/vocabulary 改为薄代理（保兼容）。
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from app.routers.auth import get_current_user_id
from app.services.vocab_service import (
    save_item,
    list_items,
    delete_item,
    rate_item,
)
from app.logger import get_logger

logger = get_logger("vocab")

router = APIRouter()


class VocabCreate(BaseModel):
    source_text: str
    translated_text: str = ""
    direction: str = "en2zh"
    context: Optional[str] = None
    item_type: str = "sentence"           # word | phrase | sentence
    source_type: str = "translate"        # translate | article | practice | chat
    source_ref: Optional[str] = None
    explanation_json: Optional[str] = None
    series: Optional[str] = None          # bbc_eaw | voa | ... (when source_type='article')


class VocabRate(BaseModel):
    rating: str  # again | hard | good | easy


@router.post("/vocab", status_code=201)
async def create_vocab(req: VocabCreate, user_id: str = Depends(get_current_user_id)):
    try:
        return save_item(
            user_id=user_id,
            source_text=req.source_text,
            translated_text=req.translated_text,
            direction=req.direction,
            context=req.context,
            item_type=req.item_type,
            source_type=req.source_type,
            source_ref=req.source_ref,
            explanation_json=req.explanation_json,
            series=req.series,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/vocab")
async def get_vocab(
    user_id: str = Depends(get_current_user_id),
    item_type: Optional[str] = Query(None),
    source_ref: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None),
    due: bool = Query(False),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    items = list_items(
        user_id=user_id,
        item_type=item_type,
        source_ref=source_ref,
        source_type=source_type,
        due_only=due,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "count": len(items)}


@router.delete("/vocab/{vocab_id}")
async def remove_vocab(vocab_id: int, user_id: str = Depends(get_current_user_id)):
    if not delete_item(vocab_id, user_id):
        raise HTTPException(404, "生词本条目不存在")
    return {"deleted": True, "id": vocab_id}


@router.post("/vocab/{vocab_id}/rate")
async def rate_vocab(
    vocab_id: int,
    req: VocabRate,
    user_id: str = Depends(get_current_user_id),
):
    try:
        return rate_item(vocab_id, user_id, req.rating)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except LookupError as e:
        raise HTTPException(404, str(e))
