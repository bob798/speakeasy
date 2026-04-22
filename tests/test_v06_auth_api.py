"""
V0.6 认证系统 API 级测试 — TestClient HTTP 流程
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from main import app
from app.models.db import engine, Base, User


client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup():
    Base.metadata.create_all(engine)
    with OrmSession(engine) as s:
        s.query(User).filter(User.email.like("apitest_%@test.com")).delete(synchronize_session=False)
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(User).filter(User.email.like("apitest_%@test.com")).delete(synchronize_session=False)
        s.commit()


def test_register_and_login_flow():
    # 注册
    resp = client.post("/auth/register", json={
        "email": "apitest_one@test.com",
        "password": "password123",
        "display_name": "Tester",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "token" in data
    assert data["user"]["email"] == "apitest_one@test.com"

    # /auth/me 带 token
    token = data["token"]
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["user"]["email"] == "apitest_one@test.com"

    # 登录
    resp = client.post("/auth/login", json={
        "email": "apitest_one@test.com",
        "password": "password123",
    })
    assert resp.status_code == 200
    assert resp.json()["user"]["email"] == "apitest_one@test.com"


def test_register_duplicate_returns_400():
    client.post("/auth/register", json={
        "email": "apitest_dup@test.com", "password": "password123",
    })
    resp = client.post("/auth/register", json={
        "email": "apitest_dup@test.com", "password": "password123",
    })
    assert resp.status_code == 400


def test_login_wrong_password_returns_401():
    client.post("/auth/register", json={
        "email": "apitest_lw@test.com", "password": "password123",
    })
    resp = client.post("/auth/login", json={
        "email": "apitest_lw@test.com", "password": "bad-pass",
    })
    assert resp.status_code == 401


def test_me_without_token_returns_401():
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_with_invalid_token_returns_401():
    resp = client.get("/auth/me", headers={"Authorization": "Bearer junk.token.here"})
    assert resp.status_code == 401


def test_protected_endpoint_without_token_returns_401():
    """挑一个受保护端点验证中间件"""
    resp = client.get("/translate/vocabulary")
    assert resp.status_code == 401


def test_protected_endpoint_with_valid_token_works():
    reg = client.post("/auth/register", json={
        "email": "apitest_auth@test.com", "password": "password123",
    }).json()
    token = reg["token"]
    resp = client.get(
        "/translate/vocabulary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["count"] == 0
