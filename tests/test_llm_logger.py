"""
test_llm_logger.py — 单元测试 app/services/llm_logger.py

覆盖：
  - log_llm_call 正常写入一条记录到 llm_call_logs 表
  - log_llm_call 写入 optional 字段 (ttft_ms, total_ms, tokens, error_message)
  - log_llm_call 在 DB 异常时静默降级（不抛出）
  - log_llm_call 将 input_messages 序列化为 JSON 字符串
  - StreamLogger.on_chunk 收集文本块
  - StreamLogger.on_first_token 只在首次调用时记录 ttft_ms
  - StreamLogger.finish 写入 stream=True 的日志并汇总所有 chunks
  - StreamLogger.finish 在 status=error 时写入 error_message
  - StreamLogger.finish 当无 chunk 被收集时 output_text 为空字符串
"""

import json
import time
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, Base, LlmCallLog
from app.services.llm_logger import log_llm_call, StreamLogger

TEST_USER = "test_user_llm_logger"

MESSAGES = [{"role": "user", "content": "Hello"}]


@pytest.fixture(autouse=True)
def cleanup():
    Base.metadata.create_all(engine)
    with OrmSession(engine) as s:
        s.query(LlmCallLog).filter(LlmCallLog.scene.like("test_%")).delete(synchronize_session=False)
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(LlmCallLog).filter(LlmCallLog.scene.like("test_%")).delete(synchronize_session=False)
        s.commit()


def _fetch_logs(scene: str) -> list:
    with OrmSession(engine) as s:
        return s.query(LlmCallLog).filter_by(scene=scene).all()


# ── log_llm_call ─────────────────────────────────────────────

def test_log_llm_call_writes_one_row():
    log_llm_call(
        scene="test_basic",
        provider="deepseek",
        model="deepseek-chat",
        input_messages=MESSAGES,
        output_text="Hi there",
    )
    rows = _fetch_logs("test_basic")
    assert len(rows) == 1


def test_log_llm_call_persists_required_fields():
    log_llm_call(
        scene="test_fields",
        provider="volcengine",
        model="deepseek-v3",
        input_messages=MESSAGES,
        output_text="response text",
    )
    rows = _fetch_logs("test_fields")
    r = rows[0]
    assert r.provider == "volcengine"
    assert r.model == "deepseek-v3"
    assert r.output_text == "response text"
    assert r.status == "ok"
    assert r.stream is False


def test_log_llm_call_serializes_input_messages_as_json():
    messages = [{"role": "system", "content": "You are a tutor"}, {"role": "user", "content": "Hello"}]
    log_llm_call(
        scene="test_json",
        provider="anthropic",
        model="claude-haiku",
        input_messages=messages,
        output_text="",
    )
    rows = _fetch_logs("test_json")
    stored = json.loads(rows[0].input_messages)
    assert stored == messages


def test_log_llm_call_writes_optional_timing_and_token_fields():
    log_llm_call(
        scene="test_optional",
        provider="deepseek",
        model="deepseek-chat",
        input_messages=MESSAGES,
        output_text="ok",
        stream=True,
        ttft_ms=120,
        total_ms=800,
        input_tokens=50,
        output_tokens=30,
    )
    rows = _fetch_logs("test_optional")
    r = rows[0]
    assert r.stream is True
    assert r.ttft_ms == 120
    assert r.total_ms == 800
    assert r.input_tokens == 50
    assert r.output_tokens == 30


def test_log_llm_call_writes_error_status_and_message():
    log_llm_call(
        scene="test_error",
        provider="deepseek",
        model="deepseek-chat",
        input_messages=MESSAGES,
        output_text="",
        status="error",
        error_message="Connection timeout",
    )
    rows = _fetch_logs("test_error")
    r = rows[0]
    assert r.status == "error"
    assert r.error_message == "Connection timeout"


def test_log_llm_call_silently_swallows_db_exception():
    """DB 写入失败时函数不抛出异常（静默降级）"""
    with patch("app.services.llm_logger.OrmSession") as mock_session_cls:
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(side_effect=RuntimeError("DB is down"))
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_session_cls.return_value = mock_ctx
        # Should not raise
        log_llm_call(
            scene="test_silent",
            provider="deepseek",
            model="model",
            input_messages=MESSAGES,
            output_text="",
        )


def test_log_llm_call_multiple_calls_create_multiple_rows():
    for i in range(3):
        log_llm_call(
            scene="test_multi",
            provider="deepseek",
            model="deepseek-chat",
            input_messages=MESSAGES,
            output_text=f"reply {i}",
        )
    rows = _fetch_logs("test_multi")
    assert len(rows) == 3


# ── StreamLogger ─────────────────────────────────────────────

def test_stream_logger_on_chunk_accumulates_text():
    sl = StreamLogger("test_sl_chunks", "deepseek", "model", MESSAGES)
    sl.on_chunk("Hello")
    sl.on_chunk(", ")
    sl.on_chunk("world")
    assert "".join(sl._chunks) == "Hello, world"


def test_stream_logger_on_first_token_records_ttft_once():
    sl = StreamLogger("test_sl_ttft", "deepseek", "model", MESSAGES)
    sl.on_first_token()
    first_ttft = sl.ttft_ms
    assert first_ttft is not None
    assert first_ttft >= 0
    # Second call must not overwrite
    sl.on_first_token()
    assert sl.ttft_ms == first_ttft


def test_stream_logger_on_chunk_sets_ttft_on_first_chunk():
    sl = StreamLogger("test_sl_ttft2", "deepseek", "model", MESSAGES)
    assert sl.ttft_ms is None
    sl.on_chunk("first")
    assert sl.ttft_ms is not None


def test_stream_logger_finish_writes_stream_true_row():
    sl = StreamLogger("test_sl_finish", "deepseek", "deepseek-chat", MESSAGES)
    sl.on_chunk("part1")
    sl.on_chunk("part2")
    sl.finish()

    rows = _fetch_logs("test_sl_finish")
    assert len(rows) == 1
    r = rows[0]
    assert r.stream is True
    assert r.output_text == "part1part2"
    assert r.provider == "deepseek"
    assert r.model == "deepseek-chat"
    assert r.status == "ok"
    assert r.ttft_ms is not None
    assert r.total_ms is not None


def test_stream_logger_finish_with_error_status():
    sl = StreamLogger("test_sl_error", "anthropic", "claude", MESSAGES)
    sl.on_chunk("partial")
    sl.finish(status="error", error_message="Stream interrupted")

    rows = _fetch_logs("test_sl_error")
    assert len(rows) == 1
    r = rows[0]
    assert r.status == "error"
    assert r.error_message == "Stream interrupted"
    assert r.output_text == "partial"


def test_stream_logger_finish_with_no_chunks_gives_empty_output():
    sl = StreamLogger("test_sl_empty", "deepseek", "model", MESSAGES)
    sl.finish()

    rows = _fetch_logs("test_sl_empty")
    assert len(rows) == 1
    assert rows[0].output_text == ""


def test_stream_logger_total_ms_is_non_negative():
    sl = StreamLogger("test_sl_timing", "deepseek", "model", MESSAGES)
    sl.on_chunk("x")
    sl.finish()

    rows = _fetch_logs("test_sl_timing")
    assert rows[0].total_ms >= 0
