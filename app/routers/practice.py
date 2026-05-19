"""发音练习路由 — 字幕提取 + 卡片 CRUD + FSRS 评分 + 多源 TTS"""

import json
import hashlib
import os
from typing import Optional, List, Dict

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
from app.services import vocab_service as _vocab_service

logger = get_logger("practice")

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────

class SubtitleRequest(BaseModel):
    url: Optional[str] = None
    text: Optional[str] = None
    cookies: Optional[str] = None   # Netscape 格式 B 站 cookies；抓取失败时前端兜底用


class SegmentItem(BaseModel):
    content: str
    # from/to 可选，脚本导入的文本没有时间戳
    start: Optional[float] = None    # 别名：from 是 Python 保留字
    end: Optional[float] = None


class SourceImportRequest(BaseModel):
    """外部脚本批量导入 subtitle source"""
    source_id: str                        # 唯一标识，如 voa_8003108
    source_type: str = "external"         # voa / podcast / external ...
    title: str
    segments: List[SegmentItem]
    source_url: Optional[str] = None      # 原文链接（仅存档）
    published_at: Optional[str] = None    # ISO 格式发布时间，用于按原始发布顺序排序


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
    kind: str                                # 'sentence' | 'word'
    context: Optional[str] = ""              # word 模式下可提供所在句子
    refresh: bool = False                    # V0.11 #8 · 跳过缓存强制重新生成
    # V0.8 自动入库：可选，传了就在解读入口自动写 vocabulary
    source_type: Optional[str] = None        # 'bbc_eaw' | 'translate' | ...
    source_ref: Optional[str] = None         # 例: BBC episode slug
    item_type: Optional[str] = None          # 'word' | 'phrase' | 'sentence'，缺省由 kind 推断


# ── 字幕缓存工具 ─────────────────────────────────────────

def _cache_subtitles(user_id: str, source_id: str, source_type: str,
                     title: str, segments: list, audio_file: str = None,
                     created_at=None):
    """统一缓存字幕到 subtitle_sources，可选保存 audio_file 路径 / 覆盖 created_at"""
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
                if created_at:
                    existing.created_at = created_at
            else:
                src = SubtitleSource(
                    user_id=user_id,
                    source_id=source_id,
                    source_type=source_type,
                    title=title,
                    subtitle_json=json.dumps(cache_data, ensure_ascii=False),
                )
                if created_at:
                    src.created_at = created_at
                s.add(src)
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
            .order_by(SubtitleSource.created_at.desc(), SubtitleSource.id.desc())
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


# ── 外部导入 ─────────────────────────────────────────────

@router.post("/practice/sources/import", status_code=201)
async def import_source(
    req: SourceImportRequest,
    user_id: str = Depends(get_current_user_id),
):
    """脚本/工具批量导入 subtitle source（upsert），Practice 页面「📚 历史」可见。"""
    segments = [
        {
            "content": seg.content,
            "from": seg.start or i * 10.0,
            "to": seg.end or (i + 1) * 10.0,
        }
        for i, seg in enumerate(req.segments)
    ]
    # 解析发布时间（用于按原始发布顺序排序）
    pub_dt = None
    if req.published_at:
        from datetime import datetime, timezone
        try:
            pub_dt = datetime.fromisoformat(req.published_at.replace("Z", "+00:00"))
        except ValueError:
            pass

    _cache_subtitles(user_id, req.source_id, req.source_type,
                     req.title, segments, created_at=pub_dt)
    return {
        "source_id": req.source_id,
        "title": req.title,
        "segments_count": len(segments),
    }


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


def _resolve_item_type(text: str, explicit: Optional[str], kind: str) -> str:
    """优先显式 item_type，否则按 kind 推断；word 多 token 视作 phrase。"""
    if explicit in ("word", "phrase", "sentence"):
        return explicit
    if kind == "word":
        tokens = (text or "").strip().split()
        return "word" if len(tokens) <= 1 else "phrase"
    return "sentence"


def _auto_save_vocab(
    user_id: Optional[str],
    text: str,
    context: Optional[str],
    source_type: Optional[str],
    source_ref: Optional[str],
    item_type: str,
) -> bool:
    """解读发起时占位写入 vocabulary（explanation_json=None）。

    跳过条件：未登录 / 未提供 source_type / text 为空。
    写入失败：logger.warning，绝不向上抛。

    注：save_item 命中已存在记录时不更新任何字段（vocab_service.py L77–83）。
    这意味着同一 (user_id, source_text, source_ref) 的 item_type 由**第一次**调用决定，
    后续调用即使 item_type 不同也不会更新。前端必须确保 phonetic 与后续 explain 使用一致的 item_type。
    """
    if not user_id or not source_type or not text or not text.strip():
        return False
    try:
        _vocab_service.save_item(
            user_id=user_id,
            source_text=text,
            translated_text="",
            direction="en2zh",
            context=context or None,
            item_type=item_type,
            source_type=source_type,
            source_ref=source_ref,
            explanation_json=None,
        )
        logger.info(
            "vocab_auto_save_attempt user_id=%s text=%s source_type=%s source_ref=%s item_type=%s",
            user_id, text[:40], source_type, source_ref, item_type,
        )
        return True
    except Exception as e:
        logger.warning(
            "vocab_auto_save_failed user_id=%s text=%s err=%s",
            user_id, text[:40], e,
        )
        return False


# ── 句子/单词解读 ─────────────────────────────────────────

@router.post("/practice/explain")
async def practice_explain(
    req: ExplainRequest,
    user_id: str = Depends(get_current_user_id),
):
    # 入口占位写入
    item_type = _resolve_item_type(req.text, req.item_type, req.kind)
    _auto_save_vocab(
        user_id=user_id, text=req.text, context=req.context,
        source_type=req.source_type, source_ref=req.source_ref,
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
        logger.error("解读失败: %s", e, exc_info=True)
        raise HTTPException(503, "解读服务暂时不可用，请稍后重试")

    # 解读完成回填（refresh=True 时 force-overwrite，否则仅 NULL 写入）
    if req.source_type and result.get("explanation"):
        try:
            _vocab_service.update_explanation(
                user_id=user_id,
                source_text=req.text,
                source_ref=req.source_ref,
                explanation_json=json.dumps(result["explanation"], ensure_ascii=False),
                force=req.refresh,
            )
        except Exception as e:
            logger.warning("vocab_backfill_failed user_id=%s err=%s", user_id, e)

    return result


class QuickPhoneticRequest(BaseModel):
    text: str
    source_type: Optional[str] = None
    source_ref: Optional[str] = None
    item_type: Optional[str] = None         # 前端推断后传入，避免与后续 explain 不一致


@router.post("/practice/explain/phonetic")
async def practice_explain_phonetic(
    req: QuickPhoneticRequest,
    user_id: Optional[str] = Depends(get_current_user_id_optional),
):
    """单词 IPA 本地秒出；未知词 phonetic=null，前端退回等 LLM 结果。"""
    if not req.text or not req.text.strip():
        raise HTTPException(400, "text is required")
    # 登录态 + 带 source 时占位入库；phonetic 不产生完整解读，不回填
    if user_id and req.source_type:
        item_type = _resolve_item_type(req.text, req.item_type, "word")
        _auto_save_vocab(
            user_id=user_id, text=req.text, context=None,
            source_type=req.source_type, source_ref=req.source_ref,
            item_type=item_type,
        )
    return {"phonetic": quick_phonetic(req.text)}


class StreamExplainRequest(BaseModel):
    text: str
    refresh: bool = False                    # V0.11 #8
    # V0.8 自动入库
    source_type: Optional[str] = None
    source_ref: Optional[str] = None
    item_type: Optional[str] = None
    context: Optional[str] = ""              # 句子级 context（如所在段落）


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

    # 入口占位写入
    item_type = _resolve_item_type(req.text, req.item_type, "sentence")
    _auto_save_vocab(
        user_id=user_id, text=req.text, context=req.context,
        source_type=req.source_type, source_ref=req.source_ref,
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
            logger.error("stream 解读失败: %s", e, exc_info=True)
            yield json.dumps({"_error": "解读服务暂时不可用"}, ensure_ascii=False) + "\n"
            return

        # 流末尾回填（best-effort）：
        # · 如果客户端中途断开，Starlette 抛 ClientDisconnect → generator 不会到这里
        #   → pending 留存，由前端 /vocabulary 重拉路径兜底（这是 by design）
        # · refresh=True 时 force-overwrite 已有 explanation_json
        if req.source_type and collected:
            try:
                _vocab_service.update_explanation(
                    user_id=user_id,
                    source_text=req.text,
                    source_ref=req.source_ref,
                    explanation_json=json.dumps(collected, ensure_ascii=False),
                    force=req.refresh,
                )
            except Exception as e:
                logger.warning("vocab_stream_backfill_failed user_id=%s err=%s", user_id, e)

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


# ── 多源 TTS ─────────────────────────────────────────────

class PracticeTTSRequest(BaseModel):
    text: str = ""
    provider: str = ""       # azure | edge | openai | original（空=使用默认）
    voice: str = "jenny"
    speed: str = "+0%"
    segment_path: Optional[str] = None
    phoneme_map: Optional[Dict[str, str]] = None   # IPA 纠音映射，传入则后端走 Azure


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
        audio, media_type, meta = await multi_tts(
            req.text, provider, req.voice, req.speed, req.phoneme_map,
        )
        tts_logger.info(
            "[tts %s] ok provider=%s(eff=%s) bytes=%d phoneme_ignored=%s fallback=%s ms=%d",
            rid, req.provider or "(default)", meta.get("provider_used"),
            len(audio), meta.get("phoneme_ignored"), meta.get("fallback"),
            int((time.time() - t0) * 1000),
        )
        headers = {
            "Cache-Control": "public, max-age=3600",
            "X-TTS-Provider-Used": str(meta.get("provider_used") or ""),
        }
        if meta.get("phoneme_ignored"):
            headers["X-TTS-Phoneme-Ignored"] = "1"
        if meta.get("fallback"):
            headers["X-TTS-Fallback"] = str(meta["fallback"])
        return Response(
            content=audio,
            media_type=media_type,
            headers=headers,
        )
    except ValueError as e:
        tts_logger.warning("[tts %s] 400 ValueError: %s", rid, e)
        raise HTTPException(400, str(e))
    except Exception as e:
        tts_logger.exception("[tts %s] 503 %s: %s", rid, type(e).__name__, e)
        raise HTTPException(503, f"TTS failed: {e}")
