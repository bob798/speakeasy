"""
V0.5 Step 3 — /translate API 路由
user_id: test_user_v05_step3
"""
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from main import app
from app.models.db import engine, Base, Vocabulary

TEST_USER = "test_user_v05_step3"

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup():
    Base.metadata.create_all(engine)
    yield
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter_by(user_id=TEST_USER).delete()
        s.commit()


# ── POST /translate/text ────────────────────────────────────

def test_translate_text_success():
    with patch("app.routers.translate.translate_text", new=AsyncMock(return_value="I have worked on recommendation systems")):
        resp = client.post("/translate/text", json={"text": "我做过推荐系统", "direction": "zh2en"})
    assert resp.status_code == 200
    data = resp.json()
    assert "translated_text" in data
    assert len(data["translated_text"]) > 0


def test_translate_text_exceeds_limit():
    long_text = "你好 " * 400  # > 1000 chars
    resp = client.post("/translate/text", json={"text": long_text, "direction": "zh2en"})
    assert resp.status_code == 400


def test_translate_text_empty():
    resp = client.post("/translate/text", json={"text": "  ", "direction": "zh2en"})
    assert resp.status_code == 400


def test_translate_text_model_error():
    with patch("app.routers.translate.translate_text", new=AsyncMock(side_effect=Exception("model unavailable: api_key=sk-xxx"))):
        resp = client.post("/translate/text", json={"text": "hello", "direction": "en2zh"})
    assert resp.status_code == 503
    data = resp.json()
    assert "detail" in data
    # 不应泄露原始异常信息（例如 api_key 片段）
    assert "api_key" not in data["detail"]
    assert "sk-xxx" not in data["detail"]


def test_vocabulary_create_invalid_direction_returns_400():
    resp = client.post("/translate/vocabulary", json={
        "user_id": TEST_USER,
        "source_text": "foo",
        "translated_text": "bar",
        "direction": "xx",
    })
    assert resp.status_code == 400
    assert "无效的翻译方向" in resp.json()["detail"]


# ── Vocabulary CRUD 生命周期 ────────────────────────────────

def test_vocabulary_crud_lifecycle():
    # 1. 创建
    resp = client.post("/translate/vocabulary", json={
        "user_id": TEST_USER,
        "source_text": "机器学习",
        "translated_text": "machine learning",
        "direction": "zh2en",
    })
    assert resp.status_code == 201
    item = resp.json()
    vid = item["id"]
    assert item["source_text"] == "机器学习"
    assert item["status"] == "active"

    # 2. 列表可见
    resp = client.get(f"/translate/vocabulary?user_id={TEST_USER}")
    assert resp.status_code == 200
    data = resp.json()
    ids = [v["id"] for v in data["items"]]
    assert vid in ids

    # 3. 删除
    resp = client.delete(f"/translate/vocabulary/{vid}?user_id={TEST_USER}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True

    # 4. 列表不可见
    resp = client.get(f"/translate/vocabulary?user_id={TEST_USER}")
    ids_after = [v["id"] for v in resp.json()["items"]]
    assert vid not in ids_after


def test_vocabulary_delete_nonexistent():
    resp = client.delete(f"/translate/vocabulary/99999?user_id={TEST_USER}")
    assert resp.status_code == 404


def test_vocabulary_list_pagination():
    for i in range(4):
        client.post("/translate/vocabulary", json={
            "user_id": TEST_USER,
            "source_text": f"词语{i}",
            "translated_text": f"word{i}",
            "direction": "zh2en",
        })

    resp = client.get(f"/translate/vocabulary?user_id={TEST_USER}&limit=2&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    assert len(data["items"]) == 2
