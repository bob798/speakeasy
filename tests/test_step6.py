import pytest
import json
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy.orm import Session
from app.models.db import engine, GrammarCard, SessionReview
from main import app

TEST_USER = "test_user_v02b_step6"
TEST_SESSION = "test_session_step6"


def seed():
    # 写入 session_review
    with Session(engine) as s:
        review = SessionReview(
            session_id=TEST_SESSION,
            user_id=TEST_USER,
            errors=json.dumps([{
                "key": "go_went",
                "original": "I go yesterday",
                "corrected": "I went yesterday",
                "explanation_zh": "go → went",
                "count": 2,
                "confidence": 0.9
            }]),
            highlights=json.dumps([]),
            stats=json.dumps({"turns": 4, "duration_seconds": 120}),
        )
        s.add(review)
        s.commit()

    # 写入对应 grammar_card
    from fsrs import Card
    card_dict = Card().to_dict()
    with Session(engine) as s:
        row = GrammarCard(
            user_id=TEST_USER, key="go_went",
            content="常用 go 代替 went",
            status="active", frequency=2,
            fsrs_card_data=json.dumps(card_dict),
        )
        s.add(row)
        s.commit()


def cleanup():
    with Session(engine) as s:
        s.query(SessionReview).filter_by(user_id=TEST_USER).delete()
        s.query(GrammarCard).filter_by(user_id=TEST_USER).delete()
        s.commit()


@pytest.fixture(autouse=True)
def setup():
    cleanup()
    seed()
    yield
    cleanup()


@pytest.mark.asyncio
async def test_get_review_success():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/review/{TEST_SESSION}")
    assert resp.status_code == 200
    data = resp.json()
    assert "errors" in data
    assert len(data["errors"]) == 1
    assert data["errors"][0]["key"] == "go_went"


@pytest.mark.asyncio
async def test_get_review_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/review/nonexistent_session")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_rate_good_updates_fsrs():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(f"/review/{TEST_SESSION}/rate", json={
            "user_id": TEST_USER,
            "card_key": "go_went",
            "rating": "good"
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "next_review" in data

    # 验证 next_review 是未来时间
    next_review = datetime.fromisoformat(data["next_review"].replace("Z", "+00:00"))
    assert next_review > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_rate_again_sooner_than_good():
    # good 的 next_review
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp_good = await client.post(f"/review/{TEST_SESSION}/rate", json={
            "user_id": TEST_USER, "card_key": "go_went", "rating": "good"
        })
    next_good = datetime.fromisoformat(resp_good.json()["next_review"].replace("Z", "+00:00"))

    # 重置 card，再测 again
    from fsrs import Card
    with Session(engine) as s:
        card_row = s.query(GrammarCard).filter_by(user_id=TEST_USER, key="go_went").first()
        card_row.fsrs_card_data = json.dumps(Card().to_dict())
        s.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp_again = await client.post(f"/review/{TEST_SESSION}/rate", json={
            "user_id": TEST_USER, "card_key": "go_went", "rating": "again"
        })
    next_again = datetime.fromisoformat(resp_again.json()["next_review"].replace("Z", "+00:00"))

    assert next_again < next_good


@pytest.mark.asyncio
async def test_is_user_rated_set_after_rating():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(f"/review/{TEST_SESSION}/rate", json={
            "user_id": TEST_USER, "card_key": "go_went", "rating": "good"
        })
    with Session(engine) as s:
        review = s.query(SessionReview).filter_by(session_id=TEST_SESSION).first()
    assert review.is_user_rated is True
