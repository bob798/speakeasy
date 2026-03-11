import pytest
from fsrs import FSRS, Card, Rating
from sqlalchemy import inspect
from app.models.db import engine, GrammarCard, SessionReview, Base
from sqlalchemy.orm import Session


def test_fsrs_importable():
    scheduler = FSRS()
    card = Card()
    card, log = scheduler.review_card(card, Rating.Good)
    assert card is not None


def test_tables_exist():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "grammar_cards" in tables
    assert "session_reviews" in tables


def test_grammar_cards_schema():
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("grammar_cards")}
    required = {"id", "user_id", "key", "status", "frequency", "fsrs_card_data"}
    assert required.issubset(columns)


def test_session_reviews_schema():
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("session_reviews")}
    required = {"id", "session_id", "user_id", "errors", "highlights", "is_user_rated"}
    assert required.issubset(columns)


def test_grammar_card_crud():
    with Session(engine) as session:
        card = GrammarCard(
            user_id="test_user_v02b",
            key="test_key_step1",
            status="pending",
            frequency=1,
        )
        session.add(card)
        session.commit()
        found = session.query(GrammarCard).filter_by(key="test_key_step1").first()
        assert found is not None
        assert found.status == "pending"
        session.delete(found)
        session.commit()
