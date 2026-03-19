"""
V0.3 Step 1 — 数据层：user_profile 表 + Level 评估 API
user_id: test_user_v03_s1
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session as OrmSession

from main import app
from app.models.db import engine, Base, UserProfile, UserFact
from app.services.profile_service import assess_cefr, get_profile, upsert_profile

TEST_USER = "test_user_v03_s1"


@pytest.fixture(autouse=True)
def cleanup():
    # 确保表存在
    Base.metadata.create_all(engine)
    yield
    # 清理测试数据
    with OrmSession(engine) as s:
        s.query(UserProfile).filter_by(user_id=TEST_USER).delete()
        s.query(UserFact).filter_by(user_id=TEST_USER).delete()
        s.commit()


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=True)


# ── 表结构 ──────────────────────────────────────────────────────────────────

def test_user_profile_table_exists():
    inspector = sa_inspect(engine)
    tables = inspector.get_table_names()
    assert "user_profile" in tables, f"user_profile 表不存在，已有：{tables}"


def test_user_facts_table_exists():
    inspector = sa_inspect(engine)
    tables = inspector.get_table_names()
    assert "user_facts" in tables, f"user_facts 表不存在，已有：{tables}"


def test_user_profile_columns():
    inspector = sa_inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("user_profile")}
    required = {"user_id", "cefr_level", "profession", "industry",
                "topic_preferences", "learning_goal", "personality_note"}
    assert required <= cols, f"缺少字段：{required - cols}"


def test_user_facts_columns():
    inspector = sa_inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("user_facts")}
    required = {"id", "user_id", "content", "source_session_id", "created_at"}
    assert required <= cols, f"缺少字段：{required - cols}"


# ── assess_cefr ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("answers,expected", [
    (["cannot", "cannot", "cannot", "cannot", "cannot"], "A1"),   # 0
    (["can",    "cannot", "cannot", "cannot", "cannot"], "A1"),   # 2
    (["can",    "partially", "cannot", "cannot", "cannot"], "A2"),# 3
    (["can",    "can",    "cannot", "cannot", "cannot"], "A2"),   # 4
    (["can",    "can",    "partially", "cannot", "cannot"], "B1"),# 5
    (["can",    "can",    "can",    "cannot", "cannot"], "B1"),   # 6
    (["can",    "can",    "can",    "partially", "cannot"], "B2"),# 7
    (["can",    "can",    "can",    "can",    "cannot"], "B2"),   # 8
    (["can",    "can",    "can",    "can",    "partially"], "C1"),# 9
    (["can",    "can",    "can",    "can",    "can"],    "C1"),   # 10
])
def test_assess_cefr_scoring(answers, expected):
    assert assess_cefr(answers) == expected


# ── profile_service CRUD ────────────────────────────────────────────────────

def test_get_profile_returns_none_if_not_exist():
    result = get_profile(TEST_USER)
    assert result is None


def test_upsert_profile_creates_new():
    profile = upsert_profile(TEST_USER, {
        "cefr_level": "B1",
        "profession": "Product Manager",
    })
    assert profile.user_id == TEST_USER
    assert profile.cefr_level == "B1"
    assert profile.profession == "Product Manager"


def test_upsert_profile_updates_existing():
    upsert_profile(TEST_USER, {"cefr_level": "A2"})
    profile = upsert_profile(TEST_USER, {"cefr_level": "B1", "profession": "Engineer"})
    assert profile.cefr_level == "B1"
    assert profile.profession == "Engineer"


def test_upsert_profile_partial_update():
    upsert_profile(TEST_USER, {"cefr_level": "B1", "profession": "PM"})
    upsert_profile(TEST_USER, {"learning_goal": "workplace English"})
    profile = get_profile(TEST_USER)
    # Both fields preserved
    assert profile.cefr_level == "B1"
    assert profile.profession == "PM"
    assert profile.learning_goal == "workplace English"


# ── API: POST /assessment/self ───────────────────────────────────────────────

def test_api_assessment_self_b1(client):
    r = client.post("/assessment/self", json={
        "user_id": TEST_USER,
        "answers": ["can", "can", "can", "cannot", "cannot"],  # score=6 → B1
    })
    assert r.status_code == 200
    data = r.json()
    assert data["cefr_level"] == "B1"
    assert data["user_id"] == TEST_USER

    # Profile saved in DB
    profile = get_profile(TEST_USER)
    assert profile is not None
    assert profile.cefr_level == "B1"


def test_api_assessment_self_a1(client):
    r = client.post("/assessment/self", json={
        "user_id": TEST_USER,
        "answers": ["cannot", "cannot", "cannot", "cannot", "cannot"],  # 0 → A1
    })
    assert r.status_code == 200
    assert r.json()["cefr_level"] == "A1"


def test_api_assessment_self_wrong_count(client):
    r = client.post("/assessment/self", json={
        "user_id": TEST_USER,
        "answers": ["can", "cannot"],
    })
    assert r.status_code == 400


def test_api_assessment_self_invalid_value(client):
    r = client.post("/assessment/self", json={
        "user_id": TEST_USER,
        "answers": ["can", "can", "can", "can", "maybe"],
    })
    assert r.status_code == 400


# ── API: GET /memory/profile ─────────────────────────────────────────────────

def test_api_get_profile_empty(client):
    r = client.get(f"/memory/profile?user_id={TEST_USER}")
    assert r.status_code == 200
    data = r.json()
    assert data["user_id"] == TEST_USER
    assert data["cefr_level"] is None


def test_api_get_profile_with_data(client):
    upsert_profile(TEST_USER, {"cefr_level": "B2", "profession": "Designer"})
    r = client.get(f"/memory/profile?user_id={TEST_USER}")
    assert r.status_code == 200
    data = r.json()
    assert data["cefr_level"] == "B2"
    assert data["profession"] == "Designer"


# ── API: PUT /memory/profile ─────────────────────────────────────────────────

def test_api_put_profile(client):
    r = client.put(
        f"/memory/profile?user_id={TEST_USER}",
        json={"profession": "Engineer", "learning_goal": "fluent speaking"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["profession"] == "Engineer"
    assert data["learning_goal"] == "fluent speaking"


print("✅ Step 1 完成")
