"""Library smoke + edge case tests

Smoke tests: verify basic endpoint availability
Edge cases: input validation, truncation, stub-driven backfill, refetch, vocab persistence
"""
import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from main import app
from app.models.db import engine, LibraryArticle, Vocabulary, init_db
from app.routers.auth import get_current_user_id, get_current_user_id_optional

USER = "test_user_library_smoke"
client = TestClient(app)


# ── Fixtures ───────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _override_user():
    app.dependency_overrides[get_current_user_id] = lambda: USER
    app.dependency_overrides[get_current_user_id_optional] = lambda: USER
    yield
    app.dependency_overrides.pop(get_current_user_id, None)
    app.dependency_overrides.pop(get_current_user_id_optional, None)


@pytest.fixture(autouse=True)
def _cleanup():
    init_db()
    with OrmSession(engine) as s:
        s.query(LibraryArticle).filter(
            LibraryArticle.user_id.like("test_user_library_smoke%")
        ).delete()
        s.query(Vocabulary).filter(
            Vocabulary.user_id.like("test_user_library_smoke%")
        ).delete()
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(LibraryArticle).filter(
            LibraryArticle.user_id.like("test_user_library_smoke%")
        ).delete()
        s.query(Vocabulary).filter(
            Vocabulary.user_id.like("test_user_library_smoke%")
        ).delete()
        s.commit()


@pytest.fixture
def stub_explain(monkeypatch):
    """Stub LLM explain to avoid real API requests."""
    from app.services import explain_service
    import app.routers.library as lr

    async def _fake(text, kind, user_id, context="", force=False):
        return {
            "explanation": {"meaning": "stub-" + text, "phonetic": "stʌb"},
            "cefr_level": "B1",
            "cached": False,
        }

    monkeypatch.setattr(explain_service, "explain_text", _fake)
    monkeypatch.setattr(lr, "explain_text", _fake)


@pytest.fixture
def article_id():
    """Create a minimal article and return its id."""
    resp = client.post(
        "/library/articles",
        json={"markdown": "# Smoke Article\n\nTest content for smoke tests.", "title": "Smoke Article"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ── Smoke tests ────────────────────────────────────────────

def test_smoke_import_markdown():
    """POST /library/articles with markdown → 201."""
    resp = client.post(
        "/library/articles",
        json={"markdown": "# Smoke Test\n\nHello world content.", "title": "Smoke Test"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "active"
    assert data["existing"] is False


def test_smoke_list_empty():
    """GET /library/articles → 200 with empty articles list."""
    resp = client.get("/library/articles")
    assert resp.status_code == 200
    data = resp.json()
    assert "articles" in data
    assert data["articles"] == []


def test_smoke_get_nonexistent():
    """GET /library/articles/999 → 404."""
    resp = client.get("/library/articles/999")
    assert resp.status_code == 404


def test_smoke_delete_nonexistent():
    """DELETE /library/articles/999 → 404."""
    resp = client.delete("/library/articles/999")
    assert resp.status_code == 404


def test_smoke_phonetic(article_id):
    """POST /library/articles/{id}/explain/phonetic with {text:'hello'} → 200 + phonetic field."""
    resp = client.post(
        f"/library/articles/{article_id}/explain/phonetic",
        json={"text": "hello"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "phonetic" in data


def test_smoke_explain_nonexistent_article():
    """POST /library/articles/999/explain with valid body → 404."""
    resp = client.post(
        "/library/articles/999/explain",
        json={"text": "hello world", "kind": "word"},
    )
    assert resp.status_code == 404


# ── Edge case tests ────────────────────────────────────────

def test_import_both_url_and_markdown():
    """POST with both url and markdown → 201 (url takes priority per service logic)."""
    fake_md = "# URL Priority\n\nContent from URL extraction."
    fake_meta = {"title": "URL Priority", "site_name": "example.com", "author": None}

    with patch("app.services.library_service._extract_from_url") as mock_extract:
        mock_extract.return_value = (fake_md, fake_meta)
        resp = client.post(
            "/library/articles",
            json={
                "url": "https://example.com/url-priority",
                "markdown": "# Markdown content\n\nThis should be ignored.",
                "title": "Should use URL",
            },
        )

    assert resp.status_code == 201
    data = resp.json()
    # URL was used — source_url populated, content from URL
    assert data["source_url"] == "https://example.com/url-priority"
    assert data["existing"] is False


def test_import_empty_body():
    """POST /library/articles with {} → 400."""
    resp = client.post("/library/articles", json={})
    assert resp.status_code == 400


def test_import_empty_markdown():
    """POST with markdown='' → 400 (empty string treated as missing)."""
    resp = client.post(
        "/library/articles",
        json={"markdown": ""},
    )
    assert resp.status_code == 400


def test_import_very_long_markdown():
    """POST with markdown > 100000 chars → 201 with source_meta.truncated=true."""
    long_markdown = "# Long Article\n\n" + ("word " * 25_000)  # ~125 017 chars
    assert len(long_markdown) > 100_000

    resp = client.post(
        "/library/articles",
        json={"markdown": long_markdown, "title": "Long Article"},
    )
    assert resp.status_code == 201
    article_id = resp.json()["id"]

    # Fetch detail to verify truncation
    get_resp = client.get(f"/library/articles/{article_id}")
    assert get_resp.status_code == 200
    detail = get_resp.json()

    assert len(detail["markdown"]) == 100_000
    assert detail["source_meta"].get("truncated") is True


def test_explain_empty_text(article_id):
    """POST /library/articles/{id}/explain with text='' → 400."""
    resp = client.post(
        f"/library/articles/{article_id}/explain",
        json={"text": "", "kind": "word"},
    )
    assert resp.status_code == 400


def test_stream_explain_empty_text(article_id):
    """POST /library/articles/{id}/explain/stream with text='' → 400."""
    resp = client.post(
        f"/library/articles/{article_id}/explain/stream",
        json={"text": ""},
    )
    assert resp.status_code == 400


def test_phonetic_empty_text(article_id):
    """POST /library/articles/{id}/explain/phonetic with text='' → 400."""
    resp = client.post(
        f"/library/articles/{article_id}/explain/phonetic",
        json={"text": ""},
    )
    assert resp.status_code == 400


def test_explain_with_stub_returns_backfilled_vocab(article_id, stub_explain):
    """explain endpoint backfills explanation_json in vocabulary."""
    text = "backfill-word"

    explain_resp = client.post(
        f"/library/articles/{article_id}/explain",
        json={"text": text, "kind": "word"},
    )
    assert explain_resp.status_code == 200

    from app.services import vocab_service as vs
    items = vs.list_items(user_id=USER, source_type="library", source_ref=str(article_id))
    assert len(items) == 1
    item = items[0]
    assert item["source_text"] == text
    assert item["explanation_json"] is not None
    parsed = json.loads(item["explanation_json"])
    assert parsed["meaning"] == f"stub-{text}"


def test_stream_explain_collects_and_backfills(article_id, monkeypatch):
    """stream endpoint collects fields and backfills vocab."""
    import app.routers.library as lr

    async def fake_stream(text, user_id, force=False):
        yield '{"field":"meaning","value":"test meaning"}'
        yield '{"_done":true,"explanation":{"meaning":"test meaning"},"cefr_level":"B1"}'

    monkeypatch.setattr(lr, "stream_sentence_explanation", fake_stream)

    text = "stream backfill sentence"

    stream_resp = client.post(
        f"/library/articles/{article_id}/explain/stream",
        json={"text": text, "item_type": "sentence"},
    )
    assert stream_resp.status_code == 200

    from app.services import vocab_service as vs
    items = vs.list_items(user_id=USER, source_type="library", source_ref=str(article_id))
    assert len(items) >= 1
    match = next((i for i in items if i["source_text"] == text), None)
    assert match is not None
    assert match["source_type"] == "library"
    assert match["source_ref"] == str(article_id)
    # explanation_json should be backfilled from the stream
    assert match["explanation_json"] is not None
    parsed = json.loads(match["explanation_json"])
    assert parsed.get("meaning") == "test meaning"


def test_refetch_url_article_success():
    """POST /library/articles/{id}/refetch for URL article → 200 with updated markdown."""
    original_md = "# Original\n\nOriginal content."
    updated_md = "# Updated\n\nFresh content after refetch."

    with patch("app.services.library_service._extract_from_url") as mock_extract:
        mock_extract.return_value = (
            original_md,
            {"title": "Original", "site_name": "example.com", "author": None},
        )
        resp = client.post(
            "/library/articles",
            json={"url": "https://example.com/refetch-smoke"},
        )

    assert resp.status_code == 201
    article_id = resp.json()["id"]

    with patch("app.services.library_service._extract_from_url") as mock_extract:
        mock_extract.return_value = (
            updated_md,
            {"title": "Updated", "site_name": "example.com", "author": None},
        )
        refetch_resp = client.post(f"/library/articles/{article_id}/refetch")

    assert refetch_resp.status_code == 200
    data = refetch_resp.json()
    assert "Fresh content after refetch" in data["markdown"]
    assert data["id"] == article_id


def test_vocab_not_deleted_on_article_delete():
    """Delete article → vocab items with source_type='library' still exist."""
    resp = client.post(
        "/library/articles",
        json={"markdown": "# Vocab Persist\n\nContent.", "title": "Vocab Persist"},
    )
    assert resp.status_code == 201
    article_id = resp.json()["id"]

    # Add a vocab item tied to this article
    from app.services import vocab_service as vs
    vs.save_item(
        user_id=USER,
        source_text="persist word",
        translated_text="持久化词",
        direction="en2zh",
        item_type="word",
        source_type="library",
        source_ref=str(article_id),
    )

    # Soft-delete the article
    del_resp = client.delete(f"/library/articles/{article_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True

    # Article is gone from list
    list_resp = client.get("/library/articles")
    assert list_resp.status_code == 200
    ids = [a["id"] for a in list_resp.json()["articles"]]
    assert article_id not in ids

    # Vocab item still exists — not cascade-deleted
    items = vs.list_items(user_id=USER, source_type="library", source_ref=str(article_id))
    assert len(items) == 1
    assert items[0]["source_text"] == "persist word"
