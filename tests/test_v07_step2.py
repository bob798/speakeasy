"""
V0.7 Step 2 — ask_service 通用追问服务
user_id: test_user_v07_step2
"""
import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, Base, AskThread, AskMessage
from app.services.ask_service import (
    AskError,
    create_thread,
    append_message,
    list_threads,
    get_thread,
    delete_thread,
)
from app.prompts.ask import build_system_prompt, SCOPE_PROMPTS

TEST_USER = "test_user_v07_step2"
OTHER_USER = "test_user_v07_step2_other"


@pytest.fixture(autouse=True)
def cleanup():
    Base.metadata.create_all(engine)
    with OrmSession(engine) as s:
        tids = [
            t.id for t in s.query(AskThread).filter(
                AskThread.user_id.in_([TEST_USER, OTHER_USER])
            ).all()
        ]
        if tids:
            s.query(AskMessage).filter(AskMessage.thread_id.in_(tids)).delete(synchronize_session=False)
            s.query(AskThread).filter(AskThread.user_id.in_([TEST_USER, OTHER_USER])).delete(synchronize_session=False)
            s.commit()
    yield
    with OrmSession(engine) as s:
        tids = [
            t.id for t in s.query(AskThread).filter(
                AskThread.user_id.in_([TEST_USER, OTHER_USER])
            ).all()
        ]
        if tids:
            s.query(AskMessage).filter(AskMessage.thread_id.in_(tids)).delete(synchronize_session=False)
            s.query(AskThread).filter(AskThread.user_id.in_([TEST_USER, OTHER_USER])).delete(synchronize_session=False)
            s.commit()


def _patch_client(answers):
    """patch get_client with pre-canned answers in order."""
    it = iter(answers)
    mock_client = AsyncMock()
    mock_client.complete = AsyncMock(side_effect=lambda *a, **kw: next(it))
    return patch("app.services.ask_service.get_client", return_value=mock_client), mock_client


# ── Prompt builders ─────────────────────────────────────────

def test_build_system_prompt_practice_explain_has_level_and_text():
    s = build_system_prompt("practice_explain", {
        "kind": "word", "text": "remain", "context": "We remain friends.",
        "cefr_level": "B1", "explanation": {"definitions": ["保持"]},
    })
    assert "B1" in s
    assert "remain" in s
    assert "保持" in s


def test_build_system_prompt_unknown_scope_raises():
    with pytest.raises(ValueError, match="未支持|未注册"):
        build_system_prompt("nonexistent_scope", {})


def test_translate_scope_registered():
    assert "translate" in SCOPE_PROMPTS
    s = build_system_prompt("translate", {
        "source_text": "我做过推荐系统",
        "translated_text": "I worked on recommendation systems",
        "direction": "zh2en",
    })
    assert "推荐系统" in s
    assert "I worked on recommendation systems" in s


# ── create_thread ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_thread_persists_and_returns_answer():
    p, _ = _patch_client(["Because 'remain' keeps a state."])
    with p:
        out = await create_thread(
            user_id=TEST_USER,
            scope="practice_explain",
            ref_type="explanation",
            ref_id="hash_abc",
            context_payload={"kind": "word", "text": "remain", "cefr_level": "B1"},
            first_question="Why is 'remain' present tense here?",
        )
    assert out["thread_id"] > 0
    assert len(out["messages"]) == 2
    assert out["messages"][0]["role"] == "user"
    assert out["messages"][1]["role"] == "assistant"
    assert "remain" in out["messages"][1]["content"].lower()

    # 入库
    with OrmSession(engine) as s:
        t = s.query(AskThread).filter_by(id=out["thread_id"]).first()
        assert t is not None
        assert t.user_id == TEST_USER
        assert t.scope == "practice_explain"
        assert t.ref_id == "hash_abc"
        assert "remain" in t.title.lower() or "why" in t.title.lower()
        msgs = s.query(AskMessage).filter_by(thread_id=t.id).order_by(AskMessage.id).all()
        assert [m.role for m in msgs] == ["user", "assistant"]


@pytest.mark.asyncio
async def test_create_thread_empty_question_raises():
    with pytest.raises(AskError, match="问题不能为空"):
        await create_thread(
            user_id=TEST_USER, scope="practice_explain",
            ref_type="explanation", ref_id="x",
            context_payload={}, first_question="   ",
        )


@pytest.mark.asyncio
async def test_create_thread_rejects_unknown_scope():
    with pytest.raises(AskError, match="未支持|未注册"):
        await create_thread(
            user_id=TEST_USER, scope="nope",
            ref_type="explanation", ref_id="x",
            context_payload={}, first_question="q?",
        )


# ── append_message ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_append_message_uses_history():
    p, mock_client = _patch_client([
        "Answer 1 about remain.",
        "Answer 2 building on previous.",
    ])
    with p:
        out1 = await create_thread(
            user_id=TEST_USER, scope="practice_explain",
            ref_type="explanation", ref_id="h1",
            context_payload={"kind": "word", "text": "remain"},
            first_question="Q1?",
        )
        out2 = await append_message(
            user_id=TEST_USER,
            thread_id=out1["thread_id"],
            question="Q2?",
        )
    assert out2["answer"] == "Answer 2 building on previous."

    # 验证第二次 LLM 调用带上了历史
    second_call = mock_client.complete.call_args_list[1]
    msgs = second_call[0][0]
    roles = [m["role"] for m in msgs]
    assert roles[0] == "system"
    # 第二次调用应包含：system + 首轮 Q + 首轮 A + 新 Q
    assert "user" in roles and "assistant" in roles
    assert any(m["content"] == "Q1?" for m in msgs)
    assert any(m["content"] == "Answer 1 about remain." for m in msgs)
    assert msgs[-1]["content"] == "Q2?"


@pytest.mark.asyncio
async def test_append_message_rejects_other_user():
    p, _ = _patch_client(["A1"])
    with p:
        out = await create_thread(
            user_id=TEST_USER, scope="practice_explain",
            ref_type="explanation", ref_id="hh",
            context_payload={}, first_question="Q?",
        )
    with pytest.raises(AskError, match="无权"):
        await append_message(user_id=OTHER_USER, thread_id=out["thread_id"], question="steal?")


@pytest.mark.asyncio
async def test_append_message_rejects_deleted_thread():
    p, _ = _patch_client(["A1"])
    with p:
        out = await create_thread(
            user_id=TEST_USER, scope="practice_explain",
            ref_type="explanation", ref_id="hh",
            context_payload={}, first_question="Q?",
        )
    delete_thread(user_id=TEST_USER, thread_id=out["thread_id"])
    with pytest.raises(AskError, match="不存在|已删除"):
        await append_message(user_id=TEST_USER, thread_id=out["thread_id"], question="Q2?")


# ── list / get / delete ────────────────────────────────────

@pytest.mark.asyncio
async def test_list_threads_filter_by_ref():
    p, _ = _patch_client(["A1", "A2", "A3"])
    with p:
        await create_thread(user_id=TEST_USER, scope="practice_explain",
                            ref_type="explanation", ref_id="R1",
                            context_payload={}, first_question="q1")
        await create_thread(user_id=TEST_USER, scope="practice_explain",
                            ref_type="explanation", ref_id="R2",
                            context_payload={}, first_question="q2")
        await create_thread(user_id=TEST_USER, scope="translate",
                            ref_type="vocabulary", ref_id="V1",
                            context_payload={"source_text": "x", "translated_text": "y"},
                            first_question="q3")

    all_t = list_threads(user_id=TEST_USER)
    assert len(all_t) == 3

    only_explain = list_threads(user_id=TEST_USER, scope="practice_explain")
    assert len(only_explain) == 2

    only_r1 = list_threads(user_id=TEST_USER, scope="practice_explain", ref_id="R1")
    assert len(only_r1) == 1
    assert only_r1[0]["ref_id"] == "R1"


@pytest.mark.asyncio
async def test_get_thread_returns_messages():
    p, _ = _patch_client(["first answer"])
    with p:
        out = await create_thread(
            user_id=TEST_USER, scope="practice_explain",
            ref_type="explanation", ref_id="hx",
            context_payload={}, first_question="hi?",
        )
    t = get_thread(user_id=TEST_USER, thread_id=out["thread_id"])
    assert t is not None
    assert len(t["messages"]) == 2
    assert t["messages"][0]["content"] == "hi?"
    assert t["messages"][1]["content"] == "first answer"


@pytest.mark.asyncio
async def test_get_thread_other_user_returns_none():
    p, _ = _patch_client(["a"])
    with p:
        out = await create_thread(
            user_id=TEST_USER, scope="practice_explain",
            ref_type="explanation", ref_id="hx",
            context_payload={}, first_question="hi?",
        )
    assert get_thread(user_id=OTHER_USER, thread_id=out["thread_id"]) is None


@pytest.mark.asyncio
async def test_delete_thread_hides_from_list():
    p, _ = _patch_client(["a"])
    with p:
        out = await create_thread(
            user_id=TEST_USER, scope="practice_explain",
            ref_type="explanation", ref_id="hx",
            context_payload={}, first_question="hi?",
        )
    assert delete_thread(user_id=TEST_USER, thread_id=out["thread_id"]) is True
    assert list_threads(user_id=TEST_USER) == []
    assert get_thread(user_id=TEST_USER, thread_id=out["thread_id"]) is None
