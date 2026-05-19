import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession
from main import app
from app.models.db import engine, Vocabulary, Base
from app.routers.auth import get_current_user_id_optional

USER = "test_user_v08_articles_task7"
client = TestClient(app)


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


def test_phonetic_logged_in_with_source_creates_pending():
    app.dependency_overrides[get_current_user_id_optional] = lambda: USER
    try:
        body = {"text": "office", "source_type": "bbc_eaw", "source_ref": "ep-12", "item_type": "word"}
        resp = client.post("/practice/explain/phonetic", json=body)
        assert resp.status_code == 200
        with OrmSession(engine) as s:
            v = s.query(Vocabulary).filter_by(user_id=USER, source_text="office").first()
            assert v is not None, "phonetic 端点应已写入 vocabulary 占位"
            assert v.explanation_json is None  # phonetic 不回填
            assert v.source_type == "bbc_eaw"
            assert v.item_type == "word"
    finally:
        app.dependency_overrides.pop(get_current_user_id_optional, None)


def test_phonetic_anonymous_still_returns_ipa_no_vocab():
    app.dependency_overrides[get_current_user_id_optional] = lambda: None
    try:
        body = {"text": "office", "source_type": "bbc_eaw", "source_ref": "ep-12", "item_type": "word"}
        resp = client.post("/practice/explain/phonetic", json=body)
        assert resp.status_code == 200
        with OrmSession(engine) as s:
            cnt = s.query(Vocabulary).filter_by(source_text="office").count()
            assert cnt == 0
    finally:
        app.dependency_overrides.pop(get_current_user_id_optional, None)
