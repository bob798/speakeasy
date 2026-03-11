import json
from datetime import datetime, timezone
from typing import List

from fsrs import FSRS, Card, Rating
from sqlalchemy.orm import Session

from app.models.db import engine, GrammarCard
from app.prompts.system import SYSTEM_PROMPT
from app.logger import get_logger

logger = get_logger("memory_service")

_scheduler = FSRS()


async def update_grammar_cards(user_id: str, errors: list) -> None:
    """
    遍历 errors，更新 grammar_cards 表。
    - 首次出现：status='pending'，frequency=1
    - 第二次：status='active'，创建 FSRS Card，frequency=2
    - 之后：frequency+1，Rating.Hard 更新 FSRS
    """
    with Session(engine) as s:
        for err in errors:
            key = err.get("key", "")
            if not key:
                continue
            row = s.query(GrammarCard).filter_by(user_id=user_id, key=key).first()
            if row is None:
                row = GrammarCard(
                    user_id=user_id,
                    key=key,
                    content=err.get("content", err.get("explanation_zh", "")),
                    example_wrong=err.get("original", ""),
                    example_right=err.get("corrected", ""),
                    explanation_zh=err.get("explanation_zh", ""),
                    frequency=1,
                    fsrs_card_data="",
                    status="pending",
                )
                s.add(row)
            elif row.status == "pending":
                row.frequency += 1
                row.example_wrong = err.get("original", row.example_wrong)
                row.example_right = err.get("corrected", row.example_right)
                row.explanation_zh = err.get("explanation_zh", row.explanation_zh)
                if row.frequency >= 2:
                    row.status = "active"
                    fsrs_card = Card()
                    fsrs_card, _ = _scheduler.review_card(fsrs_card, Rating.Hard)
                    row.fsrs_card_data = json.dumps(fsrs_card.to_dict())
            elif row.status == "active":
                row.frequency += 1
                row.example_wrong = err.get("original", row.example_wrong)
                row.example_right = err.get("corrected", row.example_right)
                row.explanation_zh = err.get("explanation_zh", row.explanation_zh)
                fsrs_card = Card.from_dict(json.loads(row.fsrs_card_data))
                fsrs_card, _ = _scheduler.review_card(fsrs_card, Rating.Hard)
                row.fsrs_card_data = json.dumps(fsrs_card.to_dict())
        s.commit()


async def mark_errors_not_appeared(user_id: str, appeared_keys: list) -> None:
    """
    对未在本次出现的 active card，用 Rating.Good 更新 FSRS。
    """
    with Session(engine) as s:
        active_cards = s.query(GrammarCard).filter_by(user_id=user_id, status="active").all()
        for row in active_cards:
            if row.key not in appeared_keys and row.fsrs_card_data:
                try:
                    fsrs_card = Card.from_dict(json.loads(row.fsrs_card_data))
                    fsrs_card, _ = _scheduler.review_card(fsrs_card, Rating.Good)
                    row.fsrs_card_data = json.dumps(fsrs_card.to_dict())
                except Exception as e:
                    logger.error("mark_errors_not_appeared error key=%s: %s", row.key, e)
        s.commit()


async def get_injectable_cards(user_id: str, limit: int = 3) -> List[GrammarCard]:
    """
    返回 due <= now 的 active card，按 stability 升序，最多 limit 条。
    """
    now = datetime.now(timezone.utc)
    result = []
    with Session(engine) as s:
        active_cards = s.query(GrammarCard).filter_by(user_id=user_id, status="active").all()
        for row in active_cards:
            if not row.fsrs_card_data:
                continue
            try:
                card_data = json.loads(row.fsrs_card_data)
                due_str = card_data.get("due", "")
                if not due_str:
                    continue
                due = datetime.fromisoformat(due_str)
                if due.tzinfo is None:
                    due = due.replace(tzinfo=timezone.utc)
                if due <= now:
                    result.append((card_data.get("stability", 0.0), row))
            except Exception as e:
                logger.error("get_injectable_cards parse error key=%s: %s", row.key, e)

    result.sort(key=lambda x: x[0])
    return [row for _, row in result[:limit]]


async def build_system_prompt(user_id: str) -> str:
    """
    根据到期的 grammar_cards 构建注入记忆的 system prompt。
    """
    cards = await get_injectable_cards(user_id, limit=3)
    if not cards:
        return SYSTEM_PROMPT

    memory_lines = [
        f"该用户有一个待改善的语法习惯：{card.content}。"
        f"在对话中自然多使用正确形式即可，绝对不要直接指出或提及这条记录。"
        for card in cards
    ]
    return SYSTEM_PROMPT + "\n\n## About This User（私有上下文，绝对不要直接提及）\n" + \
           "\n".join(f"- {l}" for l in memory_lines)
