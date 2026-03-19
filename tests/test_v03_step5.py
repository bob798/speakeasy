"""
V0.3 Step 5 — 记忆管理页面后端 API 验证
user_id: test_user_v03_s5
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from main import app
from app.models.db import engine, Base, UserFact, GrammarCard, UserProfile

TEST_USER = "test_user_v03_s5"


@pytest.fixture(autouse=True)
def cleanup():
    Base.metadata.create_all(engine)
    yield
    with OrmSession(engine) as s:
        s.query(UserFact).filter_by(user_id=TEST_USER).delete()
        s.query(GrammarCard).filter_by(user_id=TEST_USER).delete()
        s.query(UserProfile).filter_by(user_id=TEST_USER).delete()
        s.commit()


@pytest.fixture
def client():
    return TestClient(app)


# ── /memory/cards GET ─────────────────────────────────────────────────────────

def test_get_cards_empty(client):
    r = client.get(f"/memory/cards?user_id={TEST_USER}")
    assert r.status_code == 200
    assert r.json()["cards"] == []


def test_get_cards_active_and_pending(client):
    with OrmSession(engine) as s:
        s.add(GrammarCard(user_id=TEST_USER, key="k1", content="c1", example_wrong="", example_right="",
                          explanation_zh="", frequency=2, fsrs_card_data="{}", status="active"))
        s.add(GrammarCard(user_id=TEST_USER, key="k2", content="c2", example_wrong="", example_right="",
                          explanation_zh="", frequency=1, fsrs_card_data="", status="pending"))
        s.add(GrammarCard(user_id=TEST_USER, key="k3", content="c3", example_wrong="", example_right="",
                          explanation_zh="", frequency=1, fsrs_card_data="", status="deleted"))
        s.commit()

    r = client.get(f"/memory/cards?user_id={TEST_USER}")
    assert r.status_code == 200
    cards = r.json()["cards"]
    # active + pending returned, deleted excluded
    assert len(cards) == 2
    statuses = {c["status"] for c in cards}
    assert "active" in statuses
    assert "pending" in statuses
    assert "deleted" not in statuses


def test_get_cards_filter_by_status(client):
    with OrmSession(engine) as s:
        s.add(GrammarCard(user_id=TEST_USER, key="k1", content="c1", example_wrong="", example_right="",
                          explanation_zh="", frequency=2, fsrs_card_data="{}", status="active"))
        s.add(GrammarCard(user_id=TEST_USER, key="k2", content="c2", example_wrong="", example_right="",
                          explanation_zh="", frequency=1, fsrs_card_data="", status="pending"))
        s.commit()

    r = client.get(f"/memory/cards?user_id={TEST_USER}&status=active")
    assert r.status_code == 200
    cards = r.json()["cards"]
    assert len(cards) == 1
    assert cards[0]["status"] == "active"


# ── /memory/cards/{id} DELETE ─────────────────────────────────────────────────

def test_delete_card_soft_deletes(client):
    with OrmSession(engine) as s:
        c = GrammarCard(user_id=TEST_USER, key="del_key", content="c1", example_wrong="", example_right="",
                        explanation_zh="", frequency=2, fsrs_card_data="{}", status="active")
        s.add(c)
        s.commit()
        card_id = c.id

    r = client.delete(f"/memory/cards/{card_id}?user_id={TEST_USER}")
    assert r.status_code == 200
    assert r.json()["deleted"] is True

    # Verify soft delete in DB
    with OrmSession(engine) as s:
        card = s.query(GrammarCard).filter_by(id=card_id).first()
        assert card.status == "deleted"


def test_delete_card_not_found(client):
    r = client.delete(f"/memory/cards/99999?user_id={TEST_USER}")
    assert r.status_code == 404


def test_delete_card_wrong_user(client):
    with OrmSession(engine) as s:
        c = GrammarCard(user_id=TEST_USER, key="protected", content="c1", example_wrong="", example_right="",
                        explanation_zh="", frequency=2, fsrs_card_data="{}", status="active")
        s.add(c)
        s.commit()
        card_id = c.id

    r = client.delete(f"/memory/cards/{card_id}?user_id=other_user")
    assert r.status_code == 404

    # Card still active
    with OrmSession(engine) as s:
        card = s.query(GrammarCard).filter_by(id=card_id).first()
        assert card.status == "active"


# ── /memory page route ────────────────────────────────────────────────────────

def test_memory_page_served(client):
    r = client.get("/memory")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")


def test_memory_page_has_tabs(client):
    r = client.get("/memory")
    assert "语言档案" in r.text
    assert "Alex 记得的事" in r.text
    assert "语法强化" in r.text


# ── index.html has memory link ────────────────────────────────────────────────

def test_index_has_memory_link(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "/memory" in r.text


print("✅ Step 5 完成")
