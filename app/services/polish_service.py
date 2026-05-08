"""写作教练服务 — V0.11

公共能力：
  - polish_text: 一次性润色（结构化输出 · diff + 解释）
  - polish_chat_once: 单轮对话润色（基于上一轮结果 + 用户指令）
  - save_card / list_cards / delete_card: polish_cards CRUD
"""
import json
import re
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.exc import IntegrityError

from app.models.db import engine, PolishCard
from app.prompts.polish import POLISH_SYSTEM_PROMPT, POLISH_CHAT_SYSTEM_PROMPT
from app.services.model_client import get_client
from app.services.fsrs_utils import (
    create_card,
    review_card,
    is_due,
    get_due_date,
    RATING_MAP,
)
from app.services.polish_facts import build_polish_addon
from app.logger import get_logger

logger = get_logger("polish_service")

VALID_CATEGORIES = {"grammar", "word_choice", "style", "structure"}
MAX_INPUT_LEN = 2000


def _strip_code_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)
    return raw.strip()


async def polish_text(text: str, user_id: Optional[str] = None) -> Dict:
    """一次性润色 · 返回 {polished, segments, overall_note}"""
    if not text or not text.strip():
        raise ValueError("输入文本不能为空")
    if len(text) > MAX_INPUT_LEN:
        raise ValueError(f"输入文本不能超过 {MAX_INPUT_LEN} 字符")

    # P1 · 注入用户偏好 + 高频错误（如有）
    system = POLISH_SYSTEM_PROMPT
    if user_id:
        addon = build_polish_addon(user_id)
        if addon:
            system = POLISH_SYSTEM_PROMPT + "\n" + addon

    client = get_client()
    raw = await client.complete(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ],
        max_tokens=2000,
    )
    cleaned = _strip_code_fences(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("polish 返回非 JSON: %s", cleaned[:200])
        # 兜底：把原文当 polished 返回，不报错
        return {"polished": text, "segments": [], "overall_note": ""}

    polished = data.get("polished") or text
    segments = data.get("segments") or []
    if not isinstance(segments, list):
        segments = []
    # 过滤非法 category
    cleaned_segments = []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        cat = seg.get("category") or ""
        if cat and cat not in VALID_CATEGORIES:
            cat = ""
        cleaned_segments.append({
            "original": str(seg.get("original", "")),
            "replacement": str(seg.get("replacement", "")),
            "explanation": str(seg.get("explanation", "")),
            "category": cat,
        })
    return {
        "polished": str(polished),
        "segments": cleaned_segments,
        "overall_note": str(data.get("overall_note") or ""),
    }


async def polish_chat_once(
    original: str,
    current_polished: str,
    user_instruction: str,
    history: Optional[List[Dict]] = None,
    user_id: Optional[str] = None,
) -> Dict:
    """根据用户指令在 current_polished 基础上再调一轮 · 返回 {polished, summary}"""
    if not user_instruction.strip():
        raise ValueError("指令不能为空")

    system = POLISH_CHAT_SYSTEM_PROMPT
    if user_id:
        addon = build_polish_addon(user_id)
        if addon:
            system = POLISH_CHAT_SYSTEM_PROMPT + "\n" + addon

    messages = [{"role": "system", "content": system}]
    # 起始上下文：原文 + 当前版本
    messages.append(
        {
            "role": "user",
            "content": (
                f"原文（参考用，不要直接返回）：\n{original}\n\n"
                f"当前版本：\n{current_polished}\n\n"
                f"指令：{user_instruction}"
            ),
        }
    )
    # 多轮历史（如有）
    for h in (history or []):
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})

    client = get_client()
    raw = await client.complete(messages, max_tokens=2000)
    cleaned = _strip_code_fences(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("polish_chat 返回非 JSON: %s", cleaned[:200])
        return {"polished": current_polished, "summary": ""}

    return {
        "polished": str(data.get("polished") or current_polished),
        "summary": str(data.get("summary") or ""),
    }


# ── polish_cards CRUD（FSRS 字段建表已就位，P0 不主动调度，P1 启用）──

def _to_dict(c: PolishCard) -> Dict:
    return {
        "id": c.id,
        "user_id": c.user_id,
        "original": c.original,
        "polished": c.polished,
        "explanation": c.explanation,
        "context": c.context,
        "category": c.category,
        "status": c.status,
        "review_count": c.review_count,
        "last_reviewed_at": c.last_reviewed_at.isoformat() if c.last_reviewed_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "due": get_due_date(c.fsrs_card_data) if c.fsrs_card_data else None,
        "is_due": is_due(c.fsrs_card_data) if c.fsrs_card_data else True,
    }


def save_card(
    user_id: str,
    original: str,
    polished: str,
    explanation: str = "",
    context: Optional[str] = None,
    category: str = "",
    init_fsrs: bool = True,   # P1 · 默认入 FSRS 队列，方便后续到期复习
) -> Dict:
    if not original.strip() or not polished.strip():
        raise ValueError("original / polished 不能为空")
    if category and category not in VALID_CATEGORIES:
        raise ValueError(f"category 非法: {category}")
    with OrmSession(engine) as s:
        existing = (
            s.query(PolishCard)
            .filter_by(user_id=user_id, original=original, polished=polished)
            .first()
        )
        if existing:
            if existing.status == "deleted":
                existing.status = "active"
                s.commit()
                s.refresh(existing)
            return _to_dict(existing)

        card = PolishCard(
            user_id=user_id,
            original=original,
            polished=polished,
            explanation=explanation,
            context=context,
            category=category,
            status="active",
            fsrs_card_data=create_card() if init_fsrs else "",
        )
        s.add(card)
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            existing = (
                s.query(PolishCard)
                .filter_by(user_id=user_id, original=original, polished=polished)
                .first()
            )
            if existing:
                return _to_dict(existing)
            raise
        s.refresh(card)
        return _to_dict(card)


def list_cards(
    user_id: str,
    category: Optional[str] = None,
    due_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict]:
    with OrmSession(engine) as s:
        q = s.query(PolishCard).filter_by(user_id=user_id, status="active")
        if category:
            q = q.filter_by(category=category)
        rows = q.order_by(PolishCard.created_at.desc()).all()
        items = [_to_dict(r) for r in rows]
        if due_only:
            items = [it for it in items if it["is_due"]]
        return items[offset : offset + limit]


def delete_card(card_id: int, user_id: str) -> bool:
    with OrmSession(engine) as s:
        c = s.query(PolishCard).filter_by(id=card_id, user_id=user_id).first()
        if not c:
            return False
        c.status = "deleted"
        s.commit()
        return True


def rate_card(card_id: int, user_id: str, rating_str: str) -> Dict:
    rating_str = (rating_str or "").lower()
    if rating_str not in RATING_MAP:
        raise ValueError(f"rating 必须为 again/hard/good/easy，收到: {rating_str}")
    with OrmSession(engine) as s:
        c = s.query(PolishCard).filter_by(id=card_id, user_id=user_id, status="active").first()
        if not c:
            raise LookupError("polish_card 不存在或已删除")
        if not c.fsrs_card_data:
            c.fsrs_card_data = create_card()
        new_json, card_dict = review_card(c.fsrs_card_data, RATING_MAP[rating_str])
        c.fsrs_card_data = new_json
        c.last_reviewed_at = datetime.utcnow()
        c.review_count = (c.review_count or 0) + 1
        s.commit()
        s.refresh(c)
        return {"id": c.id, "due": card_dict.get("due"), "card": _to_dict(c)}
