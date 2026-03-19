import json
from typing import List, Optional

from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, UserFact
from app.prompts.facts import FACTS_EXTRACTION_PROMPT
from app.services.model_client import get_client
from app.logger import get_logger

logger = get_logger("facts_service")


async def extract_and_save_facts(
    user_id: str,
    session_id: str,
    history: list,
) -> None:
    """
    从对话历史中提取事实，写入 user_facts 表。
    幂等保护：同一 session_id 已提取过则跳过。
    """
    # 幂等检查
    with OrmSession(engine) as s:
        existing = s.query(UserFact).filter_by(source_session_id=session_id).first()
        if existing:
            logger.info("facts already extracted for session=%s, skip", session_id)
            return

    # 至少需要 2 条用户消息才提取
    user_messages = [m for m in history if m.get("role") == "user"]
    if len(user_messages) < 2:
        logger.info("not enough user messages in session=%s, skip facts extraction", session_id)
        return

    conversation_text = "\n".join(
        f"{m['role']}: {m['content']}" for m in history
    )
    prompt = FACTS_EXTRACTION_PROMPT.format(conversation=conversation_text)

    try:
        client = get_client()
        raw = await client.complete(prompt, max_tokens=500)

        # Strip markdown code fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw

        facts_list = json.loads(raw)
        if not isinstance(facts_list, list):
            logger.error("facts extraction returned non-list for session=%s", session_id)
            return

        with OrmSession(engine) as s:
            for fact_text in facts_list[:5]:  # max 5
                if fact_text and isinstance(fact_text, str):
                    fact = UserFact(
                        user_id=user_id,
                        content=fact_text.strip(),
                        source_session_id=session_id,
                    )
                    s.add(fact)
            s.commit()
            logger.info("saved %d facts for user=%s session=%s", len(facts_list[:5]), user_id, session_id)

    except Exception as e:
        logger.error("facts extraction failed for session=%s: %s", session_id, e)


def get_recent_facts(user_id: str, limit: int = 20) -> List[UserFact]:
    """返回用户最近的 facts，按创建时间倒序。"""
    with OrmSession(engine) as s:
        facts = (
            s.query(UserFact)
            .filter_by(user_id=user_id)
            .order_by(UserFact.created_at.desc())
            .limit(limit)
            .all()
        )
        # Detach from session
        for f in facts:
            s.expunge(f)
        return facts


def delete_fact(fact_id: int, user_id: str) -> bool:
    """物理删除一条 fact，返回是否成功。"""
    with OrmSession(engine) as s:
        fact = s.query(UserFact).filter_by(id=fact_id, user_id=user_id).first()
        if not fact:
            return False
        s.delete(fact)
        s.commit()
        return True
