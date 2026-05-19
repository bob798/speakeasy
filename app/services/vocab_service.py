"""生词本服务 — 句子/单词/短语 + FSRS 调度

P1 实现 4 个能力：
  - save_item: upsert，唯一键 (user_id, source_text, source_ref)
  - list_items: 支持 type / source_ref / due / 分页
  - delete_item: 软删
  - rate_item: FSRS 评分推进 due
"""
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.exc import IntegrityError

from app.models.db import engine, Vocabulary
from app.services.fsrs_utils import (
    create_card,
    review_card,
    is_due,
    get_due_date,
    RATING_MAP,
)
from app.logger import get_logger

logger = get_logger("vocab_service")

VALID_ITEM_TYPES = {"word", "phrase", "sentence"}
VALID_SOURCE_TYPES = {"translate", "bbc_eaw", "practice", "chat"}


def _to_dict(v: Vocabulary) -> Dict:
    return {
        "id": v.id,
        "user_id": v.user_id,
        "source_text": v.source_text,
        "translated_text": v.translated_text,
        "direction": v.direction,
        "context": v.context,
        "item_type": v.item_type,
        "source_type": v.source_type,
        "source_ref": v.source_ref,
        "explanation_json": v.explanation_json,
        "status": v.status,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "last_reviewed_at": v.last_reviewed_at.isoformat() if v.last_reviewed_at else None,
        "due": get_due_date(v.fsrs_card_data) if v.fsrs_card_data else None,
        "is_due": is_due(v.fsrs_card_data) if v.fsrs_card_data else True,
    }


def save_item(
    user_id: str,
    source_text: str,
    translated_text: str = "",
    direction: str = "en2zh",
    context: Optional[str] = None,
    item_type: str = "sentence",
    source_type: str = "translate",
    source_ref: Optional[str] = None,
    explanation_json: Optional[str] = None,
) -> Dict:
    """新增或返回已存在条目（去重键: user_id + source_text + source_ref）"""
    if not source_text or not source_text.strip():
        raise ValueError("source_text 不能为空")
    if item_type not in VALID_ITEM_TYPES:
        raise ValueError(f"item_type 非法: {item_type}")
    if source_type not in VALID_SOURCE_TYPES:
        raise ValueError(f"source_type 非法: {source_type}")

    with OrmSession(engine) as s:
        # 先查重
        existing = (
            s.query(Vocabulary)
            .filter_by(user_id=user_id, source_text=source_text, source_ref=source_ref)
            .first()
        )
        if existing:
            # 复活已删除的；其它字段不覆盖（避免后写吞掉前面的解释）
            if existing.status == "deleted":
                existing.status = "active"
                s.commit()
                s.refresh(existing)
            return _to_dict(existing)

        v = Vocabulary(
            user_id=user_id,
            source_text=source_text,
            translated_text=translated_text or "",
            direction=direction,
            context=context,
            item_type=item_type,
            source_type=source_type,
            source_ref=source_ref,
            explanation_json=explanation_json,
            fsrs_card_data=create_card(),
            status="active",
        )
        s.add(v)
        try:
            s.commit()
        except IntegrityError:
            # 并发去重兜底
            s.rollback()
            existing = (
                s.query(Vocabulary)
                .filter_by(user_id=user_id, source_text=source_text, source_ref=source_ref)
                .first()
            )
            if existing:
                return _to_dict(existing)
            raise
        s.refresh(v)
        return _to_dict(v)


def update_explanation(
    user_id: str,
    source_text: str,
    source_ref: Optional[str],
    explanation_json: str,
    force: bool = False,
) -> bool:
    """回填 explanation_json。

    默认仅在当前 explanation_json 为 NULL 时写入（保护已有解释不被首写覆盖）。
    force=True 时强制覆盖（用于 refresh=True 路径，用户主动重生）。
    软删条目也回填（保留历史，下次复活带完整数据）。
    找不到记录返回 False，不抛异常。
    """
    with OrmSession(engine) as s:
        v = (
            s.query(Vocabulary)
            .filter_by(user_id=user_id, source_text=source_text, source_ref=source_ref)
            .first()
        )
        if not v:
            logger.warning(
                "vocab_explanation_backfill_miss user_id=%s source_text=%s source_ref=%s",
                user_id, source_text, source_ref,
            )
            return False
        if v.explanation_json and not force:
            return False
        v.explanation_json = explanation_json
        s.commit()
        logger.info(
            "vocab_explanation_backfill user_id=%s id=%s len=%d force=%s",
            user_id, v.id, len(explanation_json), force,
        )
        return True


def list_items(
    user_id: str,
    item_type: Optional[str] = None,
    source_ref: Optional[str] = None,
    due_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict]:
    with OrmSession(engine) as s:
        q = s.query(Vocabulary).filter_by(user_id=user_id, status="active")
        if item_type:
            q = q.filter_by(item_type=item_type)
        if source_ref:
            q = q.filter_by(source_ref=source_ref)
        rows = q.order_by(Vocabulary.created_at.desc()).all()

        items = [_to_dict(v) for v in rows]
        if due_only:
            items = [it for it in items if it["is_due"]]
        return items[offset : offset + limit]


def delete_item(vocab_id: int, user_id: str) -> bool:
    with OrmSession(engine) as s:
        v = s.query(Vocabulary).filter_by(id=vocab_id, user_id=user_id).first()
        if not v:
            return False
        v.status = "deleted"
        s.commit()
        return True


def rate_item(vocab_id: int, user_id: str, rating_str: str) -> Dict:
    rating_str = (rating_str or "").lower()
    if rating_str not in RATING_MAP:
        raise ValueError(f"rating 必须为 again/hard/good/easy，收到: {rating_str}")
    with OrmSession(engine) as s:
        v = s.query(Vocabulary).filter_by(id=vocab_id, user_id=user_id, status="active").first()
        if not v:
            raise LookupError("条目不存在或已删除")
        if not v.fsrs_card_data:
            v.fsrs_card_data = create_card()
        new_json, card_dict = review_card(v.fsrs_card_data, RATING_MAP[rating_str])
        v.fsrs_card_data = new_json
        v.last_reviewed_at = datetime.utcnow()
        s.commit()
        s.refresh(v)
        return {"id": v.id, "due": card_dict.get("due"), "item": _to_dict(v)}


def bulk_save_from_bbc(
    user_id: str,
    slug: str,
    segments: List[Dict],
) -> int:
    """BBC 文章答错的句子批量入库 · P3 联动用。

    segments: [{text, translated_text?, context?}]
    返回新增（非已存在）的条数。
    """
    new_count = 0
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        item = save_item(
            user_id=user_id,
            source_text=text,
            translated_text=seg.get("translated_text", ""),
            direction="en2zh",
            context=seg.get("context"),
            item_type="sentence",
            source_type="bbc_eaw",
            source_ref=slug,
        )
        # 粗略判定：刚创建的 last_reviewed_at 必为 None
        if item.get("last_reviewed_at") is None:
            new_count += 1
    return new_count
