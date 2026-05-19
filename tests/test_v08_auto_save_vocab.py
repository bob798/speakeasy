import pytest
from sqlalchemy.orm import Session as OrmSession
from app.models.db import engine, Vocabulary, Base
from app.routers.practice import _auto_save_vocab, _resolve_item_type

USER = "test_user_v08_articles_task5"


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


def test_resolve_item_type_explicit_wins():
    assert _resolve_item_type(text="Hello world", explicit="phrase", kind="sentence") == "phrase"


def test_resolve_item_type_falls_back_to_kind():
    assert _resolve_item_type(text="Hello", explicit=None, kind="word") == "word"
    assert _resolve_item_type(text="Hello world.", explicit=None, kind="sentence") == "sentence"


def test_resolve_item_type_word_kind_multi_token_becomes_phrase():
    assert _resolve_item_type(text="rocket science", explicit=None, kind="word") == "phrase"


def test_auto_save_writes_pending_record():
    ok = _auto_save_vocab(
        user_id=USER, text="office banter", context="Some context.",
        source_type="bbc_eaw", source_ref="ep-12", item_type="phrase",
    )
    assert ok is True
    with OrmSession(engine) as s:
        v = s.query(Vocabulary).filter_by(user_id=USER, source_text="office banter").first()
        assert v is not None
        assert v.source_type == "bbc_eaw"
        assert v.source_ref == "ep-12"
        assert v.item_type == "phrase"
        assert v.explanation_json is None
        assert v.status == "active"


def test_auto_save_no_source_type_is_noop():
    ok = _auto_save_vocab(
        user_id=USER, text="x", context="", source_type=None, source_ref=None, item_type="word",
    )
    assert ok is False
    with OrmSession(engine) as s:
        cnt = s.query(Vocabulary).filter_by(user_id=USER).count()
        assert cnt == 0


def test_auto_save_no_user_id_is_noop():
    """匿名场景（phonetic 端点未登录）安全跳过。"""
    ok = _auto_save_vocab(
        user_id=None, text="x", context="", source_type="bbc_eaw",
        source_ref="ep-1", item_type="word",
    )
    assert ok is False


def test_auto_save_failure_does_not_raise(monkeypatch):
    """vocab_service.save_item 抛错时，_auto_save_vocab 应吞掉并返回 False。"""
    from app.services import vocab_service as vs

    def _raise(**kwargs):
        raise RuntimeError("db locked")

    monkeypatch.setattr(vs, "save_item", _raise)
    ok = _auto_save_vocab(
        user_id=USER, text="x", context="", source_type="bbc_eaw",
        source_ref="ep-1", item_type="word",
    )
    assert ok is False  # 异常被吞，返回 False
