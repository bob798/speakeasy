"""
V0.7 Step 10 — 句子解读 NDJSON 流式输出
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session as OrmSession
from fastapi.testclient import TestClient

from main import app
from app.models.db import engine, Base, ExplanationCache, User
from app.services.explain_service import stream_sentence_explanation

TEST_USER = "test_user_v07_step10"
TEST_EMAIL = "apitest_stream_v07@test.com"
TEST_PASSWORD = "password_stream_v07"

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup():
    Base.metadata.create_all(engine)
    with OrmSession(engine) as s:
        s.query(ExplanationCache).delete()
        s.query(User).filter(User.email == TEST_EMAIL).delete(synchronize_session=False)
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(ExplanationCache).delete()
        s.query(User).filter(User.email == TEST_EMAIL).delete(synchronize_session=False)
        s.commit()


def _mock_stream_client(chunks):
    async def _gen(messages, **kwargs):
        for c in chunks:
            yield c
    m = MagicMock()
    m.chat_stream_messages = _gen
    return m


# ── service 层 ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stream_yields_fields_in_order_and_caches():
    # 模拟 LLM 分块吐出完整 NDJSON
    lines = (
        '{"field":"meaning","value":"今天下雨"}\n'
        '{"field":"grammar","value":"主谓句"}\n'
        '{"field":"phrases","value":[]}\n'
        '{"field":"liaison","value":[]}\n'
        '{"field":"current_level_points","value":["一般现在时"]}\n'
        '{"field":"next_level_points","value":[]}\n'
        '{"field":"narration","value":"这句话说今天下雨"}\n'
    )
    # 切成 3 块模拟流
    third = len(lines) // 3
    chunks = [lines[:third], lines[third:third*2], lines[third*2:]]

    with patch("app.services.explain_service.get_client",
               return_value=_mock_stream_client(chunks)):
        events = []
        async for ev in stream_sentence_explanation("It's raining today.", TEST_USER):
            events.append(json.loads(ev))

    fields = [e.get("field") for e in events if "field" in e]
    assert fields == ["meaning", "grammar", "phrases", "liaison",
                      "current_level_points", "next_level_points", "narration"]
    # 结束事件
    assert any(e.get("_done") for e in events)

    # 入 cache
    with OrmSession(engine) as s:
        row = s.query(ExplanationCache).filter_by(kind="sentence").first()
        assert row is not None
        data = json.loads(row.explanation)
        assert data["meaning"] == "今天下雨"
        assert data["narration"].startswith("这句话")


@pytest.mark.asyncio
async def test_stream_cached_returns_fast_single_event():
    # 先填一条 cache
    from app.services.explain_service import _cache_set
    _cache_set("Cached sentence.", "sentence", "B1", {
        "meaning": "缓存", "grammar": "", "phrases": [], "liaison": [],
        "current_level_points": [], "next_level_points": [], "narration": "",
    })

    with patch("app.services.explain_service.get_client") as mock_get:
        # 不应调 LLM
        mock_client = MagicMock()
        mock_client.chat_stream_messages = MagicMock(side_effect=AssertionError("不该调 LLM"))
        mock_get.return_value = mock_client

        events = []
        async for ev in stream_sentence_explanation("Cached sentence.", TEST_USER):
            events.append(json.loads(ev))

    assert len(events) == 1
    assert events[0].get("_cached") is True
    assert events[0]["explanation"]["meaning"] == "缓存"


@pytest.mark.asyncio
async def test_stream_ignores_malformed_lines():
    lines = (
        "not-json\n"
        '{"field":"meaning","value":"ok"}\n'
        '{"garbage":true}\n'       # 无 field
        '{"field":"grammar","value":"g"}\n'
    )
    with patch("app.services.explain_service.get_client",
               return_value=_mock_stream_client([lines])):
        events = []
        async for ev in stream_sentence_explanation("Robust.", TEST_USER):
            events.append(json.loads(ev))
    fields = [e.get("field") for e in events if "field" in e]
    assert fields == ["meaning", "grammar"]


# ── endpoint ────────────────────────────────────────────────

def _auth_token() -> str:
    resp = client.post("/auth/register", json={
        "email": TEST_EMAIL, "password": TEST_PASSWORD, "display_name": "ST",
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["token"]


def test_stream_endpoint_unauth_401():
    resp = client.post("/practice/explain/stream", json={"text": "hi."})
    assert resp.status_code == 401


def test_stream_endpoint_empty_text_400():
    token = _auth_token()
    resp = client.post("/practice/explain/stream", json={"text": "   "},
                       headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400


def test_stream_endpoint_flows_ndjson():
    token = _auth_token()
    chunks = ['{"field":"meaning","value":"简单"}\n',
              '{"field":"grammar","value":"OK"}\n']

    with patch("app.services.explain_service.get_client",
               return_value=_mock_stream_client(chunks)):
        with client.stream("POST", "/practice/explain/stream",
                           json={"text": "Simple sentence."},
                           headers={"Authorization": f"Bearer {token}"}) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("application/x-ndjson")
            lines = [ln for ln in resp.iter_lines() if ln.strip()]
    objs = [json.loads(ln) for ln in lines]
    fields = [o.get("field") for o in objs if "field" in o]
    assert fields == ["meaning", "grammar"]
    assert any(o.get("_done") for o in objs)


# ── frontend wiring ────────────────────────────────────────

PRACTICE_HTML = Path("static/practice.html")


def test_frontend_calls_stream_endpoint_for_sentence():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    assert "/practice/explain/stream" in src


def test_frontend_has_streaming_parser():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    # 读 body reader + 按行切
    assert "getReader" in src or "body.getReader" in src
    # 按行拆分
    assert "split(" in src
    # 命中任一字段事件处理
    assert '"field"' in src or "'field'" in src or "obj.field" in src
