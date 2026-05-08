"""写作偏好提取与注入 · V0.11 P1

- extract_and_save_writing_facts: 从 polish chat 上下文异步提取写作习惯 → user_facts
- build_polish_addon: 给 polish system prompt 拼一段「用户偏好 + 高频错误」补充
"""
import json
import re
from collections import Counter
from typing import List, Optional

from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, UserFact, PolishCard
from app.prompts.polish_facts import POLISH_FACTS_EXTRACTION_PROMPT
from app.services.model_client import get_client
from app.logger import get_logger

logger = get_logger("polish_facts")

POLISH_FACT_PREFIX = "polish:"   # source_session_id 前缀，便于识别 polish 来源 fact
MIN_HISTORY_FOR_EXTRACTION = 2   # chat 至少几轮才触发提取


def _strip_code_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)
    return raw.strip()


def _polish_session_id(original: str) -> str:
    """以 original 文本前 60 字符做 polish session id（同一原文多次 polish 算一次幂等）"""
    h = original.strip()[:60].replace("\n", " ")
    return POLISH_FACT_PREFIX + h


async def extract_and_save_writing_facts(
    user_id: str,
    original: str,
    polished: str,
    chat_history: Optional[List[dict]] = None,
) -> int:
    """从 polish 上下文提取 1-3 条写作偏好 fact 入 user_facts 表 · 返回新增条数

    幂等：同 (user, polish_session_id) 已抽过则跳过。
    chat_history 不足 MIN_HISTORY_FOR_EXTRACTION 轮也跳过。
    """
    if not original or not original.strip():
        return 0
    history = chat_history or []
    if len(history) < MIN_HISTORY_FOR_EXTRACTION:
        return 0

    session_key = _polish_session_id(original)
    with OrmSession(engine) as s:
        existing = (
            s.query(UserFact)
            .filter_by(user_id=user_id, source_session_id=session_key)
            .first()
        )
        if existing:
            return 0

    # 拼上下文
    parts = [f"原文：\n{original}", f"最终版：\n{polished}", "对话："]
    for m in history:
        parts.append(f"{m.get('role','user')}: {m.get('content','')}")
    context = "\n".join(parts)

    try:
        client = get_client()
        raw = await client.complete(
            POLISH_FACTS_EXTRACTION_PROMPT.format(context=context),
            max_tokens=400,
        )
        cleaned = _strip_code_fences(raw)
        facts = json.loads(cleaned)
        if not isinstance(facts, list):
            return 0
    except Exception as e:
        logger.warning("polish 写作偏好抽取失败: %s", e)
        return 0

    saved = 0
    with OrmSession(engine) as s:
        for fact_text in facts[:3]:
            if not isinstance(fact_text, str) or not fact_text.strip():
                continue
            s.add(
                UserFact(
                    user_id=user_id,
                    content=fact_text.strip(),
                    source_session_id=session_key,
                )
            )
            saved += 1
        if saved:
            s.commit()
            logger.info("saved %d writing facts for user=%s", saved, user_id)
    return saved


def get_writing_facts(user_id: str, limit: int = 5) -> List[str]:
    """取 user_facts 中 polish: 前缀的写作偏好（按时间倒序）"""
    with OrmSession(engine) as s:
        rows = (
            s.query(UserFact)
            .filter(UserFact.user_id == user_id)
            .filter(UserFact.source_session_id.like(f"{POLISH_FACT_PREFIX}%"))
            .order_by(UserFact.created_at.desc())
            .limit(limit)
            .all()
        )
        return [r.content for r in rows]


def get_top_categories(user_id: str, limit: int = 3) -> List[str]:
    """统计 polish_cards 中出现最多的 category（高频错误类型）"""
    with OrmSession(engine) as s:
        rows = (
            s.query(PolishCard.category)
            .filter_by(user_id=user_id, status="active")
            .all()
        )
        cats = [r[0] for r in rows if r[0]]
        if not cats:
            return []
        counter = Counter(cats)
        return [c for c, _ in counter.most_common(limit)]


CATEGORY_HUMAN = {
    "grammar": "语法错误",
    "word_choice": "用词不当",
    "style": "风格 / 语气",
    "structure": "句子结构",
}


def build_polish_addon(user_id: str) -> str:
    """生成插入 POLISH_SYSTEM_PROMPT 的「用户偏好 + 高频错误」补充块。
    无任何信息时返回空串（让上层不必拼接）。
    """
    facts = get_writing_facts(user_id)
    cats = get_top_categories(user_id)
    if not facts and not cats:
        return ""
    lines = ["", "## 关于这位用户（来自历史润色记录）"]
    if facts:
        lines.append("写作习惯 / 偏好：")
        for f in facts:
            lines.append(f"- {f}")
    if cats:
        readable = "、".join(CATEGORY_HUMAN.get(c, c) for c in cats)
        lines.append(f"高频问题类型：{readable}")
    lines.append("请在润色时考虑这些已知模式 · 但不要硬性贴标签。")
    return "\n".join(lines)
