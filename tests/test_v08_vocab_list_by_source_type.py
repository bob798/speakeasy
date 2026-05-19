import pytest
from sqlalchemy.orm import Session as OrmSession
from app.models.db import engine, Vocabulary, Base
from app.services.vocab_service import save_item, list_items

USER = "test_user_v08_articles_task2"


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


def test_filter_by_bbc_eaw_returns_only_bbc():
    save_item(user_id=USER, source_text="bbc word", item_type="word",
              source_type="bbc_eaw", source_ref="ep-1")
    save_item(user_id=USER, source_text="translate word", item_type="word",
              source_type="translate", source_ref=None)
    items = list_items(user_id=USER, source_type="bbc_eaw")
    assert len(items) == 1
    assert items[0]["source_text"] == "bbc word"


def test_no_filter_returns_all():
    save_item(user_id=USER, source_text="bbc word", item_type="word",
              source_type="bbc_eaw", source_ref="ep-1")
    save_item(user_id=USER, source_text="translate word", item_type="word",
              source_type="translate", source_ref=None)
    items = list_items(user_id=USER)
    assert len(items) == 2
