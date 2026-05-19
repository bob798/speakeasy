import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession
from main import app
from app.models.db import engine, Vocabulary, Base
from app.routers.auth import get_current_user_id

USER = "test_user_v08_articles_task9"
client = TestClient(app)


@pytest.fixture(autouse=True)
def _override_user():
    app.dependency_overrides[get_current_user_id] = lambda: USER
    yield
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture(autouse=True)
def _cleanup():
    Base.metadata.create_all(engine)
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_articles_%")).delete()
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_articles_%")).delete()
        s.commit()


@pytest.fixture
def stub(monkeypatch):
    async def _fake_explain(text, kind, user_id, context="", force=False):
        return {"explanation": {"meaning": "x"}, "cefr_level": "B1", "cached": False}
    import app.routers.articles as ar
    monkeypatch.setattr(ar, "explain_text", _fake_explain)


def test_articles_explain_works(stub):
    resp = client.post("/articles/explain", json={"text": "hi", "kind": "word"})
    assert resp.status_code == 200


def test_practice_alias_still_works(stub):
    resp = client.post("/practice/explain", json={"text": "hi", "kind": "word"})
    assert resp.status_code == 200


def test_articles_phonetic_works():
    resp = client.post("/articles/explain/phonetic", json={"text": "office"})
    assert resp.status_code == 200


def test_practice_phonetic_alias_works():
    resp = client.post("/practice/explain/phonetic", json={"text": "office"})
    assert resp.status_code == 200


def test_articles_due_works():
    """非 explain 端点也得跟着改名（不只是 explain 这 3 个）。"""
    resp = client.get("/articles/due")
    # 200 或 401 都算路由挂上；404 = 没挂上
    assert resp.status_code != 404


def test_articles_subtitles_works():
    """sample 抽查另一组端点。"""
    resp = client.post("/articles/subtitles", json={"video_url": ""})
    assert resp.status_code != 404


def test_openapi_no_duplicate_practice_paths():
    """alias 注册需 include_in_schema=False，防止 OpenAPI 出现两套同名接口。"""
    schema = client.get("/openapi.json").json()
    paths = list(schema.get("paths", {}).keys())
    practice_paths = [p for p in paths if p.startswith("/practice")]
    assert practice_paths == [], f"OpenAPI 不应暴露 /practice/* 别名: {practice_paths}"
