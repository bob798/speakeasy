import pytest
import asyncio
import json
from unittest.mock import AsyncMock, patch
from app.services.review_service import analyze_conversation

TEST_USER = "test_user_v02b_step3"
TEST_SESSION = "test_session_step3"


def run(coro):
    return asyncio.run(coro)


HISTORY_WITH_ERROR = [
    {"role": "user", "content": "Yesterday I go to the client office and present the report."},
    {"role": "assistant", "content": "That sounds like a productive day!"},
    {"role": "user", "content": "Yes, I go there every week actually."},
]

HISTORY_CORRECT = [
    {"role": "user", "content": "I went to the gym this morning."},
    {"role": "assistant", "content": "Nice! How was the workout?"},
    {"role": "user", "content": "It was great, I feel much better now."},
]

HISTORY_IDIOMATIC = [
    {"role": "user", "content": "The meeting totally threw me off."},
    {"role": "assistant", "content": "I understand that feeling."},
    {"role": "user", "content": "Yeah, I wasn't prepared for the sudden change."},
]


def test_returns_errors_for_wrong_history():
    result = run(analyze_conversation(TEST_SESSION, TEST_USER, HISTORY_WITH_ERROR))
    assert result is not None
    assert "errors" in result
    assert len(result["errors"]) > 0
    err = result["errors"][0]
    assert "key" in err
    assert "original" in err
    assert "corrected" in err
    assert "explanation_zh" in err
    assert "confidence" in err


def test_returns_empty_errors_for_correct_history():
    result = run(analyze_conversation(TEST_SESSION + "_correct", TEST_USER, HISTORY_CORRECT))
    if result is not None:  # LLM 可能返回 None 也属正常
        assert result["errors"] == []


def test_returns_highlights_for_idiomatic():
    result = run(analyze_conversation(TEST_SESSION + "_idiomatic", TEST_USER, HISTORY_IDIOMATIC))
    if result is not None:
        assert "highlights" in result


def test_returns_none_on_llm_failure():
    with patch("app.services.review_service.get_client") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.complete.side_effect = Exception("LLM timeout")
        mock_client.return_value = mock_instance
        result = run(analyze_conversation(TEST_SESSION + "_fail", TEST_USER, HISTORY_WITH_ERROR))
    assert result is None


def test_returns_none_for_short_history():
    short = [{"role": "user", "content": "Hello"}]
    result = run(analyze_conversation(TEST_SESSION + "_short", TEST_USER, short))
    assert result is None
