"""
V0.3 Step 2 — user_profile 注入 system prompt（层1）
user_id: test_user_v03_s2
"""
import pytest
from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, Base, UserProfile, GrammarCard
from app.services.profile_service import upsert_profile
from app.services.memory_service import build_system_prompt

TEST_USER = "test_user_v03_s2"


@pytest.fixture(autouse=True)
def cleanup():
    Base.metadata.create_all(engine)
    yield
    with OrmSession(engine) as s:
        s.query(UserProfile).filter_by(user_id=TEST_USER).delete()
        s.query(GrammarCard).filter_by(user_id=TEST_USER).delete()
        s.commit()


# ── 无 profile 时 ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_profile_returns_base_prompt():
    prompt = await build_system_prompt(TEST_USER)
    assert "You are Alex" in prompt
    assert "[Profile]" not in prompt


# ── 有 profile 时 ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_profile_injected_in_prompt():
    upsert_profile(TEST_USER, {
        "cefr_level": "B1",
        "profession": "Product Manager",
        "industry": "internet",
        "topic_preferences": "workplace communication",
        "learning_goal": "fluent workplace English",
        "personality_note": "humor and casual",
    })
    prompt = await build_system_prompt(TEST_USER)
    assert "[Profile]" in prompt
    assert "Product Manager" in prompt
    assert "B1" in prompt
    assert "workplace communication" in prompt
    assert "fluent workplace English" in prompt
    assert "humor and casual" in prompt
    assert "internet" in prompt


@pytest.mark.asyncio
async def test_partial_profile_no_empty_lines():
    upsert_profile(TEST_USER, {"cefr_level": "B2"})
    prompt = await build_system_prompt(TEST_USER)
    assert "B2" in prompt
    # 没有 profession 字段时不出现 None
    assert "None" not in prompt
    assert "Profession: None" not in prompt


@pytest.mark.asyncio
async def test_empty_user_id_no_profile_block():
    prompt = await build_system_prompt("")
    assert "[Profile]" not in prompt
    assert "You are Alex" in prompt


# ── profile + grammar_cards 共存 ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_profile_and_grammar_cards_both_injected():
    """层1 + 层3 同时存在时，都注入且格式正确"""
    upsert_profile(TEST_USER, {"cefr_level": "B1", "profession": "Engineer"})
    # 插入一张已到期的 active grammar card
    import json
    from datetime import datetime, timezone, timedelta
    from fsrs import Card, Rating, FSRS
    sc = FSRS()
    card = Card()
    card, _ = sc.review_card(card, Rating.Hard)
    # 强制 due 为过去
    card_dict = card.to_dict()
    card_dict["due"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    with OrmSession(engine) as s:
        gc = GrammarCard(
            user_id=TEST_USER,
            key="test_grammar_key_s2",
            content="使用 past tense",
            example_wrong="Yesterday I go",
            example_right="Yesterday I went",
            explanation_zh="过去时",
            frequency=2,
            fsrs_card_data=json.dumps(card_dict),
            status="active",
        )
        s.add(gc)
        s.commit()

    prompt = await build_system_prompt(TEST_USER)
    assert "[Profile]" in prompt
    assert "Engineer" in prompt
    assert "Grammar Habits" in prompt
    assert "past tense" in prompt


print("✅ Step 2 完成")
