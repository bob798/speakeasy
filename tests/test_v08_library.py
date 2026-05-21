"""Library module tests — V0.8

Tests cover:
  - test_import_article_markdown: paste mode creates article
  - test_import_article_url_dedup: same URL twice returns existing
  - test_list_articles: pagination, only active
  - test_delete_article_soft: soft delete, vocab not affected
  - test_explain_creates_vocab: explain endpoint auto-saves to vocab with source_type='library'
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from main import app
from app.models.db import engine, LibraryArticle, Vocabulary, init_db
from app.routers.auth import get_current_user_id, get_current_user_id_optional

USER = "test_user_v08_library_task1"
client = TestClient(app)


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
            LibraryArticle.user_id.like("test_user_v08_library_%")
        ).delete()
        s.query(Vocabulary).filter(
            Vocabulary.user_id.like("test_user_v08_library_%")
        ).delete()
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(LibraryArticle).filter(
            LibraryArticle.user_id.like("test_user_v08_library_%")
        ).delete()
        s.query(Vocabulary).filter(
            Vocabulary.user_id.like("test_user_v08_library_%")
        ).delete()
        s.commit()


@pytest.fixture
def stub_explain(monkeypatch):
    """Stub out LLM calls to avoid real API requests."""
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


# ── Tests ──────────────────────────────────────────────────

def test_import_article_markdown():
    """Paste mode: creates article with correct fields."""
    resp = client.post(
        "/library/articles",
        json={
            "markdown": "# Hello World\n\nThis is a test article with some words.",
            "title": "Hello World",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Hello World"
    assert data["status"] == "active"
    assert data["word_count"] > 0
    assert data["source_url"] is None
    assert data["existing"] is False


def test_import_article_markdown_title_from_heading():
    """Paste mode: title extracted from first # heading when not provided."""
    resp = client.post(
        "/library/articles",
        json={
            "markdown": "# Extracted Title\n\nContent here.",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Extracted Title"


def test_import_article_url_dedup():
    """Same URL imported twice returns existing article with existing=True."""
    # First import using mock trafilatura
    fake_md = "# Spec Driven Development\n\nSome content about spec driven development."
    fake_meta = {"title": "Spec Driven Development", "site_name": "example.com", "author": None}

    with patch("app.services.library_service._extract_from_url") as mock_extract:
        mock_extract.return_value = (fake_md, fake_meta)
        resp1 = client.post(
            "/library/articles",
            json={"url": "https://example.com/spec-driven"},
        )

    assert resp1.status_code == 201
    data1 = resp1.json()
    assert data1["existing"] is False
    article_id = data1["id"]

    # Second import of same URL
    with patch("app.services.library_service._extract_from_url") as mock_extract:
        mock_extract.return_value = (fake_md, fake_meta)
        resp2 = client.post(
            "/library/articles",
            json={"url": "https://example.com/spec-driven"},
        )

    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["existing"] is True
    assert data2["id"] == article_id


def test_import_article_url_fetch_failed():
    """Fetch failure returns 400 with fetch_failed error."""
    with patch("app.services.library_service._extract_from_url") as mock_extract:
        mock_extract.side_effect = ValueError("fetch_failed")
        resp = client.post(
            "/library/articles",
            json={"url": "https://example.com/fail"},
        )

    assert resp.status_code == 400
    data = resp.json()
    assert data["detail"]["error"] == "fetch_failed"
    assert "粘贴正文模式" in data["detail"]["hint"]


def test_list_articles():
    """List returns only active articles with pagination."""
    # Insert 3 articles
    ids = []
    for i in range(3):
        resp = client.post(
            "/library/articles",
            json={
                "markdown": f"# Article {i}\n\nContent {i}.",
                "title": f"Article {i}",
            },
        )
        assert resp.status_code == 201
        ids.append(resp.json()["id"])

    # All articles are listed
    resp = client.get("/library/articles?page=1&page_size=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert len(data["articles"]) == 3

    # Pagination works
    resp = client.get("/library/articles?page=1&page_size=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["articles"]) == 2

    resp2 = client.get("/library/articles?page=2&page_size=2")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert len(data2["articles"]) == 1

    # All returned articles belong to current user
    all_ids = [a["id"] for a in data["articles"]] + [a["id"] for a in data2["articles"]]
    for aid in ids:
        assert aid in all_ids


def test_list_excludes_deleted():
    """Deleted articles do not appear in list."""
    resp = client.post(
        "/library/articles",
        json={"markdown": "# Deleted Article\n\nContent.", "title": "Deleted Article"},
    )
    assert resp.status_code == 201
    article_id = resp.json()["id"]

    # Delete it
    del_resp = client.delete(f"/library/articles/{article_id}")
    assert del_resp.status_code == 200

    # List should be empty
    list_resp = client.get("/library/articles")
    assert list_resp.status_code == 200
    assert len(list_resp.json()["articles"]) == 0


def test_delete_article_soft():
    """Soft delete: article disappears from list but vocab remains."""
    # Create article
    resp = client.post(
        "/library/articles",
        json={"markdown": "# Test\n\nSome words here.", "title": "Test"},
    )
    assert resp.status_code == 201
    article_id = resp.json()["id"]

    # Manually add a vocab item tied to this article
    from app.services import vocab_service
    vocab_service.save_item(
        user_id=USER,
        source_text="some words",
        translated_text="一些词",
        direction="en2zh",
        item_type="phrase",
        source_type="library",
        source_ref=str(article_id),
    )

    # Soft delete article
    del_resp = client.delete(f"/library/articles/{article_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True

    # Article gone from list
    list_resp = client.get("/library/articles")
    assert list_resp.status_code == 200
    articles = list_resp.json()["articles"]
    ids = [a["id"] for a in articles]
    assert article_id not in ids

    # Vocab still exists (not cascade deleted)
    from app.services import vocab_service as vs
    items = vs.list_items(user_id=USER, source_type="library", source_ref=str(article_id))
    assert len(items) == 1
    assert items[0]["source_text"] == "some words"


def test_get_article_detail():
    """GET /library/articles/{id} returns full markdown."""
    resp = client.post(
        "/library/articles",
        json={"markdown": "# Detail Test\n\nFull content here.", "title": "Detail Test"},
    )
    assert resp.status_code == 201
    article_id = resp.json()["id"]

    get_resp = client.get(f"/library/articles/{article_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == article_id
    assert "Full content here" in data["markdown"]


def test_get_article_not_found():
    """GET on non-existent article returns 404."""
    resp = client.get("/library/articles/999999")
    assert resp.status_code == 404


def test_explain_creates_vocab(stub_explain):
    """explain endpoint auto-saves to vocab with source_type='library'."""
    # Create article
    resp = client.post(
        "/library/articles",
        json={"markdown": "# Explain Test\n\nSome content.", "title": "Explain Test"},
    )
    assert resp.status_code == 201
    article_id = resp.json()["id"]

    # Call explain
    explain_resp = client.post(
        f"/library/articles/{article_id}/explain",
        json={"text": "spec-driven", "kind": "word"},
    )
    assert explain_resp.status_code == 200

    # Check vocab was created
    from app.services import vocab_service as vs
    items = vs.list_items(user_id=USER, source_type="library", source_ref=str(article_id))
    assert len(items) == 1
    item = items[0]
    assert item["source_text"] == "spec-driven"
    assert item["source_type"] == "library"
    assert item["source_ref"] == str(article_id)
    # explanation_json should be backfilled
    assert item["explanation_json"] is not None
    parsed = json.loads(item["explanation_json"])
    assert parsed["meaning"] == "stub-spec-driven"


def test_phonetic_creates_vocab():
    """phonetic endpoint saves placeholder to vocab."""
    resp = client.post(
        "/library/articles",
        json={"markdown": "# IPA Test\n\nContent.", "title": "IPA Test"},
    )
    assert resp.status_code == 201
    article_id = resp.json()["id"]

    phonetic_resp = client.post(
        f"/library/articles/{article_id}/explain/phonetic",
        json={"text": "development"},
    )
    assert phonetic_resp.status_code == 200

    # Vocab placeholder should exist
    from app.services import vocab_service as vs
    items = vs.list_items(user_id=USER, source_type="library", source_ref=str(article_id))
    assert len(items) == 1
    assert items[0]["source_text"] == "development"
    assert items[0]["source_type"] == "library"


def test_refetch_paste_mode_returns_400():
    """Refetch on paste-mode article (no URL) returns 400."""
    resp = client.post(
        "/library/articles",
        json={"markdown": "# Paste\n\nContent.", "title": "Paste"},
    )
    assert resp.status_code == 201
    article_id = resp.json()["id"]

    refetch_resp = client.post(f"/library/articles/{article_id}/refetch")
    assert refetch_resp.status_code == 400


def test_vocab_count_in_list():
    """Article list includes vocab_count per article."""
    resp = client.post(
        "/library/articles",
        json={"markdown": "# VocabCount\n\nWords.", "title": "VocabCount"},
    )
    assert resp.status_code == 201
    article_id = resp.json()["id"]

    # Add 2 vocab items
    from app.services import vocab_service as vs
    vs.save_item(
        user_id=USER, source_text="word1", translated_text="词1",
        direction="en2zh", item_type="word", source_type="library",
        source_ref=str(article_id),
    )
    vs.save_item(
        user_id=USER, source_text="word2", translated_text="词2",
        direction="en2zh", item_type="word", source_type="library",
        source_ref=str(article_id),
    )

    list_resp = client.get("/library/articles")
    assert list_resp.status_code == 200
    articles = list_resp.json()["articles"]
    assert len(articles) == 1
    assert articles[0]["vocab_count"] == 2


def test_explain_save_item_failure_degrades(stub_explain, monkeypatch):
    """Vocab save failure is swallowed — explain still returns 200."""
    from app.services import vocab_service as vs

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated DB error")

    monkeypatch.setattr(vs, "save_item", _boom)
    monkeypatch.setattr(vs, "update_explanation", _boom)

    # Create article
    resp = client.post(
        "/library/articles",
        json={"markdown": "# Degrade Test\n\nContent.", "title": "Degrade Test"},
    )
    assert resp.status_code == 201
    article_id = resp.json()["id"]

    # Even though vocab save raises, explain should still succeed
    explain_resp = client.post(
        f"/library/articles/{article_id}/explain",
        json={"text": "degrade", "kind": "word"},
    )
    assert explain_resp.status_code == 200
    data = explain_resp.json()
    assert "explanation" in data


def test_truncation_at_100k():
    """Paste-mode article with markdown >100k chars is truncated to 100k and source_meta has truncated=true."""
    long_markdown = "# Long Article\n\n" + ("word " * 25_000)  # ~125 001 chars
    assert len(long_markdown) > 100_000

    resp = client.post(
        "/library/articles",
        json={"markdown": long_markdown, "title": "Long Article"},
    )
    assert resp.status_code == 201
    data = resp.json()
    article_id = data["id"]

    # Fetch detail to get full markdown
    get_resp = client.get(f"/library/articles/{article_id}")
    assert get_resp.status_code == 200
    detail = get_resp.json()

    assert len(detail["markdown"]) == 100_000
    assert detail["source_meta"].get("truncated") is True


def test_refetch_url_article():
    """Refetch on a URL article updates its markdown with newly extracted content."""
    original_md = "# Original\n\nOriginal content."
    updated_md = "# Updated\n\nFresh content after refetch."
    fake_meta = {"title": "Updated", "site_name": "example.com", "author": None}

    with patch("app.services.library_service._extract_from_url") as mock_extract:
        mock_extract.return_value = (original_md, {"title": "Original", "site_name": "example.com", "author": None})
        resp = client.post(
            "/library/articles",
            json={"url": "https://example.com/refetch-test"},
        )

    assert resp.status_code == 201
    article_id = resp.json()["id"]

    with patch("app.services.library_service._extract_from_url") as mock_extract:
        mock_extract.return_value = (updated_md, fake_meta)
        refetch_resp = client.post(f"/library/articles/{article_id}/refetch")

    assert refetch_resp.status_code == 200
    data = refetch_resp.json()
    assert "Fresh content after refetch" in data["markdown"]


def test_explain_stream_creates_vocab():
    """Stream explain endpoint creates a vocabulary record with source_type='library'."""
    import asyncio
    import app.routers.library as lr

    # Create article
    resp = client.post(
        "/library/articles",
        json={"markdown": "# Stream Test\n\nSome sentence to explain.", "title": "Stream Test"},
    )
    assert resp.status_code == 201
    article_id = resp.json()["id"]

    text = "Some sentence to explain"

    async def _fake_stream(text_arg, user_id, force=False):
        explanation = {"meaning": "stub meaning", "phonetic": "stʌb"}
        yield json.dumps({"_cached": True, "cefr_level": "B1", "explanation": explanation})

    with patch.object(lr, "stream_sentence_explanation", _fake_stream):
        stream_resp = client.post(
            f"/library/articles/{article_id}/explain/stream",
            json={"text": text, "item_type": "sentence"},
        )

    assert stream_resp.status_code == 200

    # Vocab record should exist (either from placeholder or backfill)
    from app.services import vocab_service as vs
    items = vs.list_items(user_id=USER, source_type="library", source_ref=str(article_id))
    assert len(items) >= 1
    assert items[0]["source_type"] == "library"
    assert items[0]["source_ref"] == str(article_id)
