import pytest
import asyncio
import json
from datetime import datetime, timezone, timedelta
from fsrs import Card, Rating, FSRS
from sqlalchemy.orm import Session
from app.models.db import engine, GrammarCard
from app.services.memory_service import (
    update_grammar_cards,
    get_injectable_cards,
    build_system_prompt
)

TEST_USER = "test_user_v02b_step2"


def cleanup():
    with Session(engine) as s:
        s.query(GrammarCard).filter_by(user_id=TEST_USER).delete()
        s.commit()


@pytest.fixture(autouse=True)
def clean():
    cleanup()
    yield
    cleanup()


def run(coro):
    return asyncio.run(coro)


ERROR_GO_WENT = {
    "key": "go_went",
    "content": "常用 go 代替 went",
    "original": "I go to the client yesterday",
    "corrected": "I went to the client yesterday",
    "explanation_zh": "yesterday 表过去，go → went",
    "count": 1,
    "confidence": 0.9
}


def test_first_occurrence_is_pending():
    run(update_grammar_cards(TEST_USER, [ERROR_GO_WENT]))
    with Session(engine) as s:
        card = s.query(GrammarCard).filter_by(user_id=TEST_USER, key="go_went").first()
    assert card.status == "pending"
    assert card.frequency == 1
    assert card.fsrs_card_data == ""


def test_second_occurrence_becomes_active():
    run(update_grammar_cards(TEST_USER, [ERROR_GO_WENT]))
    run(update_grammar_cards(TEST_USER, [ERROR_GO_WENT]))
    with Session(engine) as s:
        card = s.query(GrammarCard).filter_by(user_id=TEST_USER, key="go_went").first()
    assert card.status == "active"
    assert card.frequency == 2
    assert card.fsrs_card_data != ""
    fsrs_data = json.loads(card.fsrs_card_data)
    assert "due" in fsrs_data


def test_third_occurrence_increments_frequency():
    run(update_grammar_cards(TEST_USER, [ERROR_GO_WENT]))
    run(update_grammar_cards(TEST_USER, [ERROR_GO_WENT]))
    run(update_grammar_cards(TEST_USER, [ERROR_GO_WENT]))
    with Session(engine) as s:
        card = s.query(GrammarCard).filter_by(user_id=TEST_USER, key="go_went").first()
    assert card.frequency == 3


def test_get_injectable_cards_due():
    # 手动插入一张 due=过去 的 active card
    scheduler = FSRS()
    fsrs_card = Card()
    fsrs_card, _ = scheduler.review_card(fsrs_card, Rating.Again)
    # 强制 due 为过去时间
    card_dict = fsrs_card.to_dict()
    card_dict["due"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    with Session(engine) as s:
        row = GrammarCard(
            user_id=TEST_USER, key="due_card",
            status="active", frequency=2,
            fsrs_card_data=json.dumps(card_dict),
        )
        s.add(row)
        s.commit()

    result = run(get_injectable_cards(TEST_USER))
    assert any(c.key == "due_card" for c in result)


def test_get_injectable_cards_not_due():
    scheduler = FSRS()
    fsrs_card = Card()
    card_dict = fsrs_card.to_dict()
    card_dict["due"] = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()

    with Session(engine) as s:
        row = GrammarCard(
            user_id=TEST_USER, key="future_card",
            status="active", frequency=2,
            fsrs_card_data=json.dumps(card_dict),
        )
        s.add(row)
        s.commit()

    result = run(get_injectable_cards(TEST_USER))
    assert not any(c.key == "future_card" for c in result)


def test_build_system_prompt_with_cards():
    scheduler = FSRS()
    fsrs_card = Card()
    card_dict = fsrs_card.to_dict()
    card_dict["due"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    with Session(engine) as s:
        row = GrammarCard(
            user_id=TEST_USER, key="inject_card",
            content="常用 go 代替 went",
            status="active", frequency=2,
            fsrs_card_data=json.dumps(card_dict),
        )
        s.add(row)
        s.commit()

    prompt = run(build_system_prompt(TEST_USER))
    assert "常用 go 代替 went" in prompt


def test_build_system_prompt_without_cards():
    from app.services.chat_service import SYSTEM_PROMPT
    prompt = run(build_system_prompt(TEST_USER))
    assert prompt == SYSTEM_PROMPT
