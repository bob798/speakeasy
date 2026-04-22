"""
V0.5 句子/单词解读 — 服务 + 缓存 + CEFR 等级分层
user_id: test_user_v05_explain
"""
import json

import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, Base, ExplanationCache, UserProfile
from app.services.explain_service import explain_text

TEST_USER = "test_user_v05_explain"


def _mock_sentence_explanation() -> str:
    return json.dumps({
        "meaning": "Java 在企业级开发中仍然流行",
        "grammar": "主句 + remain 系动词 + 形容词短语",
        "phrases": [{"phrase": "in the enterprise", "note": "在企业中"}],
        "current_level_points": ["remain 作系动词"],
        "next_level_points": ["表达行业趋势的固定搭配"],
    }, ensure_ascii=False)


def _mock_word_explanation() -> str:
    return json.dumps({
        "phonetic": "/rɪˈmeɪn/",
        "pos": "动词",
        "definitions": ["保持；仍然是"],
        "examples": [{"en": "He remained silent.", "zh": "他保持沉默。"}],
        "synonyms": ["stay", "continue"],
        "antonyms": ["leave"],
        "current_level_usage": "remain + 形容词",
        "next_level_usage": "remain to be seen 固定搭配",
    }, ensure_ascii=False)


@pytest.fixture(autouse=True)
def cleanup():
    Base.metadata.create_all(engine)
    with OrmSession(engine) as s:
        s.query(ExplanationCache).delete()
        s.query(UserProfile).filter_by(user_id=TEST_USER).delete()
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(ExplanationCache).delete()
        s.query(UserProfile).filter_by(user_id=TEST_USER).delete()
        s.commit()


# ── 基础行为 ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_explain_sentence_basic():
    with patch("app.services.explain_service.get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=_mock_sentence_explanation())
        mock_get.return_value = mock_client

        result = await explain_text("Java remains popular", "sentence", TEST_USER)
        assert result["cached"] is False
        assert result["explanation"]["meaning"].startswith("Java")
        assert "remain 作系动词" in result["explanation"]["current_level_points"]


@pytest.mark.asyncio
async def test_explain_word_basic():
    with patch("app.services.explain_service.get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=_mock_word_explanation())
        mock_get.return_value = mock_client

        result = await explain_text("remain", "word", TEST_USER, context="Java remains popular")
        assert result["explanation"]["pos"] == "动词"
        assert result["explanation"]["phonetic"] == "/rɪˈmeɪn/"


@pytest.mark.asyncio
async def test_explain_empty_raises():
    with pytest.raises(ValueError, match="不能为空"):
        await explain_text("", "sentence", TEST_USER)


@pytest.mark.asyncio
async def test_explain_invalid_kind():
    with pytest.raises(ValueError, match="无效"):
        await explain_text("hello", "paragraph", TEST_USER)


@pytest.mark.asyncio
async def test_explain_too_long():
    long_text = "a" * 2001
    with pytest.raises(ValueError, match="2000"):
        await explain_text(long_text, "sentence", TEST_USER)


# ── CEFR 等级上下文注入 ─────────────────────────────────────

@pytest.mark.asyncio
async def test_explain_uses_user_cefr_level():
    # 预置用户 profile 为 C1
    with OrmSession(engine) as s:
        s.add(UserProfile(user_id=TEST_USER, cefr_level="C1"))
        s.commit()

    with patch("app.services.explain_service.get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=_mock_sentence_explanation())
        mock_get.return_value = mock_client

        result = await explain_text("Hello", "sentence", TEST_USER)
        # prompt 里应该带 C1
        system_msg = [m for m in mock_client.complete.call_args[0][0] if m["role"] == "system"][0]
        assert "C1" in system_msg["content"]
        assert result["cefr_level"] == "C1"


@pytest.mark.asyncio
async def test_explain_defaults_to_b1_when_no_level():
    with patch("app.services.explain_service.get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=_mock_sentence_explanation())
        mock_get.return_value = mock_client

        result = await explain_text("Hello", "sentence", TEST_USER)
        assert result["cefr_level"] == "B1"
        system_msg = [m for m in mock_client.complete.call_args[0][0] if m["role"] == "system"][0]
        assert "B1" in system_msg["content"]


# ── 缓存 ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cache_hit_skips_llm():
    with patch("app.services.explain_service.get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=_mock_sentence_explanation())
        mock_get.return_value = mock_client

        r1 = await explain_text("Hello world", "sentence", TEST_USER)
        r2 = await explain_text("Hello world", "sentence", TEST_USER)

        assert r1["explanation"] == r2["explanation"]
        assert r1["cached"] is False
        assert r2["cached"] is True
        assert mock_client.complete.await_count == 1


@pytest.mark.asyncio
async def test_cache_separates_by_kind():
    """同一文本 sentence 和 word 缓存独立"""
    with patch("app.services.explain_service.get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=_mock_sentence_explanation())
        mock_get.return_value = mock_client

        await explain_text("remain", "sentence", TEST_USER)

        mock_client.complete = AsyncMock(return_value=_mock_word_explanation())
        result = await explain_text("remain", "word", TEST_USER)
        assert result["cached"] is False
        assert result["explanation"]["pos"] == "动词"


@pytest.mark.asyncio
async def test_cache_separates_by_cefr_level():
    """同一文本不同 CEFR 等级独立缓存"""
    with patch("app.services.explain_service.get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=_mock_sentence_explanation())
        mock_get.return_value = mock_client

        # 用户无等级 → B1
        await explain_text("Hello", "sentence", TEST_USER)
        assert mock_client.complete.await_count == 1

        # 设置为 C1 后重查，应触发新调用
        with OrmSession(engine) as s:
            s.add(UserProfile(user_id=TEST_USER, cefr_level="C1"))
            s.commit()
        await explain_text("Hello", "sentence", TEST_USER)
        assert mock_client.complete.await_count == 2


# ── 解析健壮性 ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_code_fence_wrapped_response_is_parsed():
    wrapped = "```json\n" + _mock_sentence_explanation() + "\n```"
    with patch("app.services.explain_service.get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=wrapped)
        mock_get.return_value = mock_client

        result = await explain_text("Hello", "sentence", TEST_USER)
        assert "meaning" in result["explanation"]


@pytest.mark.asyncio
async def test_bad_json_raises_value_error():
    with patch("app.services.explain_service.get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value="not a json at all")
        mock_get.return_value = mock_client

        with pytest.raises(ValueError, match="JSON"):
            await explain_text("Hello", "sentence", TEST_USER)
