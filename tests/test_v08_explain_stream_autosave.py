import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession
from main import app
from app.models.db import engine, Vocabulary, Base
from app.routers.auth import get_current_user_id

USER = "test_user_v08_articles_task8"
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
def stub_stream(monkeypatch):
    """伪造流式：返回 field/value 事件，最后 _done。"""
    async def _fake(text, user_id, force=False):
        yield json.dumps({"field": "meaning", "value": "办公室闲聊"}, ensure_ascii=False)
        yield json.dumps({"field": "grammar", "value": "名词短语"}, ensure_ascii=False)
        yield json.dumps({"_done": True, "cefr_level": "B1"}, ensure_ascii=False)

    import app.routers.articles as pr
    monkeypatch.setattr(pr, "stream_sentence_explanation", _fake)


def test_stream_writes_pending_at_entry_and_backfills_on_done(stub_stream):
    body = {
        "text": "office banter exists", "source_type": "bbc_eaw",
        "source_ref": "ep-12", "item_type": "sentence", "context": "in the meeting",
    }
    with client.stream("POST", "/practice/explain/stream", json=body) as resp:
        assert resp.status_code == 200
        chunks = list(resp.iter_lines())
    assert any('"_done"' in c for c in chunks)
    with OrmSession(engine) as s:
        v = s.query(Vocabulary).filter_by(user_id=USER, source_text="office banter exists").first()
        assert v is not None
        assert v.source_type == "bbc_eaw"
        assert v.item_type == "sentence"
        parsed = json.loads(v.explanation_json)
        assert parsed["meaning"] == "办公室闲聊"
        assert parsed["grammar"] == "名词短语"


def test_stream_cache_hit_backfills(monkeypatch):
    async def _fake_cached(text, user_id, force=False):
        yield json.dumps({
            "_cached": True, "cefr_level": "B1",
            "explanation": {"meaning": "cached"},
        }, ensure_ascii=False)
        yield json.dumps({"_done": True}, ensure_ascii=False)

    import app.routers.articles as pr
    monkeypatch.setattr(pr, "stream_sentence_explanation", _fake_cached)

    body = {"text": "cached text", "source_type": "bbc_eaw", "source_ref": "ep-1", "item_type": "sentence"}
    with client.stream("POST", "/practice/explain/stream", json=body) as resp:
        list(resp.iter_lines())
    with OrmSession(engine) as s:
        v = s.query(Vocabulary).filter_by(user_id=USER, source_text="cached text").first()
        assert v is not None
        assert json.loads(v.explanation_json)["meaning"] == "cached"


def test_stream_without_source_no_vocab(stub_stream):
    body = {"text": "no source"}
    with client.stream("POST", "/practice/explain/stream", json=body) as resp:
        list(resp.iter_lines())
    with OrmSession(engine) as s:
        cnt = s.query(Vocabulary).filter_by(user_id=USER, source_text="no source").count()
        assert cnt == 0
