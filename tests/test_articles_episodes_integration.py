"""Integration tests for /articles/episodes/* routes.

Covers:
  - GET /articles/episodes (list, series filter)
  - GET /articles/episodes/{slug} (detail, 404)
  - POST /articles/episodes/{slug}/start (create card, 404)
  - POST /articles/episodes/{slug}/rate (success, bad rating)
  - GET /articles/due
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from main import app
from app.models.db import engine, ArticleEpisode, BbcArticleCard, BbcArticleQuestion
from app.routers.auth import get_current_user_id

USER = "test_user_episodes_integ"
SLUG = "test-ep-integ"


# ── Auth override ──────────────────────────────────────────────────────────────

app.dependency_overrides[get_current_user_id] = lambda: USER


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ── Cleanup fixture ────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset():
    """Wipe test rows before and after each test."""
    def _clean():
        with OrmSession(engine) as s:
            s.query(BbcArticleCard).filter_by(user_id=USER).delete()
            s.query(BbcArticleQuestion).filter_by(slug=SLUG).delete()
            s.query(ArticleEpisode).filter_by(slug=SLUG).delete()
            s.commit()

    _clean()
    with OrmSession(engine) as s:
        s.add(ArticleEpisode(
            series="bbc_eaw",
            slug=SLUG,
            url="https://example.com/test",
            title="Test Episode",
            description="Test",
            transcript_json='[{"speaker":"A","text":"Hello world."}]',
            phrases_json='["hello"]',
            transcript_turns=1,
        ))
        s.commit()

    yield

    _clean()


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_list_episodes_returns_series_field(client):
    resp = client.get("/articles/episodes")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    matching = [item for item in data["items"] if item["slug"] == SLUG]
    assert len(matching) == 1
    assert matching[0]["series"] == "bbc_eaw"


def test_list_episodes_filter_by_series(client):
    resp = client.get("/articles/episodes?series=bbc_eaw")
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["series"] == "bbc_eaw" for item in data["items"])
    slugs = [item["slug"] for item in data["items"]]
    assert SLUG in slugs


def test_list_episodes_filter_by_series_no_match(client):
    resp = client.get("/articles/episodes?series=nonexistent_series")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 0
    assert data["items"] == []


def test_get_episode_returns_series_and_source_type(client):
    resp = client.get(f"/articles/episodes/{SLUG}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["slug"] == SLUG
    assert data["series"] == "bbc_eaw"
    assert data["source_type"] == "article"
    assert data["title"] == "Test Episode"
    assert isinstance(data["segments"], list)
    assert len(data["segments"]) == 1
    assert data["segments"][0]["content"] == "Hello world."


def test_get_episode_not_found(client):
    resp = client.get("/articles/episodes/nonexistent-slug-xyz")
    assert resp.status_code == 404


def test_start_studying_creates_card(client):
    resp = client.post(f"/articles/episodes/{SLUG}/start")
    assert resp.status_code == 201
    data = resp.json()
    assert data["slug"] == SLUG
    assert data["title"] == "Test Episode"
    assert data["due"] is not None
    assert isinstance(data["id"], int)


def test_start_studying_not_found(client):
    resp = client.post("/articles/episodes/nonexistent-slug-xyz/start")
    assert resp.status_code == 404


def test_rate_card(client):
    # First create the card
    start_resp = client.post(f"/articles/episodes/{SLUG}/start")
    assert start_resp.status_code == 201

    # Then rate it
    resp = client.post(
        f"/articles/episodes/{SLUG}/rate",
        json={"rating": "good"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["slug"] == SLUG
    assert data["review_count"] == 1
    assert data["last_reviewed_at"] is not None
    assert data["due"] is not None


def test_rate_invalid_rating(client):
    # Create card first so the route reaches the rating validation
    start_resp = client.post(f"/articles/episodes/{SLUG}/start")
    assert start_resp.status_code == 201

    resp = client.post(
        f"/articles/episodes/{SLUG}/rate",
        json={"rating": "meh"},
    )
    assert resp.status_code == 400


def test_due_returns_list(client):
    resp = client.get("/articles/due")
    assert resp.status_code == 200
    data = resp.json()
    # /articles/due is served by the articles router (prefix="/articles", route="/due")
    # which returns {"cards": [...], "count": N}
    assert "cards" in data
    assert "count" in data
    assert isinstance(data["cards"], list)
    assert data["count"] == len(data["cards"])
