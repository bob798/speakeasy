"""V0.11 #12 P1 · 写作偏好提取 + system prompt 注入 单测"""
import asyncio
import json

import pytest
from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, PolishCard, UserFact
from app.services import polish_service, polish_facts

USER = "user_polish_p1"


@pytest.fixture(autouse=True)
def _reset():
    with OrmSession(engine) as s:
        s.query(PolishCard).filter_by(user_id=USER).delete()
        s.query(UserFact).filter_by(user_id=USER).delete()
        s.commit()
    yield


# ── 写作偏好抽取 ─────────────────────────────────────────────

def test_extract_skips_when_history_too_short(monkeypatch):
    """history 不足 2 轮 · 不调 LLM · 不入库"""

    class BoomClient:
        async def complete(self, *a, **k):
            raise AssertionError("不应被调用")

    monkeypatch.setattr("app.services.polish_facts.get_client", lambda: BoomClient())
    n = asyncio.run(polish_facts.extract_and_save_writing_facts(
        user_id=USER, original="hi", polished="hi",
        chat_history=[{"role": "user", "content": "x"}],
    ))
    assert n == 0


def test_extract_saves_facts(monkeypatch):
    class FakeClient:
        async def complete(self, *a, **k):
            return json.dumps([
                "倾向使用主动语态",
                "经常漏掉冠词",
            ])

    monkeypatch.setattr("app.services.polish_facts.get_client", lambda: FakeClient())
    history = [
        {"role": "user", "content": "更口语"},
        {"role": "assistant", "content": "OK"},
        {"role": "user", "content": "再短一点"},
    ]
    n = asyncio.run(polish_facts.extract_and_save_writing_facts(
        user_id=USER, original="long original text",
        polished="short polished",
        chat_history=history,
    ))
    assert n == 2
    facts = polish_facts.get_writing_facts(USER)
    assert len(facts) == 2
    assert "主动语态" in facts[0] or "主动语态" in facts[1]


def test_extract_idempotent_on_same_original(monkeypatch):
    class FakeClient:
        async def complete(self, *a, **k):
            return json.dumps(["x"])

    monkeypatch.setattr("app.services.polish_facts.get_client", lambda: FakeClient())
    history = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]

    n1 = asyncio.run(polish_facts.extract_and_save_writing_facts(
        USER, "same original", "p", history,
    ))
    n2 = asyncio.run(polish_facts.extract_and_save_writing_facts(
        USER, "same original", "p", history,
    ))
    assert n1 == 1
    assert n2 == 0  # 第二次幂等跳过


def test_extract_garbage_returns_zero(monkeypatch):
    class GarbageClient:
        async def complete(self, *a, **k):
            return "not json"

    monkeypatch.setattr("app.services.polish_facts.get_client", lambda: GarbageClient())
    history = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
    n = asyncio.run(polish_facts.extract_and_save_writing_facts(USER, "x", "y", history))
    assert n == 0


# ── 高频 category 统计 ─────────────────────────────────────

def test_top_categories_orders_by_freq():
    polish_service.save_card(USER, "a1", "A1", category="grammar")
    polish_service.save_card(USER, "a2", "A2", category="grammar")
    polish_service.save_card(USER, "a3", "A3", category="grammar")
    polish_service.save_card(USER, "b1", "B1", category="word_choice")
    polish_service.save_card(USER, "b2", "B2", category="word_choice")
    polish_service.save_card(USER, "c1", "C1", category="style")
    cats = polish_facts.get_top_categories(USER)
    assert cats[0] == "grammar"
    assert cats[1] == "word_choice"
    assert cats[2] == "style"


def test_top_categories_empty_user():
    assert polish_facts.get_top_categories("ghost_user") == []


# ── system prompt addon ──────────────────────────────────

def test_addon_empty_when_no_history():
    assert polish_facts.build_polish_addon("ghost_user_no_history") == ""


def test_addon_includes_facts_and_categories(monkeypatch):
    # 先插一条 polish fact（直接 DB 操作绕过 LLM）
    with OrmSession(engine) as s:
        s.add(UserFact(
            user_id=USER,
            content="倾向用 wanna / gonna",
            source_session_id="polish:test_seed",
        ))
        s.commit()
    polish_service.save_card(USER, "x", "X", category="grammar")
    polish_service.save_card(USER, "y", "Y", category="grammar")

    addon = polish_facts.build_polish_addon(USER)
    assert "倾向用 wanna" in addon
    assert "语法错误" in addon  # grammar 的中文展示


# ── polish_text user_id 注入 ─────────────────────────────

def test_polish_text_passes_addon_to_llm(monkeypatch):
    """有用户偏好时 system prompt 应包含 addon"""
    captured = {}

    class Spy:
        async def complete(self, messages, max_tokens=2000):
            captured["system"] = messages[0]["content"]
            return json.dumps({"polished": "ok", "segments": [], "overall_note": ""})

    monkeypatch.setattr("app.services.polish_service.get_client", lambda: Spy())

    # 先放一条 fact + 一条 high-freq category
    with OrmSession(engine) as s:
        s.add(UserFact(
            user_id=USER,
            content="偏好简短句",
            source_session_id="polish:seed",
        ))
        s.commit()
    polish_service.save_card(USER, "a", "A", category="grammar")

    asyncio.run(polish_service.polish_text("hello", user_id=USER))
    assert "偏好简短句" in captured["system"]
    assert "语法错误" in captured["system"]


def test_polish_text_no_user_no_addon(monkeypatch):
    captured = {}

    class Spy:
        async def complete(self, messages, max_tokens=2000):
            captured["system"] = messages[0]["content"]
            return json.dumps({"polished": "ok", "segments": []})

    monkeypatch.setattr("app.services.polish_service.get_client", lambda: Spy())
    asyncio.run(polish_service.polish_text("hello"))
    assert "关于这位用户" not in captured["system"]


# ── save_card 默认 init_fsrs=True ────────────────────────

def test_save_card_defaults_to_fsrs_init():
    c = polish_service.save_card(USER, "auto fsrs", "Auto FSRS")
    # init_fsrs 默认 True · due 不为 None
    assert c["due"] is not None


def test_save_card_explicit_no_fsrs():
    c = polish_service.save_card(USER, "no fsrs", "No FSRS", init_fsrs=False)
    assert c["due"] is None
