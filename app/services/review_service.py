import json
from typing import Optional

from sqlalchemy.orm import Session

from app.models.db import engine, SessionReview
from app.prompts.review import REVIEW_PROMPT
from app.services.model_client import get_client
from app.logger import get_logger

logger = get_logger("review_service")


async def analyze_conversation(session_id: str, user_id: str, history: list) -> Optional[dict]:
    """
    分析对话，返回复盘数据。返回 None 表示分析失败，调用方降级到今日一句。
    """
    try:
        user_messages = [m for m in history if m["role"] == "user"]
        if len(user_messages) < 2:
            return None

        conversation_text = "\n".join(f"user: {m['content']}" for m in user_messages)
        prompt = REVIEW_PROMPT.format(conversation=conversation_text)

        client = get_client()
        raw = await client.complete(prompt, max_tokens=1000)

        # Strip markdown code fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw

        result = json.loads(raw)
        result["errors"] = [e for e in result.get("errors", []) if e.get("confidence", 0) >= 0.7]

        stats = {
            "turns": len(history),
            "duration_seconds": 0
        }
        result["stats"] = stats

        await save_session_review(session_id, user_id, result)
        return result

    except Exception as e:
        logger.error("复盘分析失败 session_id=%s error=%s", session_id, e)
        return None


async def save_session_review(session_id: str, user_id: str, data: dict) -> None:
    """写入 session_reviews 表"""
    with Session(engine) as s:
        existing = s.query(SessionReview).filter_by(session_id=session_id).first()
        if existing:
            existing.errors = json.dumps(data.get("errors", []))
            existing.highlights = json.dumps(data.get("highlights", []))
            existing.stats = json.dumps(data.get("stats", {}))
        else:
            review = SessionReview(
                session_id=session_id,
                user_id=user_id,
                errors=json.dumps(data.get("errors", [])),
                highlights=json.dumps(data.get("highlights", [])),
                stats=json.dumps(data.get("stats", {})),
                is_user_rated=False,
            )
            s.add(review)
        s.commit()


async def get_session_review(session_id: str) -> Optional[SessionReview]:
    """查询复盘数据"""
    with Session(engine) as s:
        return s.query(SessionReview).filter_by(session_id=session_id).first()


async def get_card_by_key(user_id: str, key: str):
    """根据 user_id + key 查询 grammar_card"""
    from app.models.db import GrammarCard
    with Session(engine) as s:
        return s.query(GrammarCard).filter_by(user_id=user_id, key=key).first()


async def update_card_fsrs(card_id: int, fsrs_card_data: str) -> None:
    """更新 grammar_card 的 FSRS 数据"""
    from app.models.db import GrammarCard
    with Session(engine) as s:
        card = s.query(GrammarCard).filter_by(id=card_id).first()
        if card:
            card.fsrs_card_data = fsrs_card_data
            s.commit()


async def mark_session_user_rated(session_id: str) -> None:
    """标记该 session 用户已手动打分"""
    with Session(engine) as s:
        review = s.query(SessionReview).filter_by(session_id=session_id).first()
        if review:
            review.is_user_rated = True
            s.commit()
