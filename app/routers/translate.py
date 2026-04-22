"""翻译路由 — 双向翻译 + 生词本 CRUD"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.translate_service import (
    translate_text,
    save_vocabulary,
    list_vocabulary,
    delete_vocabulary,
)
from app.logger import get_logger

logger = get_logger("translate")

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────

class TranslateRequest(BaseModel):
    text: str
    direction: str   # 'zh2en' | 'en2zh'


class VocabularyCreate(BaseModel):
    user_id: str
    source_text: str
    translated_text: str
    direction: str
    context: Optional[str] = None


class VocabularyResponse(BaseModel):
    id: int
    user_id: str
    source_text: str
    translated_text: str
    direction: str
    context: Optional[str]
    status: str
    created_at: Optional[str]


# ── 翻译 ──────────────────────────────────────────────────

@router.post("/translate/text")
async def do_translate(req: TranslateRequest):
    if len(req.text.strip()) == 0:
        raise HTTPException(400, "输入文本不能为空")
    if len(req.text.strip()) > 1000:
        raise HTTPException(400, "输入文本不能超过 1000 字符")

    try:
        translated = await translate_text(req.text, req.direction)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("翻译失败: %s", e, exc_info=True)
        raise HTTPException(503, "翻译服务暂时不可用，请稍后重试")

    return {"translated_text": translated}


# ── 生词本 CRUD ───────────────────────────────────────────

@router.post("/translate/vocabulary", status_code=201)
async def create_vocabulary(req: VocabularyCreate):
    try:
        item = save_vocabulary(
            user_id=req.user_id,
            source_text=req.source_text,
            translated_text=req.translated_text,
            direction=req.direction,
            context=req.context,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return item


@router.get("/translate/vocabulary")
async def get_vocabulary(
    user_id: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    items = list_vocabulary(user_id=user_id, limit=limit, offset=offset)
    return {"items": items, "count": len(items)}


@router.delete("/translate/vocabulary/{vocab_id}")
async def remove_vocabulary(vocab_id: int, user_id: str = Query(...)):
    ok = delete_vocabulary(vocab_id, user_id)
    if not ok:
        raise HTTPException(404, "生词本条目不存在")
    return {"deleted": True, "id": vocab_id}
