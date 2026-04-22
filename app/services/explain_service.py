"""句子/单词解读服务 — 按用户 CEFR 等级生成结构化解读，带缓存"""

import hashlib
import json
import re
from typing import Dict, Optional

from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.exc import IntegrityError

from app.models.db import engine, ExplanationCache, UserProfile
from app.prompts.explain import EXPLAIN_SENTENCE_PROMPT, EXPLAIN_WORD_PROMPT
from app.services.model_client import get_client
from app.logger import get_logger

logger = get_logger("explain_service")

VALID_KINDS = {"sentence", "word"}
MAX_TEXT_LEN = 2000
_DEFAULT_LEVEL = "B1"


# ── Helpers ──────────────────────────────────────────────────

def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_level(level: Optional[str]) -> str:
    if not level:
        return ""
    level = level.strip().upper()
    if level in {"A1", "A2", "B1", "B2", "C1", "C2"}:
        return level
    return ""


def _get_user_level(user_id: str) -> str:
    with OrmSession(engine) as s:
        row = s.query(UserProfile).filter_by(user_id=user_id).first()
        if row and row.cefr_level:
            return _normalize_level(row.cefr_level)
    return ""


def _cache_get(text: str, kind: str, cefr_level: str) -> Optional[Dict]:
    h = _hash_text(text)
    with OrmSession(engine) as s:
        row = (
            s.query(ExplanationCache)
            .filter_by(text_hash=h, kind=kind, cefr_level=cefr_level)
            .first()
        )
        if row and row.source_text == text:
            row.hit_count = (row.hit_count or 0) + 1
            s.commit()
            try:
                return json.loads(row.explanation)
            except json.JSONDecodeError:
                return None
    return None


def _cache_set(text: str, kind: str, cefr_level: str, explanation: Dict) -> None:
    h = _hash_text(text)
    with OrmSession(engine) as s:
        existing = (
            s.query(ExplanationCache)
            .filter_by(text_hash=h, kind=kind, cefr_level=cefr_level)
            .first()
        )
        if existing:
            return
        s.add(
            ExplanationCache(
                text_hash=h,
                kind=kind,
                cefr_level=cefr_level,
                source_text=text,
                explanation=json.dumps(explanation, ensure_ascii=False),
            )
        )
        try:
            s.commit()
        except IntegrityError:
            s.rollback()


def _strip_code_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)
    return raw.strip()


def _parse_explanation(raw: str) -> Dict:
    cleaned = _strip_code_fences(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"解读返回无法解析为 JSON：{cleaned[:200]}") from e
    if not isinstance(data, dict):
        raise ValueError(f"解读返回不是 JSON 对象：{cleaned[:200]}")
    return data


# ── Public API ──────────────────────────────────────────────

async def explain_text(
    text: str,
    kind: str,
    user_id: str,
    context: str = "",
) -> Dict:
    """
    生成句子/单词解读。
    :param kind: 'sentence' | 'word'
    :param context: word 模式下提供所在句子，sentence 模式下忽略
    """
    if not text or not text.strip():
        raise ValueError("解读内容不能为空")
    text = text.strip()
    if len(text) > MAX_TEXT_LEN:
        raise ValueError(f"解读内容不能超过 {MAX_TEXT_LEN} 字符")
    if kind not in VALID_KINDS:
        raise ValueError(f"无效的解读类型: {kind}，可选值: sentence / word")

    cefr_level = _get_user_level(user_id)
    cache_level = cefr_level or _DEFAULT_LEVEL

    cached = _cache_get(text, kind, cache_level)
    if cached is not None:
        return {"explanation": cached, "cefr_level": cache_level, "cached": True}

    prompt_level = cefr_level or _DEFAULT_LEVEL
    if kind == "sentence":
        system_prompt = EXPLAIN_SENTENCE_PROMPT.format(cefr_level=prompt_level)
    else:
        system_prompt = EXPLAIN_WORD_PROMPT.format(
            cefr_level=prompt_level,
            text=text.replace('"', '\\"'),
            context=(context or "").replace('"', '\\"'),
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text},
    ]
    client = get_client()
    raw = await client.complete(messages, max_tokens=2000)
    explanation = _parse_explanation(raw)

    _cache_set(text, kind, cache_level, explanation)
    return {"explanation": explanation, "cefr_level": cache_level, "cached": False}
