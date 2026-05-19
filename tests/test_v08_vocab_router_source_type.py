import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession
from main import app  # project entry is repo-root main.py
from app.models.db import engine, Vocabulary, Base
from app.services.vocab_service import save_item
from app.routers.auth import get_current_user_id

USER = "test_user_v08_articles_task3"
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


def test_get_vocab_with_source_type_bbc():
    save_item(user_id=USER, source_text="bbc", item_type="word", source_type="bbc_eaw", source_ref="ep-1")
    save_item(user_id=USER, source_text="trans", item_type="word", source_type="translate", source_ref=None)
    resp = client.get("/vocab?source_type=bbc_eaw")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["items"][0]["source_text"] == "bbc"


def test_get_vocab_no_source_type_returns_all():
    save_item(user_id=USER, source_text="bbc", item_type="word", source_type="bbc_eaw", source_ref="ep-1")
    save_item(user_id=USER, source_text="trans", item_type="word", source_type="translate", source_ref=None)
    resp = client.get("/vocab")
    assert resp.status_code == 200
    assert resp.json()["count"] == 2
