"""
V0.7 Step 3 — /ask API 路由
user_id: test_user_v07_step3（通过注册新用户取得 token）
"""
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from main import app
from app.models.db import engine, Base, User, AskThread, AskMessage

TEST_EMAIL = "apitest_ask_v07@test.com"
TEST_PASSWORD = "password_ask_v07"

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup():
    Base.metadata.create_all(engine)
    with OrmSession(engine) as s:
        users = s.query(User).filter(User.email == TEST_EMAIL).all()
        uids = [u.id for u in users]
        if uids:
            tids = [t.id for t in s.query(AskThread).filter(AskThread.user_id.in_(uids)).all()]
            if tids:
                s.query(AskMessage).filter(AskMessage.thread_id.in_(tids)).delete(synchronize_session=False)
                s.query(AskThread).filter(AskThread.user_id.in_(uids)).delete(synchronize_session=False)
            s.query(User).filter(User.id.in_(uids)).delete(synchronize_session=False)
            s.commit()
    yield
    with OrmSession(engine) as s:
        users = s.query(User).filter(User.email == TEST_EMAIL).all()
        uids = [u.id for u in users]
        if uids:
            tids = [t.id for t in s.query(AskThread).filter(AskThread.user_id.in_(uids)).all()]
            if tids:
                s.query(AskMessage).filter(AskMessage.thread_id.in_(tids)).delete(synchronize_session=False)
                s.query(AskThread).filter(AskThread.user_id.in_(uids)).delete(synchronize_session=False)
            s.query(User).filter(User.id.in_(uids)).delete(synchronize_session=False)
            s.commit()


def _register_and_token() -> str:
    resp = client.post("/auth/register", json={
        "email": TEST_EMAIL, "password": TEST_PASSWORD, "display_name": "Ask Tester",
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _mock_client(answers):
    it = iter(answers)
    m = AsyncMock()
    m.complete = AsyncMock(side_effect=lambda *a, **kw: next(it))
    return patch("app.services.ask_service.get_client", return_value=m), m


def test_create_thread_requires_auth():
    resp = client.post("/ask/threads", json={
        "scope": "practice_explain", "ref_type": "explanation", "ref_id": "abc",
        "context": {}, "question": "why?",
    })
    assert resp.status_code == 401


def test_full_create_append_get_list_delete_flow():
    token = _register_and_token()
    h = _auth(token)

    patcher, _ = _mock_client(["first answer", "second answer"])
    with patcher:
        # create
        resp = client.post("/ask/threads", json={
            "scope": "practice_explain",
            "ref_type": "explanation",
            "ref_id": "hash_xyz",
            "context": {"kind": "word", "text": "remain", "cefr_level": "B1"},
            "question": "Why present tense?",
        }, headers=h)
        assert resp.status_code == 201, resp.text
        body = resp.json()
        tid = body["thread_id"]
        assert len(body["messages"]) == 2
        assert body["messages"][1]["content"] == "first answer"

        # append
        resp = client.post(f"/ask/threads/{tid}/messages",
                          json={"question": "And next level usage?"}, headers=h)
        assert resp.status_code == 200, resp.text
        assert resp.json()["answer"] == "second answer"

    # get
    resp = client.get(f"/ask/threads/{tid}", headers=h)
    assert resp.status_code == 200
    thread = resp.json()
    assert thread["scope"] == "practice_explain"
    assert thread["ref_id"] == "hash_xyz"
    assert len(thread["messages"]) == 4  # 2 轮对话 = 4 条消息

    # list（按 ref_id 过滤）
    resp = client.get("/ask/threads",
                     params={"scope": "practice_explain", "ref_id": "hash_xyz"},
                     headers=h)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == tid

    # list（另一 ref_id → 0 条）
    resp = client.get("/ask/threads",
                     params={"scope": "practice_explain", "ref_id": "nope"},
                     headers=h)
    assert resp.json()["count"] == 0

    # delete
    resp = client.delete(f"/ask/threads/{tid}", headers=h)
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True

    # delete 后 get 404
    resp = client.get(f"/ask/threads/{tid}", headers=h)
    assert resp.status_code == 404


def test_create_thread_rejects_empty_question():
    token = _register_and_token()
    resp = client.post("/ask/threads", json={
        "scope": "practice_explain", "ref_type": "explanation", "ref_id": "x",
        "context": {}, "question": "   ",
    }, headers=_auth(token))
    assert resp.status_code == 400
    assert "问题" in resp.json()["detail"]


def test_create_thread_rejects_unknown_scope():
    token = _register_and_token()
    resp = client.post("/ask/threads", json={
        "scope": "nope_scope", "ref_type": "x", "ref_id": "x",
        "context": {}, "question": "q?",
    }, headers=_auth(token))
    assert resp.status_code == 400


def test_append_to_others_thread_forbidden():
    token_a = _register_and_token()
    # 注册另一个用户
    other_email = "apitest_ask_v07_other@test.com"
    try:
        r = client.post("/auth/register", json={
            "email": other_email, "password": "otherpass12", "display_name": "B",
        })
        assert r.status_code == 201
        token_b = r.json()["token"]

        patcher, _ = _mock_client(["a1"])
        with patcher:
            resp = client.post("/ask/threads", json={
                "scope": "practice_explain", "ref_type": "explanation", "ref_id": "zz",
                "context": {}, "question": "q?",
            }, headers=_auth(token_a))
            assert resp.status_code == 201
            tid = resp.json()["thread_id"]

        # 另一用户追问应 400
        resp = client.post(f"/ask/threads/{tid}/messages",
                          json={"question": "steal?"}, headers=_auth(token_b))
        assert resp.status_code == 400
        assert "无权" in resp.json()["detail"] or "不存在" in resp.json()["detail"]
    finally:
        with OrmSession(engine) as s:
            others = s.query(User).filter(User.email == other_email).all()
            oids = [u.id for u in others]
            if oids:
                tids = [t.id for t in s.query(AskThread).filter(AskThread.user_id.in_(oids)).all()]
                if tids:
                    s.query(AskMessage).filter(AskMessage.thread_id.in_(tids)).delete(synchronize_session=False)
                    s.query(AskThread).filter(AskThread.user_id.in_(oids)).delete(synchronize_session=False)
                s.query(User).filter(User.id.in_(oids)).delete(synchronize_session=False)
                s.commit()


def test_translate_scope_also_works_via_api():
    token = _register_and_token()
    patcher, _ = _mock_client(["translate coach answer"])
    with patcher:
        resp = client.post("/ask/threads", json={
            "scope": "translate",
            "ref_type": "vocabulary",
            "ref_id": "42",
            "context": {
                "source_text": "我做过推荐系统",
                "translated_text": "I worked on recommendation systems",
                "direction": "zh2en",
            },
            "question": "这里用过去时合适吗？",
        }, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    assert resp.json()["messages"][1]["content"] == "translate coach answer"
