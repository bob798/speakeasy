import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession
from main import app
from app.models.db import engine, Vocabulary, Base
from app.routers.auth import get_current_user_id

USER = "test_user_v08_articles_task6"
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
def stub_explain(monkeypatch):
    """避免真实 LLM 调用。"""
    from app.services import explain_service

    async def _fake(text, kind, user_id, context="", force=False):
        return {"explanation": {"meaning": "stub-" + text}, "cefr_level": "B1", "cached": False}

    monkeypatch.setattr(explain_service, "explain_text", _fake)
    # 也替换路由直接 import 的那个引用
    import app.routers.articles as pr
    monkeypatch.setattr(pr, "explain_text", _fake)


def test_explain_with_source_creates_pending_then_backfills(stub_explain):
    body = {
        "text": "office banter", "kind": "word",
        "source_type": "bbc_eaw", "source_ref": "ep-12", "item_type": "phrase",
    }
    resp = client.post("/practice/explain", json=body)
    assert resp.status_code == 200
    with OrmSession(engine) as s:
        v = s.query(Vocabulary).filter_by(user_id=USER, source_text="office banter").first()
        assert v is not None
        assert v.explanation_json is not None
        assert json.loads(v.explanation_json)["meaning"] == "stub-office banter"


def test_explain_without_source_no_vocab(stub_explain):
    body = {"text": "hello", "kind": "word"}
    resp = client.post("/practice/explain", json=body)
    assert resp.status_code == 200
    with OrmSession(engine) as s:
        cnt = s.query(Vocabulary).filter_by(user_id=USER).count()
        assert cnt == 0


def test_explain_refresh_overwrites_existing_json(stub_explain):
    """refresh=True 路径：已有 explanation_json 应被新值覆盖。"""
    from app.services.vocab_service import save_item
    save_item(
        user_id=USER, source_text="重写测试", item_type="word",
        source_type="bbc_eaw", source_ref="ep-1",
        explanation_json='{"meaning": "旧值"}',
    )
    body = {
        "text": "重写测试", "kind": "word", "refresh": True,
        "source_type": "bbc_eaw", "source_ref": "ep-1", "item_type": "word",
    }
    resp = client.post("/practice/explain", json=body)
    assert resp.status_code == 200
    with OrmSession(engine) as s:
        v = s.query(Vocabulary).filter_by(user_id=USER, source_text="重写测试").first()
        assert json.loads(v.explanation_json)["meaning"] == "stub-重写测试"
