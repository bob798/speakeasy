import pytest
from sqlalchemy.orm import Session as OrmSession
from app.models.db import engine, Base, Vocabulary
from app.services.vocab_service import save_item, update_explanation

USER = "test_user_v08_articles_task1"


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


def _seed(explanation_json=None, status="active"):
    item = save_item(
        user_id=USER, source_text="office banter",
        item_type="phrase", source_type="bbc_eaw", source_ref="ep-12",
        explanation_json=explanation_json,
    )
    if status == "deleted":
        with OrmSession(engine) as s:
            v = s.query(Vocabulary).filter_by(id=item["id"]).first()
            v.status = "deleted"
            s.commit()
    return item


def test_backfill_when_json_is_null():
    _seed(explanation_json=None)
    updated = update_explanation(
        user_id=USER, source_text="office banter", source_ref="ep-12",
        explanation_json='{"meaning": "办公室闲聊"}',
    )
    assert updated is True
    with OrmSession(engine) as s:
        v = s.query(Vocabulary).filter_by(user_id=USER, source_text="office banter").first()
        assert v.explanation_json == '{"meaning": "办公室闲聊"}'


def test_no_overwrite_when_json_already_set():
    _seed(explanation_json='{"meaning": "原值"}')
    updated = update_explanation(
        user_id=USER, source_text="office banter", source_ref="ep-12",
        explanation_json='{"meaning": "新值"}',
    )
    assert updated is False
    with OrmSession(engine) as s:
        v = s.query(Vocabulary).filter_by(user_id=USER, source_text="office banter").first()
        assert v.explanation_json == '{"meaning": "原值"}'


def test_force_overwrite_existing_json():
    """refresh=True 路径：必须能覆盖。"""
    _seed(explanation_json='{"meaning": "原值"}')
    updated = update_explanation(
        user_id=USER, source_text="office banter", source_ref="ep-12",
        explanation_json='{"meaning": "新值"}', force=True,
    )
    assert updated is True
    with OrmSession(engine) as s:
        v = s.query(Vocabulary).filter_by(user_id=USER, source_text="office banter").first()
        assert v.explanation_json == '{"meaning": "新值"}'


def test_backfill_works_on_deleted_record():
    _seed(explanation_json=None, status="deleted")
    updated = update_explanation(
        user_id=USER, source_text="office banter", source_ref="ep-12",
        explanation_json='{"meaning": "x"}',
    )
    assert updated is True


def test_record_not_found_returns_false():
    updated = update_explanation(
        user_id=USER, source_text="not-exists", source_ref="ep-99",
        explanation_json='{"meaning": "x"}',
    )
    assert updated is False
