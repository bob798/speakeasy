import pytest
import json
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from main import app

TEST_USER = "test_user_v02b_step4"


@pytest.mark.asyncio
async def test_summary_returns_review():
    history = [
        {"role": "user", "content": "Yesterday I go to the client office."},
        {"role": "assistant", "content": "Sounds great!"},
        {"role": "user", "content": "I go there every week."},
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/chat/summary", json={
            "user_id": TEST_USER,
            "session_id": "test_session_step4_a",
            "history": history
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "review"
    assert "errors" in data
    assert "highlights" in data
    assert "stats" in data


@pytest.mark.asyncio
async def test_summary_fallback_on_llm_failure():
    with patch("app.services.review_service.get_client") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.complete.side_effect = Exception("LLM down")
        mock_client.return_value = mock_instance
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/chat/summary", json={
                "user_id": TEST_USER,
                "session_id": "test_session_step4_b",
                "history": [
                    {"role": "user", "content": "I go yesterday."},
                    {"role": "assistant", "content": "Ok."},
                    {"role": "user", "content": "I go again."},
                ]
            })
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "tip"
    assert "tip" in data
    assert len(data["tip"]) > 0


@pytest.mark.asyncio
async def test_summary_fallback_on_short_history():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/chat/summary", json={
            "user_id": TEST_USER,
            "session_id": "test_session_step4_c",
            "history": [{"role": "user", "content": "Hi"}]
        })
    data = resp.json()
    assert data["type"] == "tip"


@pytest.mark.asyncio
async def test_summary_creates_grammar_cards():
    from sqlalchemy.orm import Session
    from app.models.db import engine, GrammarCard

    history = [
        {"role": "user", "content": "Yesterday I go to the office."},
        {"role": "assistant", "content": "Got it."},
        {"role": "user", "content": "I go there every day last week."},
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/chat/summary", json={
            "user_id": TEST_USER,
            "session_id": "test_session_step4_d",
            "history": history
        })

    with Session(engine) as s:
        cards = s.query(GrammarCard).filter_by(user_id=TEST_USER).all()
    assert len(cards) > 0

    # 清理
    with Session(engine) as s:
        s.query(GrammarCard).filter_by(user_id=TEST_USER).delete()
        s.commit()
