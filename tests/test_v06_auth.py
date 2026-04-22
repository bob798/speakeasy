"""
V0.6 认证系统 — 注册 / 登录 / JWT / 密码哈希
user_id: test_user_v06_auth
"""
import time

import pytest
from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, Base, User
from app.services.auth_service import (
    register_user,
    login,
    authenticate,
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    get_user_by_id,
)


@pytest.fixture(autouse=True)
def cleanup():
    Base.metadata.create_all(engine)
    with OrmSession(engine) as s:
        s.query(User).filter(User.email.like("test_%@test.com")).delete(synchronize_session=False)
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(User).filter(User.email.like("test_%@test.com")).delete(synchronize_session=False)
        s.commit()


# ── 密码哈希 ────────────────────────────────────────────────

def test_hash_password_then_verify():
    h = hash_password("secret12345")
    assert h != "secret12345"                 # 必须被哈希
    assert verify_password("secret12345", h)
    assert not verify_password("wrong", h)


def test_hash_short_password_raises():
    with pytest.raises(ValueError, match="至少 8 位"):
        hash_password("short")


# ── 注册 ────────────────────────────────────────────────────

def test_register_basic():
    user = register_user("test_alice@test.com", "password123")
    assert user["email"] == "test_alice@test.com"
    assert user["id"].startswith("u_")
    assert user["created_at"] is not None


def test_register_custom_user_id():
    """指定 user_id（迁移场景）"""
    user = register_user("test_bob@test.com", "password123", user_id="bob")
    assert user["id"] == "bob"


def test_register_duplicate_email_raises():
    register_user("test_dup@test.com", "password123")
    with pytest.raises(ValueError, match="已注册"):
        register_user("test_dup@test.com", "another123")


def test_register_invalid_email_raises():
    with pytest.raises(ValueError, match="邮箱格式"):
        register_user("not-an-email", "password123")


def test_register_normalizes_email():
    user = register_user("  Test_UP@TEST.COM  ", "password123")
    assert user["email"] == "test_up@test.com"


# ── 登录 ────────────────────────────────────────────────────

def test_authenticate_valid():
    register_user("test_login@test.com", "password123")
    user = authenticate("test_login@test.com", "password123")
    assert user is not None
    assert user["email"] == "test_login@test.com"


def test_authenticate_wrong_password():
    register_user("test_wp@test.com", "password123")
    assert authenticate("test_wp@test.com", "wrongpass") is None


def test_authenticate_nonexistent():
    assert authenticate("test_nope@test.com", "whatever") is None


def test_authenticate_email_case_insensitive():
    register_user("test_case@test.com", "password123")
    user = authenticate("TEST_CASE@TEST.COM", "password123")
    assert user is not None


def test_login_returns_token_and_user():
    register_user("test_token@test.com", "password123")
    result = login("test_token@test.com", "password123")
    assert result is not None
    token, user = result
    assert isinstance(token, str) and len(token) > 20
    assert user["email"] == "test_token@test.com"


def test_login_bad_pass_returns_none():
    register_user("test_bad@test.com", "password123")
    assert login("test_bad@test.com", "bad") is None


# ── JWT ─────────────────────────────────────────────────────

def test_jwt_roundtrip():
    token = create_access_token("user_xyz")
    assert decode_access_token(token) == "user_xyz"


def test_jwt_invalid_returns_none():
    assert decode_access_token("not.a.token") is None
    assert decode_access_token("") is None
    assert decode_access_token("x" * 100) is None


def test_jwt_tampered_returns_none():
    token = create_access_token("user_xyz")
    tampered = token[:-3] + "xxx"
    assert decode_access_token(tampered) is None


# ── get_user_by_id ─────────────────────────────────────────

def test_get_user_by_id_returns_user():
    created = register_user("test_get@test.com", "password123")
    user = get_user_by_id(created["id"])
    assert user is not None
    assert user["email"] == "test_get@test.com"


def test_get_user_by_id_nonexistent_returns_none():
    assert get_user_by_id("nope_xyz") is None


# ── last_login 更新 ────────────────────────────────────────

def test_authenticate_updates_last_login():
    created = register_user("test_ll@test.com", "password123")
    assert created["last_login_at"] is None
    authenticate("test_ll@test.com", "password123")
    updated = get_user_by_id(created["id"])
    assert updated["last_login_at"] is not None
