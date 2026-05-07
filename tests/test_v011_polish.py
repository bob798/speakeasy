"""V0.11 · polish_service 单测"""
import asyncio
import json

import pytest
from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, PolishCard
from app.services import polish_service

USER = "user_polish_test"


@pytest.fixture(autouse=True)
def _reset():
    with OrmSession(engine) as s:
        s.query(PolishCard).filter_by(user_id=USER).delete()
        s.commit()
    yield


def test_save_card_with_dedup():
    a = polish_service.save_card(
        user_id=USER,
        original="I am gonna do it",
        polished="I am going to do it",
        explanation="正式场合不用 gonna",
        category="style",
    )
    b = polish_service.save_card(
        user_id=USER,
        original="I am gonna do it",
        polished="I am going to do it",
    )
    assert a["id"] == b["id"]
    assert a["category"] == "style"


def test_save_card_revives_deleted():
    c = polish_service.save_card(USER, "x", "y")
    polish_service.delete_card(c["id"], USER)
    again = polish_service.save_card(USER, "x", "y")
    assert again["id"] == c["id"]
    assert again["status"] == "active"


def test_save_card_invalid_category():
    with pytest.raises(ValueError, match="category"):
        polish_service.save_card(USER, "x", "y", category="bogus")


def test_save_card_empty_raises():
    with pytest.raises(ValueError):
        polish_service.save_card(USER, "  ", "y")


def test_list_filters_by_category():
    polish_service.save_card(USER, "a", "A", category="grammar")
    polish_service.save_card(USER, "b", "B", category="word_choice")
    polish_service.save_card(USER, "c", "C", category="grammar")
    rows = polish_service.list_cards(USER, category="grammar")
    assert len(rows) == 2
    rows2 = polish_service.list_cards(USER, category="word_choice")
    assert len(rows2) == 1


def test_rate_card_advances_due():
    c = polish_service.save_card(USER, "rate me", "rate me well", init_fsrs=True)
    res = polish_service.rate_card(c["id"], USER, "good")
    assert res["due"]
    assert res["card"]["last_reviewed_at"]
    assert res["card"]["review_count"] == 1


def test_rate_invalid():
    c = polish_service.save_card(USER, "x", "y")
    with pytest.raises(ValueError, match="rating"):
        polish_service.rate_card(c["id"], USER, "meh")


def test_rate_unknown_id():
    with pytest.raises(LookupError):
        polish_service.rate_card(999999, USER, "good")


def test_polish_text_uses_llm(monkeypatch):
    """LLM 返回结构化 JSON · 应解析出 polished + segments"""

    class FakeClient:
        async def complete(self, messages, max_tokens=2000):
            return json.dumps({
                "polished": "I am going to do it tomorrow.",
                "segments": [
                    {
                        "original": "gonna",
                        "replacement": "going to",
                        "explanation": "更正式",
                        "category": "style",
                    },
                ],
                "overall_note": "整体偏口语，已改为标准书面",
            })

    monkeypatch.setattr("app.services.polish_service.get_client", lambda: FakeClient())
    result = asyncio.run(polish_service.polish_text("I'm gonna do it tomorrow."))
    assert "going to" in result["polished"]
    assert len(result["segments"]) == 1
    assert result["segments"][0]["category"] == "style"


def test_polish_text_filters_invalid_category(monkeypatch):
    class FakeClient:
        async def complete(self, messages, max_tokens=2000):
            return json.dumps({
                "polished": "ok",
                "segments": [
                    {"original": "a", "replacement": "b", "explanation": "x", "category": "bogus"},
                ],
            })

    monkeypatch.setattr("app.services.polish_service.get_client", lambda: FakeClient())
    result = asyncio.run(polish_service.polish_text("hello"))
    assert result["segments"][0]["category"] == ""  # 非法被清空


def test_polish_text_garbage_falls_back(monkeypatch):
    class GarbageClient:
        async def complete(self, messages, max_tokens=2000):
            return "this is not json"

    monkeypatch.setattr("app.services.polish_service.get_client", lambda: GarbageClient())
    result = asyncio.run(polish_service.polish_text("hello"))
    # 兜底：返回原文 + 空 segments
    assert result["polished"] == "hello"
    assert result["segments"] == []


def test_polish_text_empty_raises():
    with pytest.raises(ValueError):
        asyncio.run(polish_service.polish_text(""))


def test_polish_chat_iterates(monkeypatch):
    """chat 一轮 · 返回新 polished + summary"""

    class FakeClient:
        async def complete(self, messages, max_tokens=2000):
            return json.dumps({
                "polished": "I'm gonna do it tomorrow, no doubt.",
                "summary": "改回口语化并加强语气",
            })

    monkeypatch.setattr("app.services.polish_service.get_client", lambda: FakeClient())
    result = asyncio.run(polish_service.polish_chat_once(
        original="I am going to do it",
        current_polished="I am going to do it tomorrow.",
        user_instruction="更口语",
    ))
    assert "gonna" in result["polished"]
    assert result["summary"]


def test_polish_chat_garbage_keeps_current(monkeypatch):
    class GarbageClient:
        async def complete(self, messages, max_tokens=2000):
            return "garbage"

    monkeypatch.setattr("app.services.polish_service.get_client", lambda: GarbageClient())
    result = asyncio.run(polish_service.polish_chat_once(
        original="x",
        current_polished="y",
        user_instruction="more formal",
    ))
    assert result["polished"] == "y"  # 维持当前版本
