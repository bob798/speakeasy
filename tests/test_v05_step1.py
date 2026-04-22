"""
V0.5 Step 1 — Vocabulary 数据模型
user_id: test_user_v05_step1
"""
import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, Base, Vocabulary

TEST_USER = "test_user_v05_step1"


@pytest.fixture(autouse=True)
def cleanup():
    Base.metadata.create_all(engine)
    yield
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter_by(user_id=TEST_USER).delete()
        s.commit()


# ── 表结构 ──────────────────────────────────────────────────

def test_vocabulary_table_created():
    inspector = sa_inspect(engine)
    tables = inspector.get_table_names()
    assert "vocabulary" in tables


def test_vocabulary_columns():
    inspector = sa_inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("vocabulary")}
    assert {"id", "user_id", "source_text", "translated_text", "direction", "context", "created_at", "status"} <= cols


# ── 默认值 ───────────────────────────────────────────────────

def test_vocabulary_default_values():
    with OrmSession(engine) as s:
        v = Vocabulary(
            user_id=TEST_USER,
            source_text="你好",
            translated_text="Hello",
            direction="zh2en",
        )
        s.add(v)
        s.commit()
        s.refresh(v)

        assert v.id is not None
        assert v.status == "active"
        assert v.context is None
        assert v.created_at is not None


def test_vocabulary_with_context():
    with OrmSession(engine) as s:
        v = Vocabulary(
            user_id=TEST_USER,
            source_text="I love reading",
            translated_text="我喜欢阅读",
            direction="en2zh",
            context="学英语语境",
        )
        s.add(v)
        s.commit()
        s.refresh(v)

        assert v.direction == "en2zh"
        assert v.context == "学英语语境"


def test_vocabulary_soft_delete():
    with OrmSession(engine) as s:
        v = Vocabulary(
            user_id=TEST_USER,
            source_text="推荐系统",
            translated_text="recommendation system",
            direction="zh2en",
        )
        s.add(v)
        s.commit()
        s.refresh(v)
        vid = v.id

    with OrmSession(engine) as s:
        v2 = s.query(Vocabulary).filter_by(id=vid).first()
        v2.status = "deleted"
        s.commit()

    with OrmSession(engine) as s:
        v3 = s.query(Vocabulary).filter_by(id=vid).first()
        assert v3.status == "deleted"
