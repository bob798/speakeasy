"""
V0.7 Step 6 — 单词 IPA 本地秒出
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from main import app
from app.models.db import engine, Base, User
from app.services.explain_service import quick_phonetic

TEST_EMAIL = "apitest_phonetic_v07@test.com"
TEST_PASSWORD = "password_ph_v07"

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup():
    Base.metadata.create_all(engine)
    with OrmSession(engine) as s:
        s.query(User).filter(User.email == TEST_EMAIL).delete(synchronize_session=False)
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(User).filter(User.email == TEST_EMAIL).delete(synchronize_session=False)
        s.commit()


# ── service 单元 ───────────────────────────────────────────

def test_quick_phonetic_known_word():
    p = quick_phonetic("remain")
    assert p is not None
    assert p.startswith("/") and p.endswith("/")
    assert "m" in p  # 粗略字符断言避免过度耦合具体符号
    assert "ɪ" in p or "e" in p  # 有元音符号


def test_quick_phonetic_case_insensitive():
    assert quick_phonetic("Remain") == quick_phonetic("remain")


def test_quick_phonetic_unknown_returns_none():
    assert quick_phonetic("xqwzyblort") is None


def test_quick_phonetic_rejects_non_word():
    assert quick_phonetic("") is None
    assert quick_phonetic("hello world") is None     # 多词
    assert quick_phonetic("123") is None              # 数字
    assert quick_phonetic("!?@") is None              # 符号


def test_quick_phonetic_allows_hyphen_and_apostrophe():
    # 词典可能不收录，但正则必须接受
    import re as _re
    from app.services.explain_service import _WORD_RE
    assert _WORD_RE.match("don't")
    assert _WORD_RE.match("well-known")


# ── endpoint ────────────────────────────────────────────────

def _auth_token() -> str:
    resp = client.post("/auth/register", json={
        "email": TEST_EMAIL, "password": TEST_PASSWORD, "display_name": "PhoneticTester",
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["token"]


def test_phonetic_endpoint_known_word():
    # 该端点不需要登录（前端并行调用，允许匿名同样合理；如需登录后续再加）
    resp = client.post("/practice/explain/phonetic", json={"text": "remain"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["phonetic"] is not None
    assert data["phonetic"].startswith("/")


def test_phonetic_endpoint_unknown_word():
    resp = client.post("/practice/explain/phonetic", json={"text": "xqwzyblort"})
    assert resp.status_code == 200
    assert resp.json()["phonetic"] is None


def test_phonetic_endpoint_empty_text_400():
    resp = client.post("/practice/explain/phonetic", json={"text": "   "})
    assert resp.status_code == 400


def test_phonetic_endpoint_multiword_returns_null():
    resp = client.post("/practice/explain/phonetic", json={"text": "hello world"})
    assert resp.status_code == 200
    # 短语不走本地秒出
    assert resp.json()["phonetic"] is None


# ── frontend wiring ────────────────────────────────────────

def test_frontend_fires_phonetic_first():
    from pathlib import Path
    src = Path("static/practice.html").read_text(encoding="utf-8")
    # 单词模式先调 /phonetic
    assert "/practice/explain/phonetic" in src
    assert "renderExplainQuickPhonetic" in src
