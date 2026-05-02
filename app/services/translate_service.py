"""翻译服务 — 按行拆分 + 缓存命中 + 批量 JSON 请求 + 生词本 CRUD"""

import hashlib
import json
import re
import string
from typing import List, Dict, Optional, Tuple

from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.exc import IntegrityError

from app.models.db import engine, Vocabulary, TranslationCache
from app.services import vocab_service
from app.prompts.translate import (
    TRANSLATE_BATCH_ZH2EN_PROMPT,
    TRANSLATE_BATCH_EN2ZH_PROMPT,
)
from app.services.model_client import get_client
from app.logger import get_logger

logger = get_logger("translate_service")

VALID_DIRECTIONS = {"zh2en", "en2zh"}
MAX_INPUT_LEN = 1000
_EXTRA_PUNCT = "，。；：！？、（）「」《》【】〈〉·…—～"


# ── Helpers ──────────────────────────────────────────────────

def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_skippable(line: str) -> bool:
    """空行或纯空白/纯标点行：无需翻译，原样保留"""
    stripped = line.strip()
    if not stripped:
        return True
    allowed = set(string.whitespace + string.punctuation + _EXTRA_PUNCT)
    return all(ch in allowed for ch in stripped)


def _cache_get(text: str, direction: str) -> Optional[str]:
    h = _hash_text(text)
    with OrmSession(engine) as s:
        row = (
            s.query(TranslationCache)
            .filter_by(text_hash=h, direction=direction)
            .first()
        )
        if row and row.source_text == text:
            row.hit_count = (row.hit_count or 0) + 1
            s.commit()
            return row.translated_text
    return None


def _cache_set(text: str, direction: str, translated: str) -> None:
    h = _hash_text(text)
    with OrmSession(engine) as s:
        existing = (
            s.query(TranslationCache)
            .filter_by(text_hash=h, direction=direction)
            .first()
        )
        if existing:
            return
        s.add(
            TranslationCache(
                text_hash=h,
                direction=direction,
                source_text=text,
                translated_text=translated,
            )
        )
        try:
            s.commit()
        except IntegrityError:
            s.rollback()  # concurrent insert, safe to drop


def _strip_code_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)
    return raw.strip()


def _parse_batch_response(raw: str, expected_n: int) -> List[str]:
    cleaned = _strip_code_fences(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"翻译返回无法解析为 JSON：{cleaned[:200]}") from e

    if isinstance(data, dict):
        arr = data.get("translations") or data.get("lines") or data.get("result")
    elif isinstance(data, list):
        arr = data
    else:
        arr = None

    if not isinstance(arr, list):
        raise ValueError(f"翻译返回缺少 translations 数组：{cleaned[:200]}")
    if len(arr) != expected_n:
        raise ValueError(
            f"翻译行数不匹配：期望 {expected_n}，实际 {len(arr)}"
        )
    return [str(x) for x in arr]


async def _translate_batch(lines: List[str], direction: str) -> List[str]:
    """把多行一次性丢给 LLM，强制 JSON 结构化输出。"""
    system_prompt = (
        TRANSLATE_BATCH_ZH2EN_PROMPT
        if direction == "zh2en"
        else TRANSLATE_BATCH_EN2ZH_PROMPT
    )
    user_payload = json.dumps({"lines": lines}, ensure_ascii=False)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_payload},
    ]
    client = get_client()
    raw = await client.complete(messages, max_tokens=4000)
    return _parse_batch_response(raw, len(lines))


# ── Public API ──────────────────────────────────────────────

async def translate_text(text: str, direction: str) -> str:
    """
    按行拆分 → 查缓存 → 未命中批量送 LLM → 按原顺序拼回。
    :raises ValueError: 空文本 / 超长 / 无效方向 / LLM 返回异常
    """
    if not text or not text.strip():
        raise ValueError("输入文本不能为空")
    if len(text) > MAX_INPUT_LEN:
        raise ValueError(f"输入文本不能超过 {MAX_INPUT_LEN} 字符")
    if direction not in VALID_DIRECTIONS:
        raise ValueError(f"无效的翻译方向: {direction}，可选值: zh2en / en2zh")

    lines = text.split("\n")
    results: List[Optional[str]] = [None] * len(lines)
    pending: List[Tuple[int, str]] = []   # (idx, stripped_line)

    for i, line in enumerate(lines):
        if _is_skippable(line):
            results[i] = line  # 保留原样（含空行 / 缩进 / 标点）
            continue
        # 翻译时去掉首尾空白；保留中间内容
        key = line.strip()
        cached = _cache_get(key, direction)
        if cached is not None:
            # 恢复原行首尾空白
            leading = line[: len(line) - len(line.lstrip())]
            trailing = line[len(line.rstrip()):]
            results[i] = leading + cached + trailing
        else:
            pending.append((i, key))

    if pending:
        batch = [key for _, key in pending]
        translated = await _translate_batch(batch, direction)
        for (idx, key), trans in zip(pending, translated):
            original = lines[idx]
            leading = original[: len(original) - len(original.lstrip())]
            trailing = original[len(original.rstrip()):]
            results[idx] = leading + trans + trailing
            _cache_set(key, direction, trans)

    return "\n".join(r if r is not None else "" for r in results)


# ── 生词本 CRUD（V0.10 起为 vocab_service 的薄代理）────────

def save_vocabulary(
    user_id: str,
    source_text: str,
    translated_text: str,
    direction: str,
    context: Optional[str] = None,
) -> Dict:
    # 沿用旧契约的输入校验
    if direction not in VALID_DIRECTIONS:
        raise ValueError(f"无效的翻译方向: {direction}，可选值: zh2en / en2zh")
    if not source_text or not source_text.strip():
        raise ValueError("源文本不能为空")
    if not translated_text or not translated_text.strip():
        raise ValueError("译文不能为空")
    return vocab_service.save_item(
        user_id=user_id,
        source_text=source_text,
        translated_text=translated_text,
        direction=direction,
        context=context,
        item_type="sentence",
        source_type="translate",
    )


def list_vocabulary(
    user_id: str,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict]:
    return vocab_service.list_items(user_id=user_id, limit=limit, offset=offset)


def delete_vocabulary(vocab_id: int, user_id: str) -> bool:
    return vocab_service.delete_item(vocab_id, user_id)
