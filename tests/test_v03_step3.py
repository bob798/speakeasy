"""
V0.3 Step 3 — user_facts 表 + 自动提取
user_id: test_user_v03_s3

Note: 测试直接调用 extract_and_save_facts()，绕开 create_task 异步问题。
"""
import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, Base, UserFact
from app.services.facts_service import (
    extract_and_save_facts,
    get_recent_facts,
    delete_fact,
)

TEST_USER = "test_user_v03_s3"
TEST_SESSION = "test_session_v03_s3"
TEST_SESSION_2 = "test_session_v03_s3b"

SAMPLE_HISTORY = [
    {"role": "user", "content": "I had a tough presentation review with my boss last week."},
    {"role": "assistant", "content": "Oh no, that sounds stressful! What happened?"},
    {"role": "user", "content": "She said my slides were not clear. I'm preparing for an English interview next month."},
    {"role": "assistant", "content": "I see — practicing is key. What company is the interview for?"},
]

MOCK_FACTS_RESPONSE = '["User had a tough presentation review with their boss.", "User is preparing for an English interview next month."]'


@pytest.fixture(autouse=True)
def cleanup():
    Base.metadata.create_all(engine)
    yield
    with OrmSession(engine) as s:
        s.query(UserFact).filter_by(user_id=TEST_USER).delete()
        s.commit()


# ── extract_and_save_facts ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_extract_saves_facts():
    mock_client = AsyncMock()
    mock_client.complete = AsyncMock(return_value=MOCK_FACTS_RESPONSE)

    with patch("app.services.facts_service.get_client", return_value=mock_client):
        await extract_and_save_facts(TEST_USER, TEST_SESSION, SAMPLE_HISTORY)

    facts = get_recent_facts(TEST_USER)
    assert len(facts) == 2
    contents = [f.content for f in facts]
    assert any("presentation" in c for c in contents)
    assert any("interview" in c for c in contents)


@pytest.mark.asyncio
async def test_extract_stores_source_session_id():
    mock_client = AsyncMock()
    mock_client.complete = AsyncMock(return_value=MOCK_FACTS_RESPONSE)

    with patch("app.services.facts_service.get_client", return_value=mock_client):
        await extract_and_save_facts(TEST_USER, TEST_SESSION, SAMPLE_HISTORY)

    facts = get_recent_facts(TEST_USER)
    for f in facts:
        assert f.source_session_id == TEST_SESSION


@pytest.mark.asyncio
async def test_extract_idempotent_same_session():
    """同一 session_id 不重复提取"""
    mock_client = AsyncMock()
    mock_client.complete = AsyncMock(return_value=MOCK_FACTS_RESPONSE)

    with patch("app.services.facts_service.get_client", return_value=mock_client):
        await extract_and_save_facts(TEST_USER, TEST_SESSION, SAMPLE_HISTORY)
        await extract_and_save_facts(TEST_USER, TEST_SESSION, SAMPLE_HISTORY)

    facts = get_recent_facts(TEST_USER)
    assert len(facts) == 2  # only extracted once


@pytest.mark.asyncio
async def test_extract_different_sessions_both_saved():
    """不同 session_id 都应提取"""
    mock_client = AsyncMock()
    mock_client.complete = AsyncMock(return_value='["Fact A"]')

    with patch("app.services.facts_service.get_client", return_value=mock_client):
        await extract_and_save_facts(TEST_USER, TEST_SESSION, SAMPLE_HISTORY)
        await extract_and_save_facts(TEST_USER, TEST_SESSION_2, SAMPLE_HISTORY)

    facts = get_recent_facts(TEST_USER)
    sessions = {f.source_session_id for f in facts}
    assert TEST_SESSION in sessions
    assert TEST_SESSION_2 in sessions


@pytest.mark.asyncio
async def test_extract_skips_if_not_enough_messages():
    """少于 2 条用户消息时跳过"""
    mock_client = AsyncMock()
    mock_client.complete = AsyncMock(return_value=MOCK_FACTS_RESPONSE)

    short_history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi!"},
    ]

    with patch("app.services.facts_service.get_client", return_value=mock_client):
        await extract_and_save_facts(TEST_USER, TEST_SESSION, short_history)

    facts = get_recent_facts(TEST_USER)
    assert len(facts) == 0
    mock_client.complete.assert_not_called()


@pytest.mark.asyncio
async def test_extract_max_5_facts():
    """超过 5 条 facts 时截断到 5"""
    big_list = [f"Fact {i}" for i in range(8)]
    mock_client = AsyncMock()
    mock_client.complete = AsyncMock(return_value=str(big_list).replace("'", '"'))

    with patch("app.services.facts_service.get_client", return_value=mock_client):
        await extract_and_save_facts(TEST_USER, TEST_SESSION, SAMPLE_HISTORY)

    facts = get_recent_facts(TEST_USER)
    assert len(facts) <= 5


# ── get_recent_facts ────────────────────────────────────────────────────────

def test_get_recent_facts_empty():
    facts = get_recent_facts(TEST_USER)
    assert facts == []


def test_get_recent_facts_returns_in_desc_order():
    with OrmSession(engine) as s:
        s.add(UserFact(user_id=TEST_USER, content="Older fact", source_session_id="s1"))
        s.add(UserFact(user_id=TEST_USER, content="Newer fact", source_session_id="s2"))
        s.commit()

    facts = get_recent_facts(TEST_USER)
    assert len(facts) == 2
    assert facts[0].content == "Newer fact"


def test_get_recent_facts_limit():
    with OrmSession(engine) as s:
        for i in range(10):
            s.add(UserFact(user_id=TEST_USER, content=f"Fact {i}", source_session_id=f"s{i}"))
        s.commit()

    facts = get_recent_facts(TEST_USER, limit=3)
    assert len(facts) == 3


# ── delete_fact ─────────────────────────────────────────────────────────────

def test_delete_fact_success():
    with OrmSession(engine) as s:
        f = UserFact(user_id=TEST_USER, content="To delete", source_session_id="s1")
        s.add(f)
        s.commit()
        fact_id = f.id

    result = delete_fact(fact_id, TEST_USER)
    assert result is True

    facts = get_recent_facts(TEST_USER)
    assert len(facts) == 0


def test_delete_fact_wrong_user():
    with OrmSession(engine) as s:
        f = UserFact(user_id=TEST_USER, content="Protected", source_session_id="s1")
        s.add(f)
        s.commit()
        fact_id = f.id

    result = delete_fact(fact_id, "other_user")
    assert result is False

    facts = get_recent_facts(TEST_USER)
    assert len(facts) == 1


# ── API: GET /memory/facts ────────────────────────────────────────────────

def test_api_get_facts(client=None):
    from fastapi.testclient import TestClient
    from main import app
    c = TestClient(app)

    with OrmSession(engine) as s:
        s.add(UserFact(user_id=TEST_USER, content="Test fact 1", source_session_id="s1"))
        s.add(UserFact(user_id=TEST_USER, content="Test fact 2", source_session_id="s2"))
        s.commit()

    r = c.get(f"/memory/facts?user_id={TEST_USER}")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert len(data["facts"]) == 2
    contents = [f["content"] for f in data["facts"]]
    assert "Test fact 1" in contents
    assert "Test fact 2" in contents


def test_api_delete_fact():
    from fastapi.testclient import TestClient
    from main import app
    c = TestClient(app)

    with OrmSession(engine) as s:
        f = UserFact(user_id=TEST_USER, content="Will be deleted", source_session_id="s1")
        s.add(f)
        s.commit()
        fact_id = f.id

    r = c.delete(f"/memory/facts/{fact_id}?user_id={TEST_USER}")
    assert r.status_code == 200
    assert r.json()["deleted"] is True

    facts = get_recent_facts(TEST_USER)
    assert len(facts) == 0


def test_api_delete_fact_not_found():
    from fastapi.testclient import TestClient
    from main import app
    c = TestClient(app)
    r = c.delete(f"/memory/facts/99999?user_id={TEST_USER}")
    assert r.status_code == 404


print("✅ Step 3 完成")
