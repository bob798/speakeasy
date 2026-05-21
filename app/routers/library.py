"""文章库路由 — /library/articles 及解读端点"""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.routers.auth import get_current_user_id, get_current_user_id_optional
from app.services import library_service
from app.services.explain_service import explain_text, quick_phonetic, stream_sentence_explanation
from app.services import vocab_service as _vocab_service
from app.logger import get_logger

logger = get_logger("library")

router = APIRouter(prefix="/library")


# ── Schemas ────────────────────────────────────────────────

class ImportArticleRequest(BaseModel):
    url: Optional[str] = None
    markdown: Optional[str] = None
    title: Optional[str] = None


class ExplainRequest(BaseModel):
    text: str
    kind: str                          # 'sentence' | 'word'
    context: Optional[str] = ""
    refresh: bool = False


class QuickPhoneticRequest(BaseModel):
    text: str
    item_type: Optional[str] = None    # 'word' | 'phrase' — 前端推断后传入


class StreamExplainRequest(BaseModel):
    text: str
    refresh: bool = False
    context: Optional[str] = ""
    item_type: Optional[str] = None


# ── 工具函数 ───────────────────────────────────────────────

def _resolve_item_type(text: str, explicit: Optional[str], kind: str) -> str:
    if explicit in ("word", "phrase", "sentence"):
        return explicit
    if kind == "word":
        tokens = (text or "").strip().split()
        return "word" if len(tokens) <= 1 else "phrase"
    return "sentence"


def _auto_save_library_vocab(
    user_id: str,
    article_id: int,
    text: str,
    context: Optional[str],
    item_type: str,
) -> None:
    """解读发起时占位写入 vocabulary（explanation_json=None）。失败仅 warning，不向上抛。"""
    if not text or not text.strip():
        return
    try:
        _vocab_service.save_item(
            user_id=user_id,
            source_text=text,
            translated_text="",
            direction="en2zh",
            context=context or None,
            item_type=item_type,
            source_type="library",
            source_ref=str(article_id),
            explanation_json=None,
        )
        logger.info(
            "library_vocab_auto_save user_id=%s article_id=%d text=%s item_type=%s",
            user_id, article_id, text[:40], item_type,
        )
    except Exception as e:
        logger.warning(
            "library_vocab_auto_save_failed user_id=%s article_id=%d text=%s err=%s",
            user_id, article_id, text[:40], e,
        )


def _backfill_library_vocab(
    user_id: str,
    article_id: int,
    text: str,
    explanation_json: str,
    force: bool = False,
) -> None:
    """解读完成后回填 explanation_json。失败仅 warning，不向上抛。"""
    try:
        _vocab_service.update_explanation(
            user_id=user_id,
            source_text=text,
            source_ref=str(article_id),
            explanation_json=explanation_json,
            force=force,
        )
        logger.info(
            "library_vocab_backfill user_id=%s article_id=%d text=%s",
            user_id, article_id, text[:40],
        )
    except Exception as e:
        logger.warning(
            "library_vocab_backfill_failed user_id=%s article_id=%d text=%s err=%s",
            user_id, article_id, text[:40], e,
        )


def _get_article_or_404(article_id: int, user_id: str):
    """Get article or raise 404."""
    article = library_service.get_article(article_id, user_id)
    if article is None:
        raise HTTPException(404, "文章不存在或已删除")
    return article


# ── CRUD 端点 ──────────────────────────────────────────────

@router.post("/articles", status_code=201)
async def import_article(
    req: ImportArticleRequest,
    user_id: str = Depends(get_current_user_id),
):
    """导入文章：URL 模式或粘贴 Markdown 模式。

    URL 命中已存条目 → 200 + {existing: true, ...}
    新条目 → 201 + 完整记录
    """
    if not req.url and not req.markdown:
        raise HTTPException(400, "url 或 markdown 必须提供其一")

    try:
        result = library_service.import_article(
            user_id=user_id,
            url=req.url or None,
            markdown=req.markdown or None,
            title=req.title or None,
        )
    except ValueError as e:
        err_str = str(e)
        if "fetch_failed" in err_str:
            raise HTTPException(
                400,
                detail={
                    "error": "fetch_failed",
                    "hint": "抓取失败，请改用粘贴正文模式",
                },
            )
        raise HTTPException(400, err_str)
    except Exception as e:
        logger.error("import_article error: %s", e, exc_info=True)
        raise HTTPException(503, "导入失败，请稍后重试")

    # 已存在时返回 200
    if result.get("existing"):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=200, content=result)

    return result


@router.get("/articles")
async def list_articles(
    user_id: str = Depends(get_current_user_id),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    articles = library_service.list_articles(user_id, page=page, page_size=page_size)
    return {"articles": articles, "page": page, "page_size": page_size}


@router.get("/articles/{article_id}")
async def get_article(
    article_id: int,
    user_id: str = Depends(get_current_user_id),
):
    return _get_article_or_404(article_id, user_id)


@router.delete("/articles/{article_id}")
async def delete_article(
    article_id: int,
    user_id: str = Depends(get_current_user_id),
):
    ok = library_service.delete_article(article_id, user_id)
    if not ok:
        raise HTTPException(404, "文章不存在或已删除")
    return {"deleted": True, "id": article_id}


@router.post("/articles/{article_id}/refetch")
async def refetch_article(
    article_id: int,
    user_id: str = Depends(get_current_user_id),
):
    try:
        result = library_service.refetch_article(article_id, user_id)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        err_str = str(e)
        if "paste_mode_no_url" in err_str:
            raise HTTPException(400, "粘贴正文模式的文章无法重新抓取")
        if "fetch_failed" in err_str:
            raise HTTPException(
                400,
                detail={
                    "error": "fetch_failed",
                    "hint": "抓取失败，请改用粘贴正文模式",
                },
            )
        raise HTTPException(400, err_str)
    except Exception as e:
        logger.error("refetch_article error: %s", e, exc_info=True)
        raise HTTPException(503, "重新抓取失败，请稍后重试")
    return result


# ── 解读端点 ───────────────────────────────────────────────

@router.post("/articles/{article_id}/explain")
async def library_explain(
    article_id: int,
    req: ExplainRequest,
    user_id: str = Depends(get_current_user_id),
):
    """词/句解读，发起即占位写入 vocabulary，完成后回填 explanation_json。"""
    # 确认文章存在（归属校验）
    _get_article_or_404(article_id, user_id)

    item_type = _resolve_item_type(req.text, None, req.kind)

    # 入口占位写入
    _auto_save_library_vocab(
        user_id=user_id,
        article_id=article_id,
        text=req.text,
        context=req.context or None,
        item_type=item_type,
    )

    try:
        result = await explain_text(
            text=req.text,
            kind=req.kind,
            user_id=user_id,
            context=req.context or "",
            force=req.refresh,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("library_explain error: %s", e, exc_info=True)
        raise HTTPException(503, "解读服务暂时不可用，请稍后重试")

    # 回填
    if result.get("explanation"):
        _backfill_library_vocab(
            user_id=user_id,
            article_id=article_id,
            text=req.text,
            explanation_json=json.dumps(result["explanation"], ensure_ascii=False),
            force=req.refresh,
        )

    return result


@router.post("/articles/{article_id}/explain/phonetic")
async def library_explain_phonetic(
    article_id: int,
    req: QuickPhoneticRequest,
    user_id: Optional[str] = Depends(get_current_user_id_optional),
):
    """单词 IPA 秒出；占位写入 vocabulary。"""
    if not req.text or not req.text.strip():
        raise HTTPException(400, "text is required")

    if user_id:
        item_type = _resolve_item_type(req.text, req.item_type, "word")
        _auto_save_library_vocab(
            user_id=user_id,
            article_id=article_id,
            text=req.text,
            context=None,
            item_type=item_type,
        )

    return {"phonetic": quick_phonetic(req.text)}


@router.post("/articles/{article_id}/explain/stream")
async def library_explain_stream(
    article_id: int,
    req: StreamExplainRequest,
    user_id: str = Depends(get_current_user_id),
):
    """句子解读流式接口（NDJSON）。入口占位写入，流完成后回填。"""
    if not req.text or not req.text.strip():
        raise HTTPException(400, "text is required")

    # 确认文章存在
    _get_article_or_404(article_id, user_id)

    item_type = _resolve_item_type(req.text, req.item_type, "sentence")

    # 入口占位写入
    _auto_save_library_vocab(
        user_id=user_id,
        article_id=article_id,
        text=req.text,
        context=req.context or None,
        item_type=item_type,
    )

    async def event_stream():
        collected: dict = {}
        try:
            async for line in stream_sentence_explanation(req.text, user_id, force=req.refresh):
                try:
                    evt = json.loads(line)
                except Exception:
                    evt = None
                if isinstance(evt, dict):
                    if evt.get("_cached") and isinstance(evt.get("explanation"), dict):
                        collected = dict(evt["explanation"])
                    elif "field" in evt and "value" in evt:
                        collected[evt["field"]] = evt["value"]
                yield line + "\n"
        except ValueError as e:
            yield json.dumps({"_error": str(e)}, ensure_ascii=False) + "\n"
            return
        except Exception as e:
            logger.error("library stream explain error: %s", e, exc_info=True)
            yield json.dumps({"_error": "解读服务暂时不可用"}, ensure_ascii=False) + "\n"
            return

        # 流末尾回填
        if collected:
            _backfill_library_vocab(
                user_id=user_id,
                article_id=article_id,
                text=req.text,
                explanation_json=json.dumps(collected, ensure_ascii=False),
                force=req.refresh,
            )

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
