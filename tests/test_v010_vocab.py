"""V0.10 · vocab_service 单测

覆盖：
  - save_item: 去重、复活、参数校验
  - list_items: type / source_ref / due 过滤
  - delete_item / rate_item: 软删 + FSRS 推进
"""
import pytest

from app.services import vocab_service
from app.services.fsrs_utils import is_due

USER = "user_test_v010"


@pytest.fixture(autouse=True)
def _reset():
    """每个测试前清掉该用户的所有条目（硬删）"""
    from sqlalchemy.orm import Session as OrmSession
    from app.models.db import engine, Vocabulary
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter_by(user_id=USER).delete()
        s.commit()
    yield


def test_save_item_creates_with_fsrs_card():
    item = vocab_service.save_item(
        user_id=USER,
        source_text="serendipity",
        translated_text="意外的好运",
        item_type="word",
        source_type="translate",
    )
    assert item["id"] > 0
    assert item["item_type"] == "word"
    assert item["source_type"] == "translate"
    assert item["due"] is not None  # FSRS 已初始化


def test_save_item_dedupes_by_user_text_ref():
    a = vocab_service.save_item(
        user_id=USER, source_text="dedupe", item_type="word",
        source_type="bbc_eaw", source_ref="01-the-interview",
    )
    b = vocab_service.save_item(
        user_id=USER, source_text="dedupe", item_type="word",
        source_type="bbc_eaw", source_ref="01-the-interview",
    )
    assert a["id"] == b["id"]


def test_save_item_different_source_ref_creates_new():
    a = vocab_service.save_item(
        user_id=USER, source_text="ambiguous", source_ref="article-a",
        source_type="bbc_eaw",
    )
    b = vocab_service.save_item(
        user_id=USER, source_text="ambiguous", source_ref="article-b",
        source_type="bbc_eaw",
    )
    assert a["id"] != b["id"]


def test_delete_then_resave_revives():
    item = vocab_service.save_item(user_id=USER, source_text="revive_me")
    vocab_service.delete_item(item["id"], USER)

    again = vocab_service.save_item(user_id=USER, source_text="revive_me")
    assert again["id"] == item["id"]
    assert again["status"] == "active"


def test_list_filters_by_type_and_source():
    vocab_service.save_item(user_id=USER, source_text="word_x", item_type="word")
    vocab_service.save_item(user_id=USER, source_text="phrase y z", item_type="phrase")
    vocab_service.save_item(
        user_id=USER, source_text="from bbc", item_type="sentence",
        source_type="bbc_eaw", source_ref="ep-1",
    )

    words = vocab_service.list_items(user_id=USER, item_type="word")
    assert len(words) == 1 and words[0]["source_text"] == "word_x"

    bbc = vocab_service.list_items(user_id=USER, source_ref="ep-1")
    assert len(bbc) == 1 and bbc[0]["source_text"] == "from bbc"


def test_rate_item_advances_due():
    item = vocab_service.save_item(user_id=USER, source_text="rate_me", item_type="word")
    initial_due = item["due"]
    result = vocab_service.rate_item(item["id"], USER, "good")
    assert result["due"] is not None
    assert result["due"] != initial_due  # FSRS 推进了
    assert result["item"]["last_reviewed_at"] is not None


def test_rate_item_invalid_rating_raises():
    item = vocab_service.save_item(user_id=USER, source_text="bad_rate")
    with pytest.raises(ValueError, match="rating"):
        vocab_service.rate_item(item["id"], USER, "meh")


def test_rate_item_unknown_id_raises_lookup():
    with pytest.raises(LookupError):
        vocab_service.rate_item(999999, USER, "good")


def test_save_item_empty_source_raises():
    with pytest.raises(ValueError, match="source_text"):
        vocab_service.save_item(user_id=USER, source_text="   ")


def test_save_item_invalid_type_raises():
    with pytest.raises(ValueError, match="item_type"):
        vocab_service.save_item(user_id=USER, source_text="x", item_type="garbage")


def test_bulk_save_from_bbc_creates_sentence_items():
    n = vocab_service.bulk_save_from_bbc(
        user_id=USER,
        slug="ep-99",
        segments=[
            {"text": "Sentence one."},
            {"text": "Sentence two.", "context": "from a transcript"},
            {"text": ""},  # 空跳过
        ],
    )
    assert n == 2
    items = vocab_service.list_items(user_id=USER, source_ref="ep-99")
    assert len(items) == 2
    assert all(it["source_type"] == "bbc_eaw" for it in items)
    assert all(it["item_type"] == "sentence" for it in items)
