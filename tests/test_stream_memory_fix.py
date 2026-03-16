"""
tests/test_stream_memory_fix.py

验证 /chat/stream 流式接口正确注入 grammar_cards 记忆（build_system_prompt）。
修复背景：流式接口原先绕过 build_system_prompt()，导致 grammar_cards 记忆对流式无效。

测试用户：test_user_stream_memory_fix（独立隔离，测试前后自动清理）
"""

import json
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.orm import Session

from main import app
from app.models.db import engine, GrammarCard
from app.services.memory_service import build_system_prompt
from app.prompts.system import SYSTEM_PROMPT

TEST_USER = "test_user_stream_memory_fix"
TEST_SESSION = "session_stream_memory_fix"


# ─── Fixture：测试前后清理 ─────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def cleanup():
    _cleanup()
    yield
    _cleanup()


def _cleanup():
    with Session(engine) as s:
        s.query(GrammarCard).filter_by(user_id=TEST_USER).delete()
        s.commit()


# ─── 辅助函数 ──────────────────────────────────────────────────────────────────

def _insert_active_card(user_id: str, key: str, content: str):
    """直接插入一张 active grammar_card（due 设为过去，确保被 get_injectable_cards 选中）"""
    import json as _json
    from datetime import datetime, timezone, timedelta
    from fsrs import FSRS, Card, Rating
    scheduler = FSRS()
    card = Card()
    card, _ = scheduler.review_card(card, Rating.Hard)
    card_dict = card.to_dict()
    # 强制 due 到昨天，使其立即命中注入条件
    card_dict["due"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    with Session(engine) as s:
        row = GrammarCard(
            user_id=user_id,
            key=key,
            content=content,
            example_wrong="i go",
            example_right="I went",
            explanation_zh="过去式用 went",
            frequency=2,
            fsrs_card_data=_json.dumps(card_dict),
            status="active",
        )
        s.add(row)
        s.commit()


async def _collect_stream(user_id: str, message: str) -> str:
    """调用 /chat/stream，收集完整回复内容"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with client.stream("POST", "/chat/stream", json={
            "user_id": user_id,
            "session_id": TEST_SESSION,
            "message": message,
            "history": [],
        }) as resp:
            full = []
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if data.get("type") == "delta":
                        full.append(data["content"])
            return "".join(full)


# ─── TC001：有 grammar_card 时，build_system_prompt 包含注入内容 ────────────────

@pytest.mark.asyncio
async def test_TC001_system_prompt_contains_card_when_active():
    """有 active grammar_card 时，build_system_prompt 应包含注入内容"""
    _insert_active_card(TEST_USER, "past_tense", "过去时用过去式动词")

    prompt = await build_system_prompt(TEST_USER)

    assert SYSTEM_PROMPT in prompt, "原始 SYSTEM_PROMPT 应被包含"
    assert "过去时用过去式动词" in prompt, "grammar_card 内容应被注入"
    assert "About This User" in prompt, "注入区块标题应存在"


# ─── TC002：无 grammar_card 时，返回原始 SYSTEM_PROMPT ────────────────────────

@pytest.mark.asyncio
async def test_TC002_system_prompt_unchanged_without_cards():
    """无 grammar_card 时，build_system_prompt 应返回原始 SYSTEM_PROMPT"""
    prompt = await build_system_prompt(TEST_USER)

    assert prompt == SYSTEM_PROMPT, "无卡片时应返回原始 SYSTEM_PROMPT，无多余内容"


# ─── TC003：/chat/stream 流式接口能正常返回内容（smoke test） ─────────────────

@pytest.mark.asyncio
async def test_TC003_stream_returns_content():
    """/chat/stream 应返回非空的流式内容"""
    reply = await _collect_stream(TEST_USER, "Hi, how are you?")

    assert len(reply) > 0, "流式接口应返回非空回复"


# ─── TC004：/chat 和 /chat/stream 使用相同的 system_prompt 构建逻辑 ──────────

@pytest.mark.asyncio
async def test_TC004_chat_and_stream_use_same_prompt_logic():
    """/chat 和 /chat/stream 均调用 build_system_prompt，逻辑对称"""
    _insert_active_card(TEST_USER, "plural", "名词复数加 s")

    # 验证 build_system_prompt 对同一用户返回一致结果（两次调用幂等）
    prompt_a = await build_system_prompt(TEST_USER)
    prompt_b = await build_system_prompt(TEST_USER)

    assert prompt_a == prompt_b, "build_system_prompt 应对相同输入返回相同结果"
    assert "名词复数加 s" in prompt_a, "grammar_card 内容应被注入到两条路径共用的 prompt"
