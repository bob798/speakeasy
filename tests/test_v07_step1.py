"""
V0.7 Step 1 — ask_threads / ask_messages 数据表
user_id: test_user_v07_step1
"""
import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, Base, AskThread, AskMessage

TEST_USER = "test_user_v07_step1"


@pytest.fixture(autouse=True)
def cleanup():
    Base.metadata.create_all(engine)
    with OrmSession(engine) as s:
        # 先清消息，FK 级联保险
        thread_ids = [t.id for t in s.query(AskThread).filter_by(user_id=TEST_USER).all()]
        if thread_ids:
            s.query(AskMessage).filter(AskMessage.thread_id.in_(thread_ids)).delete(synchronize_session=False)
            s.query(AskThread).filter_by(user_id=TEST_USER).delete()
            s.commit()
    yield
    with OrmSession(engine) as s:
        thread_ids = [t.id for t in s.query(AskThread).filter_by(user_id=TEST_USER).all()]
        if thread_ids:
            s.query(AskMessage).filter(AskMessage.thread_id.in_(thread_ids)).delete(synchronize_session=False)
            s.query(AskThread).filter_by(user_id=TEST_USER).delete()
            s.commit()


def test_tables_exist():
    tables = set(inspect(engine).get_table_names())
    assert "ask_threads" in tables
    assert "ask_messages" in tables


def test_thread_columns():
    cols = {c["name"] for c in inspect(engine).get_columns("ask_threads")}
    assert cols == {
        "id", "user_id", "scope", "ref_type", "ref_id",
        "title", "context_payload", "status", "created_at", "updated_at",
    }


def test_message_columns():
    cols = {c["name"] for c in inspect(engine).get_columns("ask_messages")}
    assert cols == {"id", "thread_id", "role", "content", "created_at"}


def test_user_id_index_present():
    idx_cols = [
        set(ix["column_names"])
        for ix in inspect(engine).get_indexes("ask_threads")
    ]
    assert {"user_id"} in idx_cols


def test_insert_thread_and_messages_cascade():
    with OrmSession(engine) as s:
        t = AskThread(
            user_id=TEST_USER,
            scope="practice_explain",
            ref_type="explanation",
            ref_id="abc123",
            title="解读追问 · remain",
            context_payload='{"kind":"word","text":"remain"}',
        )
        s.add(t)
        s.flush()
        tid = t.id
        s.add(AskMessage(thread_id=tid, role="user", content="Why present tense here?"))
        s.add(AskMessage(thread_id=tid, role="assistant", content="Because it's a general truth."))
        s.commit()

        msgs = s.query(AskMessage).filter_by(thread_id=tid).order_by(AskMessage.id).all()
        assert len(msgs) == 2
        assert msgs[0].role == "user"
        assert msgs[1].role == "assistant"

        # 软删字段
        t2 = s.query(AskThread).filter_by(id=tid).first()
        assert t2.status == "active"
        t2.status = "deleted"
        s.commit()
        assert s.query(AskThread).filter_by(id=tid).first().status == "deleted"


def test_scope_and_ref_fields_are_strings_required():
    with OrmSession(engine) as s:
        t = AskThread(
            user_id=TEST_USER,
            scope="translate",
            ref_type="vocabulary",
            ref_id="999",
        )
        s.add(t)
        s.commit()
        fetched = s.query(AskThread).filter_by(user_id=TEST_USER, scope="translate").first()
        assert fetched is not None
        assert fetched.ref_type == "vocabulary"
        assert fetched.ref_id == "999"
        assert fetched.title == ""
        assert fetched.context_payload == "{}"
