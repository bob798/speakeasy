"""
V0.4 Step 5 — FSRS 复习调度正确性
user_id: test_user_v04_s5
"""
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from main import app
from app.models.db import engine, Base, PronunciationCard

TEST_USER = "test_user_v04_s5"


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


def _create_card(client, text):
    client.post("/practice/cards", json={
        "user_id": TEST_USER,
        "items": [{"text": text}],
    })
    cards = client.get("/practice/cards", params={"user_id": TEST_USER}).json()["cards"]
    return next(c for c in cards if c["text"] == text.strip().lower())


def _force_card_due(card_id):
    """直接在 DB 中将卡片的 FSRS due 设为过去时间"""
    with OrmSession(engine) as s:
        card = s.query(PronunciationCard).filter_by(id=card_id).first()
        card_data = json.loads(card.fsrs_card_data)
        card_data["due"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        card.fsrs_card_data = json.dumps(card_data)
        s.commit()


def test_again_card_in_due_queue(client):
    """卡片 due 日期过期后应出现在 due 队列"""
    card = _create_card(client, "test again due")
    _force_card_due(card["id"])
    resp = client.get("/practice/due", params={"user_id": TEST_USER})
    due_ids = [c["id"] for c in resp.json()["cards"]]
    assert card["id"] in due_ids


def test_easy_card_not_in_due_queue(client):
    """Rating.Easy 评分后卡片不应出现在 due 队列"""
    card = _create_card(client, "test easy not due")
    client.post(f"/practice/cards/{card['id']}/review", json={
        "user_id": TEST_USER, "rating": "easy",
    })
    resp = client.get("/practice/due", params={"user_id": TEST_USER})
    due_ids = [c["id"] for c in resp.json()["cards"]]
    assert card["id"] not in due_ids


def test_deleted_card_not_in_due_queue(client):
    """已删除卡片不应出现在 due 队列"""
    card = _create_card(client, "test delete not due")
    _force_card_due(card["id"])
    client.delete(f"/practice/cards/{card['id']}", params={"user_id": TEST_USER})
    resp = client.get("/practice/due", params={"user_id": TEST_USER})
    due_ids = [c["id"] for c in resp.json()["cards"]]
    assert card["id"] not in due_ids


def test_due_limit(client):
    """limit 参数应限制返回数量"""
    for i in range(5):
        card = _create_card(client, f"limit test {i}")
        _force_card_due(card["id"])
    resp = client.get("/practice/due", params={"user_id": TEST_USER, "limit": 3})
    assert resp.json()["count"] <= 3


def test_full_loop_create_practice_review(client):
    """端到端 API 级测试：创建 → 练习 → 复习"""
    # 1. 加载文本
    resp = client.post("/practice/subtitles", json={"text": "hello world\ngood morning"})
    assert len(resp.json()["segments"]) == 2

    # 2. 创建卡片
    resp = client.post("/practice/cards", json={
        "user_id": TEST_USER,
        "items": [{"text": "hello world"}, {"text": "good morning"}],
    })
    assert resp.json()["created"] == 2

    # 3. 获取卡片
    cards = client.get("/practice/cards", params={"user_id": TEST_USER}).json()["cards"]
    assert len(cards) == 2

    # 4. 强制 due → 应在 due 列表
    card_id = cards[0]["id"]
    _force_card_due(card_id)
    due = client.get("/practice/due", params={"user_id": TEST_USER}).json()
    assert card_id in [c["id"] for c in due["cards"]]

    # 5. 评分 easy → 不在 due 列表（due 推到未来）
    client.post(f"/practice/cards/{card_id}/review", json={
        "user_id": TEST_USER, "rating": "easy",
    })
    due = client.get("/practice/due", params={"user_id": TEST_USER}).json()
    assert card_id not in [c["id"] for c in due["cards"]]
