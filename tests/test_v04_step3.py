"""
V0.4 Step 3 — 路由可达性 + 导航链接
"""
import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def test_practice_page_returns_200(client):
    # V0.8: /practice 迁到 /legacy/practice（Pass 3 B3）
    resp = client.get("/legacy/practice")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


def test_index_has_practice_link(client):
    resp = client.get("/legacy/")
    assert resp.status_code == 200
    assert 'href="/practice"' in resp.text


def test_subtitles_manual_text_via_route(client):
    resp = client.post("/practice/subtitles", json={"text": "line1\nline2"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["segments"]) == 2
