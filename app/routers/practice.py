"""发音练习路由 — 字幕提取 + 卡片 CRUD + FSRS 评分 + 多源 TTS"""

import json
import hashlib
import os
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from app.routers.auth import get_current_user_id, get_current_user_id_optional

from app.services.subtitle_service import (
    extract_bvid, extract_page_num, fetch_bilibili_subtitles, parse_manual_text,
    resolve_short_url, extract_youtube_id, fetch_youtube_subtitles,
    fetch_audio_subtitles,
)
from app.services.practice_service import (
    create_pronunciation_cards,
    get_pronunciation_cards,
    review_pronunciation_card,
    delete_pronunciation_card,
    get_due_pronunciation_cards,
)
from app.services.explain_service import explain_text, quick_phonetic, stream_sentence_explanation
from app.services.tts_service import multi_tts
from app.models.db import engine, SubtitleSource
from sqlalchemy.orm import Session as OrmSession
from app.logger import get_logger

logger = get_logger("practice")

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────

class SubtitleRequest(BaseModel):
    url: Optional[str] = None
    text: Optional[str] = None
    cookies: Optional[str] = None   # Netscape 格式 B 站 cookies；抓取失败时前端兜底用


class CardItem(BaseModel):
    text: str
    context: str = ""
    source_url: Optional[str] = None
    source_title: Optional[str] = None


class CreateCardsRequest(BaseModel):
    items: List[CardItem]


class ReviewRequest(BaseModel):
    rating: str   # again | hard | good | easy


class ExplainRequest(BaseModel):
    text: str
    kind: str                     # 'sentence' | 'word'
    context: Optional[str] = ""   # word 模式下可提供所在句子
    refresh: bool = False         # V0.11 #8 · 跳过缓存强制重新生成


# ── 字幕缓存工具 ─────────────────────────────────────────

def _cache_subtitles(user_id: str, source_id: str, source_type: str,
                     title: str, segments: list, audio_file: str = None):
    """统一缓存字幕到 subtitle_sources，可选保存 audio_file 路径"""
    try:
        # 将 audio_file 嵌入 subtitle_json 的 metadata 中
        cache_data = {"segments": segments}
        if audio_file:
            cache_data["audio_file"] = audio_file
        with OrmSession(engine) as s:
            existing = s.query(SubtitleSource).filter_by(
                user_id=user_id, source_id=source_id,
            ).first()
            if existing:
                existing.subtitle_json = json.dumps(cache_data, ensure_ascii=False)
                existing.title = title
            else:
                s.add(SubtitleSource(
                    user_id=user_id,
                    source_id=source_id,
                    source_type=source_type,
                    title=title,
                    subtitle_json=json.dumps(cache_data, ensure_ascii=False),
                ))
            s.commit()
    except Exception as e:
        logger.warning("字幕缓存失败: %s", e)


# ── 字幕提取 ──────────────────────────────────────────────

@router.post("/practice/subtitles")
async def get_subtitles(
    req: SubtitleRequest,
    user_id: Optional[str] = Depends(get_current_user_id_optional),
):
    if req.text:
        segments = parse_manual_text(req.text)
        # 缓存手动粘贴（用 md5 作为 source_id）
        if user_id and segments:
            text_hash = hashlib.md5(req.text.strip().encode()).hexdigest()[:12]
            _cache_subtitles(user_id, f"manual_{text_hash}", "manual",
                             "手动粘贴", segments)
        return {"title": "手动粘贴", "segments": segments}

    if not req.url:
        raise HTTPException(400, "请提供 B站链接或手动粘贴文本")

    # 支持 b23.tv 短链接：先解析重定向
    resolved_url = await resolve_short_url(req.url)

    result = None
    source_id = None
    source_type = None

    # 尝试 YouTube
    yt_id = extract_youtube_id(resolved_url)
    if yt_id:
        source_id = yt_id
        source_type = "youtube"
        result = await fetch_youtube_subtitles(yt_id)
        if result.get("error") and "禁用" in result["error"]:
            logger.info("YouTube 字幕不可用，尝试音频识别: %s", yt_id)
            result = await fetch_audio_subtitles(resolved_url, cookies_text=req.cookies)
    else:
        # 尝试 Bilibili
        bvid = extract_bvid(resolved_url)
        if not bvid:
            raise HTTPException(400, "无法识别链接，支持 B站和 YouTube 链接")
        page = extract_page_num(resolved_url)
        source_id = f"{bvid}_p{page}" if page > 1 else bvid
        source_type = "bilibili"
        result = await fetch_bilibili_subtitles(bvid, page=page)
        if result.get("error") and "无字幕" in result["error"]:
            logger.info("B站字幕不可用，尝试音频识别: %s", bvid)
            result = await fetch_audio_subtitles(resolved_url, cookies_text=req.cookies)

    # 统一缓存（成功时）
    if result and "error" not in result and user_id and result.get("segments"):
        _cache_subtitles(user_id, source_id, source_type,
                         result.get("title", ""), result["segments"],
                         audio_file=result.get("audio_file"))

    return result


# ── 字幕历史 ──────────────────────────────────────────────

@router.get("/practice/subtitles")
async def list_subtitle_history(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(20, ge=1, le=100),
):
    """获取用户之前提取过的字幕列表"""
    with OrmSession(engine) as s:
        sources = (
            s.query(SubtitleSource)
            .filter_by(user_id=user_id)
            .order_by(SubtitleSource.created_at.desc())
            .limit(limit)
            .all()
        )
        return {
            "items": [
                {
                    "id": src.id,
                    "source_id": src.source_id,
                    "source_type": src.source_type,
                    "title": src.title,
                    "created_at": src.created_at.isoformat() if src.created_at else None,
                }
                for src in sources
            ],
            "count": len(sources),
        }


@router.get("/practice/subtitles/{source_id}")
async def get_cached_subtitles(
    source_id: int,
    user_id: str = Depends(get_current_user_id),
):
    """读取缓存的字幕内容"""
    with OrmSession(engine) as s:
        src = s.query(SubtitleSource).filter_by(id=source_id, user_id=user_id).first()
        if not src:
            raise HTTPException(404, "字幕记录不存在")
        raw = json.loads(src.subtitle_json)
        # 兼容新旧格式：新格式 {segments, audio_file}，旧格式直接是 [segments]
        if isinstance(raw, dict) and "segments" in raw:
            segments = raw["segments"]
            audio_file = raw.get("audio_file")
        else:
            segments = raw
            audio_file = None
        result = {
            "title": src.title,
            "source_type": src.source_type,
            "segments": segments,
        }
        if audio_file:
            result["audio_file"] = audio_file
        return result


# ── 卡片 CRUD ────────────────────────────────────────────

@router.post("/practice/cards", status_code=201)
async def create_cards(
    req: CreateCardsRequest,
    user_id: str = Depends(get_current_user_id),
):
    items = [item.dict() for item in req.items]
    result = create_pronunciation_cards(user_id, items)
    return result


@router.get("/practice/cards")
async def list_cards(
    user_id: str = Depends(get_current_user_id),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    cards = get_pronunciation_cards(user_id, status=status, limit=limit, offset=offset)
    return {"cards": cards, "count": len(cards)}


@router.post("/practice/cards/{card_id}/review")
async def review_card_endpoint(
    card_id: int,
    req: ReviewRequest,
    user_id: str = Depends(get_current_user_id),
):
    result = review_pronunciation_card(card_id, user_id, req.rating)
    if result is None:
        raise HTTPException(404, "卡片不存在或评分无效")
    return result


@router.delete("/practice/cards/{card_id}")
async def delete_card(
    card_id: int,
    user_id: str = Depends(get_current_user_id),
):
    ok = delete_pronunciation_card(card_id, user_id)
    if not ok:
        raise HTTPException(404, "卡片不存在")
    return {"deleted": True, "id": card_id}


# ── 到期复习 ─────────────────────────────────────────────

@router.get("/practice/due")
async def get_due_cards(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(10, ge=1, le=50),
):
    cards = get_due_pronunciation_cards(user_id, limit=limit)
    return {"cards": cards, "count": len(cards)}


# ── 句子/单词解读 ─────────────────────────────────────────

@router.post("/practice/explain")
async def practice_explain(
    req: ExplainRequest,
    user_id: str = Depends(get_current_user_id),
):
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
        logger.error("解读失败: %s", e, exc_info=True)
        raise HTTPException(503, "解读服务暂时不可用，请稍后重试")
    return result


class QuickPhoneticRequest(BaseModel):
    text: str


@router.post("/practice/explain/phonetic")
async def practice_explain_phonetic(req: QuickPhoneticRequest):
    """单词 IPA 本地秒出；未知词 phonetic=null，前端退回等 LLM 结果。"""
    if not req.text or not req.text.strip():
        raise HTTPException(400, "text is required")
    return {"phonetic": quick_phonetic(req.text)}


class StreamExplainRequest(BaseModel):
    text: str
    refresh: bool = False         # V0.11 #8


@router.post("/practice/explain/stream")
async def practice_explain_stream(
    req: StreamExplainRequest,
    user_id: str = Depends(get_current_user_id),
):
    """句子解读流式接口（NDJSON，每行一个 JSON 事件）。

    事件形式：
      {"field": "...", "value": ...}
      {"_cached": true, "cefr_level": "B1", "explanation": {...}}     # 缓存命中
      {"_done": true, "cefr_level": "B1"}                              # 流结束
      {"_error": "..."}                                                # 错误
    """
    if not req.text or not req.text.strip():
        raise HTTPException(400, "text is required")

    async def event_stream():
        try:
            async for line in stream_sentence_explanation(req.text, user_id, force=req.refresh):
                yield line + "\n"
        except ValueError as e:
            import json as _json
            yield _json.dumps({"_error": str(e)}, ensure_ascii=False) + "\n"
        except Exception as e:
            import json as _json
            logger.error("stream 解读失败: %s", e, exc_info=True)
            yield _json.dumps({"_error": "解读服务暂时不可用"}, ensure_ascii=False) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


# ── 多源 TTS ─────────────────────────────────────────────

class PracticeTTSRequest(BaseModel):
    text: str = ""
    provider: str = ""       # azure | edge | openai | original（空=使用默认）
    voice: str = "jenny"
    speed: str = "+0%"
    segment_path: Optional[str] = None


@router.post("/practice/tts")
async def practice_tts(req: PracticeTTSRequest):
    """Multi-source TTS with disk caching"""
    import time
    import uuid
    import logging
    tts_logger = logging.getLogger("practice.tts")
    rid = uuid.uuid4().hex[:8]
    t0 = time.time()
    text_len = len(req.text or "")
    tts_logger.info(
        "[tts %s] start provider=%s voice=%s speed=%s text_len=%d preview=%r",
        rid, req.provider or "(default)", req.voice, req.speed, text_len,
        (req.text or "")[:40],
    )

    if req.provider == "original":
        if req.segment_path and os.path.exists(req.segment_path):
            with open(req.segment_path, "rb") as f:
                data = f.read()
            tts_logger.info("[tts %s] ok provider=original bytes=%d ms=%d",
                            rid, len(data), int((time.time()-t0)*1000))
            return Response(content=data, media_type="audio/mpeg")
        tts_logger.warning("[tts %s] 404 segment_path missing: %s", rid, req.segment_path)
        raise HTTPException(404, "Original audio segment not found")

    if not req.text:
        tts_logger.warning("[tts %s] 400 empty text", rid)
        raise HTTPException(400, "text is required")

    try:
        provider = req.provider if req.provider else None  # None = 使用默认
        audio, media_type = await multi_tts(req.text, provider, req.voice, req.speed)
        tts_logger.info(
            "[tts %s] ok provider=%s bytes=%d ms=%d",
            rid, req.provider or "(default)", len(audio),
            int((time.time()-t0)*1000),
        )
        return Response(
            content=audio,
            media_type=media_type,
            headers={"Cache-Control": "public, max-age=3600"},
        )
    except ValueError as e:
        tts_logger.warning("[tts %s] 400 ValueError: %s", rid, e)
        raise HTTPException(400, str(e))
    except Exception as e:
        tts_logger.exception("[tts %s] 503 %s: %s", rid, type(e).__name__, e)
        raise HTTPException(503, f"TTS failed: {e}")
