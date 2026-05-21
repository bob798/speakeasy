"""Translate 自动入生词本 — 翻译即占位 + 回填
user_id: test_user_translate_autovocab_*
"""
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.orm import Session as OrmSession

from main import app
from app.models.db import engine, Base, Vocabulary
from app.routers.auth import get_current_user_id_optional

USER = "test_user_translate_autovocab"
TRANSLATED_MOCK = "Hello World"


@pytest.fixture(autouse=True)
def cleanup():
    Base.metadata.create_all(engine)
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_translate_autovocab%")).delete(synchronize_session=False)
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_translate_autovocab%")).delete(synchronize_session=False)
        s.commit()
    app.dependency_overrides.pop(get_current_user_id_optional, None)


def _override_user(uid):
    app.dependency_overrides[get_current_user_id_optional] = lambda: uid


def _override_anon():
    app.dependency_overrides[get_current_user_id_optional] = lambda: None


def _count_vocab(user_id):
    with OrmSession(engine) as s:
        return s.query(Vocabulary).filter_by(user_id=user_id).count()


def _get_vocab(user_id):
    with OrmSession(engine) as s:
        rows = s.query(Vocabulary).filter_by(user_id=user_id).all()
        return [{"id": r.id, "source_text": r.source_text, "translated_text": r.translated_text,
                 "status": r.status, "item_type": r.item_type, "source_type": r.source_type} for r in rows]


@pytest.mark.asyncio
async def test_anonymous_translate_no_vocab():
    _override_anon()
    with patch("app.routers.translate.translate_text", new_callable=AsyncMock, return_value=TRANSLATED_MOCK):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/translate/text", json={"text": "你好世界", "direction": "zh2en"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["translated_text"] == TRANSLATED_MOCK
    assert data["saved_to_vocab"] is False
    assert data["vocab_id"] is None
    assert _count_vocab(USER) == 0


@pytest.mark.asyncio
async def test_logged_in_translate_creates_vocab():
    _override_user(USER)
    with patch("app.routers.translate.translate_text", new_callable=AsyncMock, return_value=TRANSLATED_MOCK):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/translate/text", json={"text": "你好世界", "direction": "zh2en"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["saved_to_vocab"] is True
    assert data["vocab_id"] is not None

    rows = _get_vocab(USER)
    assert len(rows) == 1
    assert rows[0]["source_text"] == "你好世界"
    assert rows[0]["translated_text"] == TRANSLATED_MOCK
    assert rows[0]["item_type"] == "sentence"
    assert rows[0]["source_type"] == "translate"


@pytest.mark.asyncio
async def test_logged_in_translate_idempotent():
    _override_user(USER)
    with patch("app.routers.translate.translate_text", new_callable=AsyncMock, return_value="First"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r1 = await c.post("/translate/text", json={"text": "重复文本", "direction": "zh2en"})

    with patch("app.routers.translate.translate_text", new_callable=AsyncMock, return_value="Second"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r2 = await c.post("/translate/text", json={"text": "重复文本", "direction": "zh2en"})

    assert r1.json()["vocab_id"] == r2.json()["vocab_id"]
    rows = _get_vocab(USER)
    assert len(rows) == 1
    assert rows[0]["translated_text"] == "Second"  # force=True 覆盖


@pytest.mark.asyncio
async def test_logged_in_translate_resurrects_deleted():
    _override_user(USER)
    # 先创建并软删
    with patch("app.routers.translate.translate_text", new_callable=AsyncMock, return_value="v1"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r1 = await c.post("/translate/text", json={"text": "删除测试", "direction": "zh2en"})
    vid = r1.json()["vocab_id"]

    # 软删
    with OrmSession(engine) as s:
        v = s.query(Vocabulary).filter_by(id=vid).first()
        v.status = "deleted"
        s.commit()

    # 再翻译同一文本
    with patch("app.routers.translate.translate_text", new_callable=AsyncMock, return_value="v2"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r2 = await c.post("/translate/text", json={"text": "删除测试", "direction": "zh2en"})

    assert r2.json()["saved_to_vocab"] is True
    rows = _get_vocab(USER)
    assert len(rows) == 1
    assert rows[0]["status"] == "active"
    assert rows[0]["translated_text"] == "v2"


@pytest.mark.asyncio
async def test_translate_failure_keeps_placeholder():
    _override_user(USER)
    with patch("app.routers.translate.translate_text", new_callable=AsyncMock, side_effect=Exception("LLM boom")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/translate/text", json={"text": "爆炸", "direction": "zh2en"})
    assert resp.status_code == 503
    # 占位条目仍在
    rows = _get_vocab(USER)
    assert len(rows) == 1
    assert rows[0]["translated_text"] == ""


@pytest.mark.asyncio
async def test_invalid_token_falls_back_anonymous():
    # Don't override dependency — let it be None (anonymous)
    _override_anon()
    with patch("app.routers.translate.translate_text", new_callable=AsyncMock, return_value=TRANSLATED_MOCK):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/translate/text", json={"text": "匿名测试", "direction": "zh2en"})
    assert resp.status_code == 200
    assert resp.json()["saved_to_vocab"] is False


@pytest.mark.asyncio
async def test_save_placeholder_failure_degrades():
    _override_user(USER)
    with patch("app.routers.translate.translate_text", new_callable=AsyncMock, return_value=TRANSLATED_MOCK), \
         patch("app.routers.translate.save_item", side_effect=Exception("DB boom")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/translate/text", json={"text": "降级", "direction": "zh2en"})
    assert resp.status_code == 200
    assert resp.json()["translated_text"] == TRANSLATED_MOCK
    assert resp.json()["saved_to_vocab"] is False


@pytest.mark.asyncio
async def test_backfill_failure_degrades():
    _override_user(USER)
    with patch("app.routers.translate.translate_text", new_callable=AsyncMock, return_value=TRANSLATED_MOCK), \
         patch("app.routers.translate.update_translated_text", side_effect=Exception("backfill boom")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/translate/text", json={"text": "回填失败", "direction": "zh2en"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["translated_text"] == TRANSLATED_MOCK
    assert data["saved_to_vocab"] is True  # 占位成功
    assert data["vocab_id"] is not None


@pytest.mark.asyncio
async def test_invalid_direction_no_placeholder():
    _override_user(USER)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/translate/text", json={"text": "方向错误", "direction": "xx"})
    assert resp.status_code == 400
    assert _count_vocab(USER) == 0
