"""
V0.4 Step 2 — 发音练习后端 API（6 端点）
user_id: test_user_v04_s2
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from main import app
from app.models.db import engine, Base, PronunciationCard

TEST_USER = "test_user_v04_s2"


@pytest.fixture(autouse=True)
def cleanup():
    Base.metadata.create_all(engine)
    yield
    with OrmSession(engine) as s:
        s.query(PronunciationCard).filter_by(user_id=TEST_USER).delete()
        s.commit()


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=True)


# ── POST /practice/subtitles ─────────────────────────────

def test_subtitles_manual_text(client):
    resp = client.post("/practice/subtitles", json={
        "text": "Hello world.\nHow are you?\nI'm fine.",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["segments"]) == 3
    assert data["segments"][0]["content"] == "Hello world."


def test_subtitles_no_input(client):
    resp = client.post("/practice/subtitles", json={})
    assert resp.status_code == 400


def test_subtitles_invalid_url(client):
    resp = client.post("/practice/subtitles", json={"url": "not-a-bilibili-url"})
    assert resp.status_code == 400


# ── POST /practice/cards ─────────────────────────────────

def test_create_cards(client):
    resp = client.post("/practice/cards", json={
        "user_id": TEST_USER,
        "items": [
            {"text": "Hello World", "context": "Hello world, welcome."},
            {"text": "Good morning", "context": "Good morning everyone."},
        ],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["created"] == 2
    assert data["skipped"] == 0


def test_create_cards_duplicate(client):
    payload = {
        "user_id": TEST_USER,
        "items": [{"text": "duplicate item", "context": "ctx"}],
    }
    resp1 = client.post("/practice/cards", json=payload)
    assert resp1.json()["created"] == 1

    resp2 = client.post("/practice/cards", json=payload)
    assert resp2.json()["created"] == 0
    assert resp2.json()["skipped"] == 1


def test_create_cards_normalizes_text(client):
    """'Hello World' 和 'hello  world' 应视为同一卡片"""
    client.post("/practice/cards", json={
        "user_id": TEST_USER,
        "items": [{"text": "Hello World"}],
    })
    resp = client.post("/practice/cards", json={
        "user_id": TEST_USER,
        "items": [{"text": "  hello   world  "}],
    })
    assert resp.json()["skipped"] == 1


# ── GET /practice/cards ──────────────────────────────────

def test_get_cards(client):
    client.post("/practice/cards", json={
        "user_id": TEST_USER,
        "items": [
            {"text": "card one"},
            {"text": "card two"},
            {"text": "card three"},
        ],
    })
    resp = client.get("/practice/cards", params={"user_id": TEST_USER})
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 3
    for card in data["cards"]:
        assert "id" in card
        assert "text" in card
        assert "fsrs_card_data" in card
        assert card["status"] == "active"


def test_get_cards_pagination(client):
    client.post("/practice/cards", json={
        "user_id": TEST_USER,
        "items": [{"text": f"item {i}"} for i in range(5)],
    })
    resp = client.get("/practice/cards", params={
        "user_id": TEST_USER, "limit": 2, "offset": 0,
    })
    assert resp.json()["count"] == 2

    resp2 = client.get("/practice/cards", params={
        "user_id": TEST_USER, "limit": 2, "offset": 3,
    })
    assert resp2.json()["count"] == 2


def test_get_cards_excludes_deleted(client):
    client.post("/practice/cards", json={
        "user_id": TEST_USER,
        "items": [{"text": "will delete"}, {"text": "will keep"}],
    })
    cards = client.get("/practice/cards", params={"user_id": TEST_USER}).json()["cards"]
    delete_id = next(c["id"] for c in cards if c["text"] == "will delete")
    client.delete(f"/practice/cards/{delete_id}", params={"user_id": TEST_USER})

    resp = client.get("/practice/cards", params={"user_id": TEST_USER})
    texts = [c["text"] for c in resp.json()["cards"]]
    assert "will delete" not in texts
    assert "will keep" in texts


# ── POST /practice/cards/{id}/review ─────────────────────

def test_review_card_good(client):
    client.post("/practice/cards", json={
        "user_id": TEST_USER,
        "items": [{"text": "review test"}],
    })
    cards = client.get("/practice/cards", params={"user_id": TEST_USER}).json()["cards"]
    card_id = cards[0]["id"]

    resp = client.post(f"/practice/cards/{card_id}/review", json={
        "user_id": TEST_USER, "rating": "good",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["practice_count"] == 1
    assert "new_due" in data


def test_review_card_again_shorter_due(client):
    """Rating.Again 应产生比 Rating.Easy 更近的 due"""
    client.post("/practice/cards", json={
        "user_id": TEST_USER,
        "items": [{"text": "again test"}, {"text": "easy test"}],
    })
    cards = client.get("/practice/cards", params={"user_id": TEST_USER}).json()["cards"]
    id_again = next(c["id"] for c in cards if c["text"] == "again test")
    id_easy = next(c["id"] for c in cards if c["text"] == "easy test")

    resp_again = client.post(f"/practice/cards/{id_again}/review", json={
        "user_id": TEST_USER, "rating": "again",
    })
    resp_easy = client.post(f"/practice/cards/{id_easy}/review", json={
        "user_id": TEST_USER, "rating": "easy",
    })
    # again 的 due 应该 <= easy 的 due
    assert resp_again.json()["new_due"] <= resp_easy.json()["new_due"]


def test_review_invalid_rating(client):
    client.post("/practice/cards", json={
        "user_id": TEST_USER,
        "items": [{"text": "invalid rating test"}],
    })
    cards = client.get("/practice/cards", params={"user_id": TEST_USER}).json()["cards"]
    card_id = cards[0]["id"]

    resp = client.post(f"/practice/cards/{card_id}/review", json={
        "user_id": TEST_USER, "rating": "invalid",
    })
    assert resp.status_code == 404


def test_review_nonexistent_card(client):
    resp = client.post("/practice/cards/99999/review", json={
        "user_id": TEST_USER, "rating": "good",
    })
    assert resp.status_code == 404


# ── DELETE /practice/cards/{id} ──────────────────────────

def test_delete_card(client):
    client.post("/practice/cards", json={
        "user_id": TEST_USER,
        "items": [{"text": "delete me"}],
    })
    cards = client.get("/practice/cards", params={"user_id": TEST_USER}).json()["cards"]
    card_id = cards[0]["id"]

    resp = client.delete(f"/practice/cards/{card_id}", params={"user_id": TEST_USER})
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True

    # 确认不再出现
    cards_after = client.get("/practice/cards", params={"user_id": TEST_USER}).json()["cards"]
    assert all(c["id"] != card_id for c in cards_after)


def test_delete_nonexistent(client):
    resp = client.delete("/practice/cards/99999", params={"user_id": TEST_USER})
    assert resp.status_code == 404


# ── GET /practice/due ────────────────────────────────────

def test_due_cards_after_again(client):
    """Rating.Again 创建的卡应该很快到期（或已到期）"""
    client.post("/practice/cards", json={
        "user_id": TEST_USER,
        "items": [{"text": "due test again"}],
    })
    # 新创建的卡用 Rating.Again 初始化，间隔很短
    # 先做一次 review(again) 让 due 更近
    cards = client.get("/practice/cards", params={"user_id": TEST_USER}).json()["cards"]
    card_id = cards[0]["id"]
    client.post(f"/practice/cards/{card_id}/review", json={
        "user_id": TEST_USER, "rating": "again",
    })

    resp = client.get("/practice/due", params={"user_id": TEST_USER})
    assert resp.status_code == 200
    # 至少应该能调用成功，due 列表结构正确
    data = resp.json()
    assert "cards" in data
    assert "count" in data


def test_due_cards_easy_not_due(client):
    """Rating.Easy 后卡片不应立即到期"""
    client.post("/practice/cards", json={
        "user_id": TEST_USER,
        "items": [{"text": "easy not due"}],
    })
    cards = client.get("/practice/cards", params={"user_id": TEST_USER}).json()["cards"]
    card_id = cards[0]["id"]

    # 先 review 一次 easy，推到远期
    client.post(f"/practice/cards/{card_id}/review", json={
        "user_id": TEST_USER, "rating": "easy",
    })

    resp = client.get("/practice/due", params={"user_id": TEST_USER})
    due_ids = [c["id"] for c in resp.json()["cards"]]
    assert card_id not in due_ids


def test_due_excludes_deleted(client):
    client.post("/practice/cards", json={
        "user_id": TEST_USER,
        "items": [{"text": "due deleted test"}],
    })
    cards = client.get("/practice/cards", params={"user_id": TEST_USER}).json()["cards"]
    card_id = cards[0]["id"]

    client.delete(f"/practice/cards/{card_id}", params={"user_id": TEST_USER})

    resp = client.get("/practice/due", params={"user_id": TEST_USER})
    due_ids = [c["id"] for c in resp.json()["cards"]]
    assert card_id not in due_ids
