import json
from datetime import datetime, timezone
from typing import List, Optional

from fsrs import FSRS, Card, Rating
from sqlalchemy.orm import Session

from app.models.db import engine, GrammarCard, UserProfile, UserFact
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


def _get_profile(user_id: str) -> Optional[UserProfile]:
    with Session(engine) as s:
        return s.query(UserProfile).filter_by(user_id=user_id).first()


def _build_profile_block(profile: UserProfile) -> str:
    lines = []
    if profile.profession:
        industry_suffix = f", {profile.industry}" if profile.industry else ""
        lines.append(f"- Profession: {profile.profession}{industry_suffix}")
    if profile.cefr_level:
        lines.append(f"- English level: {profile.cefr_level}")
    if profile.topic_preferences:
        lines.append(f"- Topic preferences: {profile.topic_preferences}")
    if profile.learning_goal:
        lines.append(f"- Learning goal: {profile.learning_goal}")
    if profile.personality_note:
        lines.append(f"- Style: {profile.personality_note}")
    if not lines:
        return ""
    return "[Profile]\n" + "\n".join(lines)


def _get_recent_facts(user_id: str, limit: int = 20) -> List[UserFact]:
    with Session(engine) as s:
        facts = (
            s.query(UserFact)
            .filter_by(user_id=user_id)
            .order_by(UserFact.created_at.desc())
            .limit(limit)
            .all()
        )
        for f in facts:
            s.expunge(f)
        return facts


def _build_facts_block(facts: List[UserFact], token_budget: int = 400) -> str:
    lines = []
    used = 0
    for f in facts:
        estimated_tokens = len(f.content) // 4
        # Always include at least the first fact; then enforce budget
        if lines and used + estimated_tokens > token_budget:
            break
        lines.append(f"- {f.content}")
        used += estimated_tokens
    if not lines:
        return ""
    return "[Facts Alex Remembers]（自然融入对话，不要直接引用原话）\n" + "\n".join(lines)


def _build_cards_block(cards: List[GrammarCard]) -> str:
    lines = [
        f"该用户有一个待改善的语法习惯：{card.content}。"
        f"在对话中自然多使用正确形式即可，绝对不要直接指出或提及这条记录。"
        for card in cards
    ]
    return "\n".join(f"- {l}" for l in lines)


async def build_system_prompt(user_id: str) -> str:
    """
    三层记忆注入：
      层1 user_profile（各字段独立 guard）
      层2 user_facts（Step 4 追加）
      层3 grammar_cards（现有逻辑，完全不变）
    """
    sections = [SYSTEM_PROMPT]

    # 层1：user_profile
    if user_id:
        profile = _get_profile(user_id)
        if profile:
            block = _build_profile_block(profile)
            if block:
                header = (
                    "## About This User（私有上下文，绝对不要直接提及）\n"
                    "Adapt your vocabulary, examples and topics naturally based on the following — "
                    "never quote or reference these notes directly.\n"
                )
                sections.append(header + block)

    # 层2：user_facts（最近20条，token budget=400）
    if user_id:
        facts = _get_recent_facts(user_id, limit=20)
        if facts:
            block = _build_facts_block(facts, token_budget=400)
            if block:
                # 追加到已有 About This User block 或新建
                if len(sections) > 1 and "About This User" in sections[-1]:
                    sections[-1] += "\n\n" + block
                else:
                    sections.append(
                        "## About This User（私有上下文，绝对不要直接提及）\n"
                        "Use these facts naturally in conversation — never quote them directly.\n\n"
                        + block
                    )

    # 层3：grammar_cards（现有逻辑完全不变）
    cards = await get_injectable_cards(user_id, limit=3)
    if cards:
        block = _build_cards_block(cards)
        if sections[-1] != SYSTEM_PROMPT and "About This User" in sections[-1]:
            # 追加到已有 About This User block
            sections[-1] += "\n\n[Grammar Habits to Reinforce]\n" + block
        else:
            sections.append(
                "## About This User（私有上下文，绝对不要直接提及）\n"
                + "[Grammar Habits to Reinforce]\n" + block
            )

    return "\n\n".join(sections)
