"""翻译路由 — 双向翻译 + 生词本 CRUD（生词本需要登录）"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

from app.services.translate_service import translate_text, VALID_DIRECTIONS
from app.services.vocab_service import save_item, list_items, delete_item, update_translated_text
from app.routers.auth import get_current_user_id, get_current_user_id_optional
from app.logger import get_logger

logger = get_logger("translate")

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────

class TranslateRequest(BaseModel):
    text: str
    direction: str   # 'zh2en' | 'en2zh'


class VocabularyCreate(BaseModel):
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


# ── 翻译（匿名可用，登录自动入生词本）──────────────────

@router.post("/translate/text")
async def do_translate(
    req: TranslateRequest,
    user_id: Optional[str] = Depends(get_current_user_id_optional),
):
    if len(req.text.strip()) == 0:
        raise HTTPException(400, "输入文本不能为空")
    if len(req.text.strip()) > 1000:
        raise HTTPException(400, "输入文本不能超过 1000 字符")

    # direction 白名单校验（提前到占位写入之前）
    if req.direction not in VALID_DIRECTIONS:
        raise HTTPException(400, f"无效的翻译方向: {req.direction}，可选值: zh2en / en2zh")

    # 登录态：占位写入 vocabulary
    vocab_id = None
    if user_id:
        try:
            item = save_item(
                user_id=user_id,
                source_text=req.text,
                translated_text="",
                direction=req.direction,
                item_type="sentence",
                source_type="translate",
                source_ref=None,
            )
            vocab_id = item["id"]
        except Exception as e:
            logger.warning("translate_placeholder_save_fail user=%s err=%s", user_id, e)
            vocab_id = None

    try:
        translated = await translate_text(req.text, req.direction)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("翻译失败: %s", e, exc_info=True)
        raise HTTPException(503, "翻译服务暂时不可用，请稍后重试")

    # 登录态：回填 translated_text
    if user_id and vocab_id and translated:
        try:
            update_translated_text(
                user_id=user_id,
                source_text=req.text,
                source_ref=None,
                translated_text=translated,
                force=True,
            )
        except Exception as e:
            logger.warning(
                "translate_backfill_fail user=%s vocab_id=%s err=%s",
                user_id, vocab_id, e,
            )

    return {
        "translated_text": translated,
        "saved_to_vocab": bool(vocab_id),
        "vocab_id": vocab_id,
    }


# ── 生词本 CRUD（登录才能用）──────────────────────────────

# 旧端点：薄代理到新 vocab_service（V0.10 起统一走 /vocab）

@router.post("/translate/vocabulary", status_code=201)
async def create_vocabulary(
    req: VocabularyCreate,
    user_id: str = Depends(get_current_user_id),
):
    try:
        return save_item(
            user_id=user_id,
            source_text=req.source_text,
            translated_text=req.translated_text,
            direction=req.direction,
            context=req.context,
            item_type="sentence",
            source_type="translate",
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/translate/vocabulary")
async def get_vocabulary(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    items = list_items(user_id=user_id, limit=limit, offset=offset)
    return {"items": items, "count": len(items)}


@router.delete("/translate/vocabulary/{vocab_id}")
async def remove_vocabulary(
    vocab_id: int,
    user_id: str = Depends(get_current_user_id),
):
    ok = delete_item(vocab_id, user_id)
    if not ok:
        raise HTTPException(404, "生词本条目不存在")
    return {"deleted": True, "id": vocab_id}
