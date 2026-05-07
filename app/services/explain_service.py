"""句子/单词解读服务 — 按用户 CEFR 等级生成结构化解读，带缓存"""

import hashlib
import json
import re
import time
from typing import Dict, Optional

from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.exc import IntegrityError

from app.models.db import engine, ExplanationCache, UserProfile
from app.prompts.explain import EXPLAIN_SENTENCE_PROMPT, EXPLAIN_WORD_PROMPT
from app.knowledge import liaison_prompt_block
from app.services.model_client import get_client
from app.logger import get_logger

try:
    import eng_to_ipa as _ipa
    _IPA_AVAILABLE = True
except Exception:  # pragma: no cover
    _IPA_AVAILABLE = False

logger = get_logger("explain_service")

VALID_KINDS = {"sentence", "word"}
MAX_TEXT_LEN = 2000
_DEFAULT_LEVEL = "B1"

# Prompt 输出 schema 版本；变更 schema（如新增字段）或语言规则时加 1，使旧 cache 自动失效
_SCHEMA_VERSION = 6     # V0.11 #6 · liaison KB 注入 · 通俗化 tip 风格

# Prompt 文本哈希（V0.11 #8）：prompt 微调即让旧 cache 自动失效，无需手 bump _SCHEMA_VERSION
# 取 8 字符已足够区分任何 prompt 版本
_PROMPT_HASH = hashlib.sha256(
    (EXPLAIN_SENTENCE_PROMPT + "|||" + EXPLAIN_WORD_PROMPT).encode("utf-8")
).hexdigest()[:8]

# 手动 refresh 防滥用：同 (user, text_hash) 的 force 间隔下限（秒）
_REFRESH_DEBOUNCE_SEC = 3.0
_refresh_log: Dict[str, float] = {}


# ── Helpers ──────────────────────────────────────────────────

def _hash_text(text: str) -> str:
    # schema 版本 + prompt hash 都纳入，任何一处变了就 cache miss
    return hashlib.sha256(
        f"v{_SCHEMA_VERSION}:{_PROMPT_HASH}:{text}".encode("utf-8")
    ).hexdigest()


def _check_refresh_debounce(user_id: str, text_hash: str) -> bool:
    """同用户对同文本的强制刷新 3s 内只允许一次"""
    key = f"{user_id}:{text_hash}"
    now = time.time()
    last = _refresh_log.get(key, 0.0)
    if now - last < _REFRESH_DEBOUNCE_SEC:
        return False
    _refresh_log[key] = now
    # 简单 LRU：超过 1000 条砍掉一半最旧的
    if len(_refresh_log) > 1000:
        cutoff = sorted(_refresh_log.values())[500]
        for k in list(_refresh_log.keys()):
            if _refresh_log[k] < cutoff:
                del _refresh_log[k]
    return True


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


def _cache_set(text: str, kind: str, cefr_level: str, explanation: Dict, overwrite: bool = False) -> None:
    h = _hash_text(text)
    with OrmSession(engine) as s:
        existing = (
            s.query(ExplanationCache)
            .filter_by(text_hash=h, kind=kind, cefr_level=cefr_level)
            .first()
        )
        if existing:
            if overwrite:
                existing.explanation = json.dumps(explanation, ensure_ascii=False)
                existing.source_text = text
                existing.hit_count = 1   # 重生成清零计数
                s.commit()
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


# ── Fast local phonetic (B1) ────────────────────────────────

_WORD_RE = re.compile(r"^[a-zA-Z][a-zA-Z'\-]{0,31}$")


def quick_phonetic(text: str) -> Optional[str]:
    """单词 IPA 的本地秒出。仅对单个英文词命中；未知返回 None。"""
    if not text or not _IPA_AVAILABLE:
        return None
    t = text.strip()
    if not _WORD_RE.match(t):
        return None
    try:
        raw = _ipa.convert(t.lower())
    except Exception:
        return None
    if not raw:
        return None
    # eng_to_ipa 对未知词会在词尾追加 '*'
    if raw.endswith("*"):
        return None
    return f"/{raw}/"


# ── Public API ──────────────────────────────────────────────

async def explain_text(
    text: str,
    kind: str,
    user_id: str,
    context: str = "",
    force: bool = False,
) -> Dict:
    """
    生成句子/单词解读。
    :param kind: 'sentence' | 'word'
    :param context: word 模式下提供所在句子，sentence 模式下忽略
    :param force: True 时跳过缓存，重新生成并覆盖；带 3s debounce
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

    if force:
        if not _check_refresh_debounce(user_id, _hash_text(text)):
            raise ValueError("刷新过于频繁，请稍后再试")
    else:
        cached = _cache_get(text, kind, cache_level)
        if cached is not None:
            return {"explanation": cached, "cefr_level": cache_level, "cached": True}

    prompt_level = cefr_level or _DEFAULT_LEVEL
    if kind == "sentence":
        system_prompt = EXPLAIN_SENTENCE_PROMPT.format(
            cefr_level=prompt_level,
            liaison_kb=liaison_prompt_block(),
        )
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

    _cache_set(text, kind, cache_level, explanation, overwrite=force)
    return {"explanation": explanation, "cefr_level": cache_level, "cached": False, "regenerated": force}


# ── Streaming (sentence only; word 解读量小，仍走整块) ─────

# 追加在现有 EXPLAIN_SENTENCE_PROMPT 上的"流式输出格式"指令
_STREAM_FORMAT_HINT = """\

CRITICAL OUTPUT FORMAT (MUST FOLLOW):
Instead of a single JSON object, output one JSON line per field (NDJSON), strictly in this order:
1. {"field":"meaning","value":"..."}
2. {"field":"grammar","value":"..."}
3. {"field":"phrases","value":[...]}
4. {"field":"liaison","value":[...]}
5. {"field":"current_level_points","value":[...]}
6. {"field":"next_level_points","value":[...]}
7. {"field":"narration","value":"..."}

Each line is a complete standalone JSON object. Separate lines with a single \\n. No fences, no other text.
"""


async def stream_sentence_explanation(
    text: str,
    user_id: str,
    force: bool = False,
):
    """Async generator yielding (raw_text, is_final) tuples.

    缓存命中时瞬间返回整体解读（is_final=True，raw_text=完整字典 json）。
    否则：
      - 流式产出一行行 NDJSON 字段对象
      - 结束后额外 yield 一个 {"_done": True} 事件
    :param force: True 时跳过缓存重新生成（带 3s debounce）
    """
    if not text or not text.strip():
        raise ValueError("解读内容不能为空")
    text = text.strip()
    if len(text) > MAX_TEXT_LEN:
        raise ValueError(f"解读内容不能超过 {MAX_TEXT_LEN} 字符")

    cefr_level = _get_user_level(user_id)
    cache_level = cefr_level or _DEFAULT_LEVEL

    if force:
        if not _check_refresh_debounce(user_id, _hash_text(text)):
            yield json.dumps({"_error": "刷新过于频繁，请稍后再试"}, ensure_ascii=False)
            return
    else:
        cached = _cache_get(text, "sentence", cache_level)
        if cached is not None:
            yield json.dumps({"_cached": True, "cefr_level": cache_level, "explanation": cached}, ensure_ascii=False)
            return

    prompt_level = cefr_level or _DEFAULT_LEVEL
    system_prompt = (
        EXPLAIN_SENTENCE_PROMPT.format(
            cefr_level=prompt_level,
            liaison_kb=liaison_prompt_block(),
        )
        + _STREAM_FORMAT_HINT
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text},
    ]

    client = get_client()
    buffer = ""
    collected: Dict[str, object] = {}
    async for chunk in client.chat_stream_messages(messages):
        buffer += chunk
        # 按换行拆行；最后一段可能不完整，留在 buffer
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            line = _strip_code_fences(line)
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            f = obj.get("field")
            if isinstance(f, str):
                collected[f] = obj.get("value")
                yield json.dumps({"field": f, "value": obj.get("value")}, ensure_ascii=False)

    # 最后残留一行
    tail = _strip_code_fences(buffer.strip())
    if tail:
        try:
            obj = json.loads(tail)
            if isinstance(obj, dict) and isinstance(obj.get("field"), str):
                collected[obj["field"]] = obj.get("value")
                yield json.dumps({"field": obj["field"], "value": obj.get("value")}, ensure_ascii=False)
        except json.JSONDecodeError:
            pass

    if collected:
        _cache_set(text, "sentence", cache_level, collected, overwrite=force)
    yield json.dumps({"_done": True, "cefr_level": cache_level, "regenerated": force}, ensure_ascii=False)
