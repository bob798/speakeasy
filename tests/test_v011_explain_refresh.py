"""V0.11 #8 · 解读缓存刷新机制单测

覆盖：
  - prompt 改了 → hash 变 → 旧 cache 自然 miss
  - force=True 跳过缓存重新生成 + 覆盖旧值
  - force 同 (user, text) 3s 内 debounce
"""
import asyncio
import json

import pytest
from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, ExplanationCache
from app.services import explain_service

USER = "user_explain_refresh"


@pytest.fixture(autouse=True)
def _reset():
    with OrmSession(engine) as s:
        s.query(ExplanationCache).delete()
        s.commit()
    explain_service._refresh_log.clear()
    yield


def test_hash_text_includes_prompt_hash():
    """同一段文本，不同 _PROMPT_HASH 时 hash 不同"""
    h1 = explain_service._hash_text("hello")
    original_hash = explain_service._PROMPT_HASH
    try:
        explain_service._PROMPT_HASH = "deadbeef"
        h2 = explain_service._hash_text("hello")
    finally:
        explain_service._PROMPT_HASH = original_hash
    assert h1 != h2


def test_explain_force_overwrites_cache(monkeypatch):
    """force=True 应跳过缓存，调 LLM，并覆盖旧值"""
    call_count = {"n": 0}

    class FakeClient:
        async def complete(self, messages, max_tokens=2000):
            call_count["n"] += 1
            return json.dumps({
                "meaning": f"v{call_count['n']}",
                "grammar": "g",
                "phrases": [],
                "liaison": [],
                "current_level_points": [],
                "next_level_points": [],
                "narration": "n",
            })

    monkeypatch.setattr("app.services.explain_service.get_client", lambda: FakeClient())

    # 第一次：建 cache
    r1 = asyncio.run(explain_service.explain_text("hello world", "sentence", USER))
    assert r1["cached"] is False
    assert call_count["n"] == 1
    assert r1["explanation"]["meaning"] == "v1"

    # 第二次：缓存命中，不调 LLM
    r2 = asyncio.run(explain_service.explain_text("hello world", "sentence", USER))
    assert r2["cached"] is True
    assert call_count["n"] == 1

    # 第三次：force=True，跳过缓存，重新调 LLM 并覆盖
    r3 = asyncio.run(explain_service.explain_text("hello world", "sentence", USER, force=True))
    assert r3["cached"] is False
    assert r3.get("regenerated") is True
    assert call_count["n"] == 2
    assert r3["explanation"]["meaning"] == "v2"

    # 再读：应是新值
    # （注意：force 后再 force 会被 debounce 卡，所以不能直接再 force；走普通读）
    # 等下一秒就好了——或者直接清 debounce log
    explain_service._refresh_log.clear()
    r4 = asyncio.run(explain_service.explain_text("hello world", "sentence", USER))
    assert r4["cached"] is True
    assert r4["explanation"]["meaning"] == "v2"


def test_force_debounce_blocks_rapid_refresh(monkeypatch):
    """3s 内重复 force 应被拒绝"""

    class FakeClient:
        async def complete(self, messages, max_tokens=2000):
            return json.dumps({
                "meaning": "x", "grammar": "g", "phrases": [], "liaison": [],
                "current_level_points": [], "next_level_points": [], "narration": "n",
            })

    monkeypatch.setattr("app.services.explain_service.get_client", lambda: FakeClient())

    # 先建 cache
    asyncio.run(explain_service.explain_text("debounce me", "sentence", USER))

    # 第一次 force：放行
    asyncio.run(explain_service.explain_text("debounce me", "sentence", USER, force=True))

    # 紧接着第二次 force：被 debounce 拒
    with pytest.raises(ValueError, match="刷新过于频繁"):
        asyncio.run(explain_service.explain_text("debounce me", "sentence", USER, force=True))

    # 不同用户互不干扰
    other_user = "other"
    # 不会被拒（不同 key）
    asyncio.run(explain_service.explain_text("debounce me", "sentence", other_user, force=True))


def test_cache_set_overwrite_replaces_existing():
    """直接调 _cache_set(overwrite=True) 应覆盖旧 explanation"""
    explain_service._cache_set("foo", "sentence", "B1", {"meaning": "old"})
    cached1 = explain_service._cache_get("foo", "sentence", "B1")
    assert cached1["meaning"] == "old"

    explain_service._cache_set("foo", "sentence", "B1", {"meaning": "new"}, overwrite=True)
    cached2 = explain_service._cache_get("foo", "sentence", "B1")
    assert cached2["meaning"] == "new"


def test_cache_set_no_overwrite_keeps_old():
    explain_service._cache_set("bar", "sentence", "B1", {"meaning": "old"})
    explain_service._cache_set("bar", "sentence", "B1", {"meaning": "new"}, overwrite=False)
    cached = explain_service._cache_get("bar", "sentence", "B1")
    assert cached["meaning"] == "old"
