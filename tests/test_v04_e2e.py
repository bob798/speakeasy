"""
V0.4 E2E — 完整 API 级端到端测试
user_id: test_user_v04_e2e
"""
import json
from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from main import app
from app.models.db import engine, Base, PronunciationCard, SubtitleSource

TEST_USER = "test_user_v04_e2e"


@pytest.fixture(autouse=True)
def cleanup():
    Base.metadata.create_all(engine)
    yield
    with OrmSession(engine) as s:
        s.query(PronunciationCard).filter_by(user_id=TEST_USER).delete()
        s.query(SubtitleSource).filter_by(user_id=TEST_USER).delete()
        s.commit()


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=True)


def _force_card_due(card_id):
    with OrmSession(engine) as s:
        card = s.query(PronunciationCard).filter_by(id=card_id).first()
        card_data = json.loads(card.fsrs_card_data)
        card_data["due"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        card.fsrs_card_data = json.dumps(card_data)
        s.commit()


def test_full_e2e_flow(client):
    """完整流程：文本 → 卡片 → 练习 → 复习 → 删除"""

    # 1. 加载手动文本
    resp = client.post("/practice/subtitles", json={
        "text": "I want to go.\nShe is happy.\nThey are playing.",
    })
    assert resp.status_code == 200
    segs = resp.json()["segments"]
    assert len(segs) == 3

    # 2. 创建 3 张发音卡
    resp = client.post("/practice/cards", json={
        "user_id": TEST_USER,
        "items": [
            {"text": segs[0]["content"], "context": ""},
            {"text": segs[1]["content"], "context": ""},
            {"text": segs[2]["content"], "context": ""},
        ],
    })
    assert resp.status_code == 201
    assert resp.json()["created"] == 3

    # 3. 查询卡片
    resp = client.get("/practice/cards", params={"user_id": TEST_USER})
    cards = resp.json()["cards"]
    assert len(cards) == 3
    for c in cards:
        assert c["status"] == "active"
        assert c["practice_count"] == 0
        assert c["fsrs_card_data"] != ""

    # 4. 评分第一张卡 good
    card1_id = cards[0]["id"]
    resp = client.post(f"/practice/cards/{card1_id}/review", json={
        "user_id": TEST_USER, "rating": "good",
    })
    assert resp.status_code == 200
    assert resp.json()["practice_count"] == 1

    # 5. 评分第二张卡 again
    card2_id = cards[1]["id"]
    resp = client.post(f"/practice/cards/{card2_id}/review", json={
        "user_id": TEST_USER, "rating": "again",
    })
    assert resp.json()["practice_count"] == 1

    # 6. 强制第二张卡到期 → due 列表
    _force_card_due(card2_id)
    resp = client.get("/practice/due", params={"user_id": TEST_USER})
    due_ids = [c["id"] for c in resp.json()["cards"]]
    assert card2_id in due_ids

    # 7. 删除第三张卡
    card3_id = cards[2]["id"]
    resp = client.delete(f"/practice/cards/{card3_id}", params={"user_id": TEST_USER})
    assert resp.json()["deleted"] is True

    # 8. 验证删除后状态
    resp = client.get("/practice/cards", params={"user_id": TEST_USER})
    remaining = resp.json()["cards"]
    assert len(remaining) == 2
    assert card3_id not in [c["id"] for c in remaining]

    # 9. Due 列表不含已删除卡
    resp = client.get("/practice/due", params={"user_id": TEST_USER})
    due_ids = [c["id"] for c in resp.json()["cards"]]
    assert card3_id not in due_ids


def test_duplicate_card_handling(client):
    """重复卡片跳过，text 规范化生效"""
    client.post("/practice/cards", json={
        "user_id": TEST_USER,
        "items": [{"text": "Hello World"}],
    })
    resp = client.post("/practice/cards", json={
        "user_id": TEST_USER,
        "items": [{"text": "  hello   world  "}],
    })
    assert resp.json()["created"] == 0
    assert resp.json()["skipped"] == 1


def test_pages_accessible(client):
    """所有页面路由可达"""
    assert client.get("/").status_code == 200
    assert client.get("/practice").status_code == 200
    assert client.get("/memory").status_code == 200
    assert client.get("/review").status_code == 200


def test_no_import_errors():
    """确认无循环依赖或 import 错误"""
    import app.models.db
    import app.services.fsrs_utils
    import app.services.subtitle_service
    import app.services.practice_service
    import app.routers.articles
