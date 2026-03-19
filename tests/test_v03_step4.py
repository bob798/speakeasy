"""
V0.3 Step 4 — user_facts 注入 system prompt + 三层联调
user_id: test_user_v03_s4
"""
import json
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, Base, UserProfile, UserFact, GrammarCard
from app.services.profile_service import upsert_profile
from app.services.memory_service import build_system_prompt
from fsrs import Card, Rating, FSRS

TEST_USER = "test_user_v03_s4"

_scheduler = FSRS()


def _make_active_card(key: str, content: str) -> GrammarCard:
    card = Card()
    card, _ = _scheduler.review_card(card, Rating.Hard)
    card_dict = card.to_dict()
    card_dict["due"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    return GrammarCard(
        user_id=TEST_USER,
        key=key,
        content=content,
        example_wrong="wrong",
        example_right="right",
        explanation_zh="说明",
        frequency=2,
        fsrs_card_data=json.dumps(card_dict),
        status="active",
    )


@pytest.fixture(autouse=True)
def cleanup():
    Base.metadata.create_all(engine)
    yield
    with OrmSession(engine) as s:
        s.query(UserProfile).filter_by(user_id=TEST_USER).delete()
        s.query(UserFact).filter_by(user_id=TEST_USER).delete()
        s.query(GrammarCard).filter_by(user_id=TEST_USER).delete()
        s.commit()


# ── 三层同时存在 ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_all_three_layers_injected():
    # 层1 profile
    upsert_profile(TEST_USER, {"cefr_level": "B1", "profession": "Designer"})
    # 层2 facts
    with OrmSession(engine) as s:
        s.add(UserFact(user_id=TEST_USER, content="User is designing a new app", source_session_id="s1"))
        s.commit()
    # 层3 grammar card
    with OrmSession(engine) as s:
        s.add(_make_active_card("past_tense_s4", "使用 past tense"))
        s.commit()

    prompt = await build_system_prompt(TEST_USER)

    assert "You are Alex" in prompt
    assert "[Profile]" in prompt
    assert "Designer" in prompt
    assert "Facts Alex Remembers" in prompt
    assert "designing a new app" in prompt
    assert "Grammar Habits" in prompt
    assert "past tense" in prompt


# ── 各层独立 guard ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_only_profile_no_facts_no_cards():
    upsert_profile(TEST_USER, {"cefr_level": "A2"})
    prompt = await build_system_prompt(TEST_USER)
    assert "[Profile]" in prompt
    assert "Facts Alex Remembers" not in prompt
    assert "Grammar Habits" not in prompt


@pytest.mark.asyncio
async def test_only_facts_no_profile_no_cards():
    with OrmSession(engine) as s:
        s.add(UserFact(user_id=TEST_USER, content="User loves hiking", source_session_id="s1"))
        s.commit()
    prompt = await build_system_prompt(TEST_USER)
    assert "Facts Alex Remembers" in prompt
    assert "loves hiking" in prompt
    assert "[Profile]" not in prompt
    assert "Grammar Habits" not in prompt


@pytest.mark.asyncio
async def test_only_cards_no_profile_no_facts():
    with OrmSession(engine) as s:
        s.add(_make_active_card("modal_s4", "使用 modal verbs"))
        s.commit()
    prompt = await build_system_prompt(TEST_USER)
    assert "Grammar Habits" in prompt
    assert "modal verbs" in prompt
    assert "[Profile]" not in prompt
    assert "Facts Alex Remembers" not in prompt


@pytest.mark.asyncio
async def test_no_layers_returns_base_prompt():
    prompt = await build_system_prompt(TEST_USER)
    assert prompt.strip() == (await _base_prompt_only())


async def _base_prompt_only():
    from app.prompts.system import SYSTEM_PROMPT
    return SYSTEM_PROMPT.strip()


# ── V0.2b 回归：grammar_cards 注入行为不变 ──────────────────────────────────

@pytest.mark.asyncio
async def test_grammar_cards_injection_unchanged_from_v02b():
    """当只有 grammar_cards 时，行为与 V0.2b 完全一致（含正确内容）"""
    with OrmSession(engine) as s:
        s.add(_make_active_card("article_s4", "使用冠词 a/an/the"))
        s.commit()

    prompt = await build_system_prompt(TEST_USER)
    assert "冠词 a/an/the" in prompt
    assert "About This User" in prompt


# ── token budget 截断 ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_facts_token_budget_respected():
    """超过 token budget 的 facts 应被截断"""
    long_fact = "X" * 1600  # ~400 tokens
    with OrmSession(engine) as s:
        for i in range(5):
            s.add(UserFact(user_id=TEST_USER, content=f"Fact {i}: {long_fact}", source_session_id=f"s{i}"))
        s.commit()

    prompt = await build_system_prompt(TEST_USER)
    # Should contain facts section but not all 5 facts (budget=400 tokens)
    assert "Facts Alex Remembers" in prompt
    # Count how many "Fact N" appear
    fact_count = sum(1 for i in range(5) if f"Fact {i}:" in prompt)
    assert fact_count < 5, "Token budget should have truncated some facts"


print("✅ Step 4 完成")
