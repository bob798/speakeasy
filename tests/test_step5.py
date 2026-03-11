import pytest
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.orm import Session
from app.models.db import engine, GrammarCard
from main import app

TEST_USER = "test_user_v02b_step5"


def insert_due_card():
    from fsrs import Card, Rating, FSRS
    scheduler = FSRS()
    fsrs_card = Card()
    card_dict = fsrs_card.to_dict()
    card_dict["due"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    with Session(engine) as s:
        row = GrammarCard(
            user_id=TEST_USER, key="step5_card",
            content="常用 go 代替 went",
            status="active", frequency=2,
            fsrs_card_data=json.dumps(card_dict),
        )
        s.add(row)
        s.commit()


def cleanup():
    with Session(engine) as s:
        s.query(GrammarCard).filter_by(user_id=TEST_USER).delete()
        s.commit()


@pytest.fixture(autouse=True)
def clean():
    cleanup()
    yield
    cleanup()


@pytest.mark.asyncio
async def test_chat_injects_memory_in_system_prompt():
    insert_due_card()
    captured = {}

    with patch("app.services.chat_service.get_client") as mock_client:
        mock_instance = AsyncMock()
        async def fake_complete(messages, **kwargs):
            captured["system"] = next(
                (m["content"] for m in messages if m.get("role") == "system"), ""
            )
            return "That sounds great!"
        mock_instance.complete = fake_complete
        mock_client.return_value = mock_instance

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/chat", json={
                "user_id": TEST_USER,
                "message": "Hello Alex",
                "history": []
            })

    assert "常用 go 代替 went" in captured.get("system", "")


@pytest.mark.asyncio
async def test_chat_no_injection_without_due_cards():
    from app.services.chat_service import SYSTEM_PROMPT
    captured = {}

    with patch("app.services.chat_service.get_client") as mock_client:
        mock_instance = AsyncMock()
        async def fake_complete(messages, **kwargs):
            captured["system"] = next(
                (m["content"] for m in messages if m.get("role") == "system"), ""
            )
            return "Hello!"
        mock_instance.complete = fake_complete
        mock_client.return_value = mock_instance

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/chat", json={
                "user_id": TEST_USER,
                "message": "Hi",
                "history": []
            })

    assert captured.get("system", "") == SYSTEM_PROMPT
