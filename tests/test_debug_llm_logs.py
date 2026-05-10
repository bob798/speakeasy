"""
test_debug_llm_logs.py — API 级测试 GET /debug/llm-logs 和 GET /debug/llm-logs/{id}

覆盖：
  - GET /debug/llm-logs 返回 200 和 {logs, count} 结构
  - GET /debug/llm-logs 无记录时 logs=[] count=0
  - GET /debug/llm-logs 返回已写入的日志行（场景、provider、model）
  - GET /debug/llm-logs ?scene= 过滤只返回对应 scene 的日志
  - GET /debug/llm-logs ?model= 过滤只返回对应 model 的日志
  - GET /debug/llm-logs ?limit= 限制返回条数
  - GET /debug/llm-logs 默认按 created_at 降序（最新在前）
  - GET /debug/llm-logs input_preview 截断到 200 字符以内
  - GET /debug/llm-logs output_preview 截断到 200 字符以内
  - GET /debug/llm-logs/{id} 返回单条完整日志
  - GET /debug/llm-logs/{id} 不存在时返回 404
  - GET /debug/llm-logs/{id} 完整 input_messages 为列表（非截断）
  - GET /debug/llm-logs/{id} 完整 output_text（非截断）
"""

import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from main import app
from app.models.db import engine, Base, LlmCallLog, User

client = TestClient(app)

SCENE_PREFIX = "test_api_llm_"
TEST_EMAIL = "debug_llm_test@example.com"
TEST_PASSWORD = "testpass123"

_token_cache = None


def _auth_token() -> str:
    global _token_cache
    if _token_cache:
        return _token_cache
    resp = client.post("/auth/register", json={
        "email": TEST_EMAIL, "password": TEST_PASSWORD, "display_name": "DT",
    })
    if resp.status_code == 409:
        resp = client.post("/auth/login", json={
            "email": TEST_EMAIL, "password": TEST_PASSWORD,
        })
    assert resp.status_code in (200, 201), resp.text
    _token_cache = resp.json()["token"]
    return _token_cache


def _headers():
    return {"Authorization": f"Bearer {_auth_token()}"}


@pytest.fixture(autouse=True)
def cleanup():
    Base.metadata.create_all(engine)
    _wipe()
    yield
    _wipe()


def _wipe():
    with OrmSession(engine) as s:
        s.query(LlmCallLog).filter(LlmCallLog.scene.like(f"{SCENE_PREFIX}%")).delete(
            synchronize_session=False
        )
        s.commit()


def _insert_log(
    scene: str = "test_api_llm_chat",
    provider: str = "deepseek",
    model: str = "deepseek-chat",
    input_messages: list = None,
    output_text: str = "reply",
    stream: bool = False,
    ttft_ms: int = None,
    total_ms: int = None,
    status: str = "ok",
    error_message: str = None,
) -> int:
    if input_messages is None:
        input_messages = [{"role": "user", "content": "Hello"}]
    with OrmSession(engine) as s:
        row = LlmCallLog(
            scene=scene,
            provider=provider,
            model=model,
            input_messages=json.dumps(input_messages, ensure_ascii=False),
            output_text=output_text,
            stream=stream,
            ttft_ms=ttft_ms,
            total_ms=total_ms,
            status=status,
            error_message=error_message,
        )
        s.add(row)
        s.commit()
        return row.id


# ── GET /debug/llm-logs ───────────────────────────────────────

def test_list_llm_logs_returns_200_with_correct_shape():
    resp = client.get("/debug/llm-logs", headers=_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert "logs" in data
    assert "count" in data


def test_list_llm_logs_empty_when_no_records_for_scene():
    # Filter by our test scene prefix so pre-existing logs don't interfere
    resp = client.get("/debug/llm-logs", headers=_headers(), params={"scene": "test_api_llm_notexist"})
    data = resp.json()
    assert data["logs"] == []
    assert data["count"] == 0


def test_list_llm_logs_returns_inserted_row():
    _insert_log(scene="test_api_llm_chat", provider="volcengine", model="deepseek-v3")
    resp = client.get("/debug/llm-logs", headers=_headers(), params={"scene": "test_api_llm_chat"})
    data = resp.json()
    assert data["count"] == 1
    row = data["logs"][0]
    assert row["scene"] == "test_api_llm_chat"
    assert row["provider"] == "volcengine"
    assert row["model"] == "deepseek-v3"
    assert row["status"] == "ok"


def test_list_llm_logs_each_row_has_required_fields():
    _insert_log()
    resp = client.get("/debug/llm-logs", headers=_headers())
    row = resp.json()["logs"][0]
    required = {"id", "scene", "provider", "model", "stream", "ttft_ms",
                "total_ms", "input_tokens", "output_tokens", "status",
                "error_message", "input_preview", "output_preview", "created_at"}
    assert required.issubset(set(row.keys()))


def test_list_llm_logs_filter_by_scene():
    _insert_log(scene="test_api_llm_explain")
    _insert_log(scene="test_api_llm_chat")
    resp = client.get("/debug/llm-logs", headers=_headers(), params={"scene": "test_api_llm_explain"})
    data = resp.json()
    assert data["count"] == 1
    assert data["logs"][0]["scene"] == "test_api_llm_explain"


def test_list_llm_logs_filter_by_model():
    _insert_log(scene="test_api_llm_chat", model="model-a")
    _insert_log(scene="test_api_llm_explain", model="model-b")
    resp = client.get("/debug/llm-logs", headers=_headers(), params={"model": "model-a"})
    data = resp.json()
    assert data["count"] == 1
    assert data["logs"][0]["model"] == "model-a"


def test_list_llm_logs_limit_restricts_returned_rows():
    for i in range(5):
        _insert_log(scene=f"test_api_llm_multi", output_text=f"reply {i}")
    resp = client.get("/debug/llm-logs", headers=_headers(), params={"limit": 3})
    data = resp.json()
    assert len(data["logs"]) == 3
    assert data["count"] == 3


def test_list_llm_logs_ordered_newest_first():
    id1 = _insert_log(scene="test_api_llm_order", output_text="first")
    id2 = _insert_log(scene="test_api_llm_order", output_text="second")
    resp = client.get("/debug/llm-logs", headers=_headers(), params={"scene": "test_api_llm_order"})
    ids = [r["id"] for r in resp.json()["logs"]]
    # newest (id2) should appear before oldest (id1)
    assert ids.index(id2) < ids.index(id1)


def test_list_llm_logs_input_preview_truncated_to_200_chars():
    long_content = "A" * 500
    _insert_log(
        scene="test_api_llm_preview",
        input_messages=[{"role": "user", "content": long_content}],
    )
    resp = client.get("/debug/llm-logs", headers=_headers(), params={"scene": "test_api_llm_preview"})
    preview = resp.json()["logs"][0]["input_preview"]
    assert len(preview) <= 200


def test_list_llm_logs_output_preview_truncated_to_200_chars():
    long_output = "B" * 500
    _insert_log(scene="test_api_llm_preview2", output_text=long_output)
    resp = client.get("/debug/llm-logs", headers=_headers(), params={"scene": "test_api_llm_preview2"})
    preview = resp.json()["logs"][0]["output_preview"]
    assert len(preview) <= 200


def test_list_llm_logs_stream_flag_preserved():
    _insert_log(scene="test_api_llm_stream", stream=True, ttft_ms=80, total_ms=600)
    resp = client.get("/debug/llm-logs", headers=_headers(), params={"scene": "test_api_llm_stream"})
    row = resp.json()["logs"][0]
    assert row["stream"] is True
    assert row["ttft_ms"] == 80
    assert row["total_ms"] == 600


# ── GET /debug/llm-logs/{id} ──────────────────────────────────

def test_get_llm_log_by_id_returns_200():
    log_id = _insert_log(scene="test_api_llm_single")
    resp = client.get(f"/debug/llm-logs/{log_id}", headers=_headers())
    assert resp.status_code == 200


def test_get_llm_log_by_id_returns_full_input_messages_as_list():
    messages = [
        {"role": "system", "content": "You are Alex"},
        {"role": "user", "content": "Hello"},
    ]
    log_id = _insert_log(scene="test_api_llm_full", input_messages=messages)
    resp = client.get(f"/debug/llm-logs/{log_id}", headers=_headers())
    data = resp.json()
    assert isinstance(data["input_messages"], list)
    assert len(data["input_messages"]) == 2
    assert data["input_messages"][0]["role"] == "system"
    assert data["input_messages"][1]["content"] == "Hello"


def test_get_llm_log_by_id_returns_full_output_text_untruncated():
    long_output = "C" * 1000
    log_id = _insert_log(scene="test_api_llm_full2", output_text=long_output)
    resp = client.get(f"/debug/llm-logs/{log_id}", headers=_headers())
    assert resp.json()["output_text"] == long_output


def test_get_llm_log_by_id_nonexistent_returns_404():
    resp = client.get("/debug/llm-logs/99999999", headers=_headers())
    assert resp.status_code == 404


def test_get_llm_log_by_id_has_all_fields():
    log_id = _insert_log(
        scene="test_api_llm_allfields",
        provider="anthropic",
        model="claude-haiku",
        stream=True,
        ttft_ms=150,
        total_ms=900,
        status="error",
        error_message="timeout",
    )
    resp = client.get(f"/debug/llm-logs/{log_id}", headers=_headers())
    data = resp.json()
    assert data["provider"] == "anthropic"
    assert data["model"] == "claude-haiku"
    assert data["stream"] is True
    assert data["ttft_ms"] == 150
    assert data["total_ms"] == 900
    assert data["status"] == "error"
    assert data["error_message"] == "timeout"
    assert data["created_at"] is not None
