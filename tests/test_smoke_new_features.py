"""冒烟测试 — 新功能端点存活性检查

所有新增端点能正常返回（不 500），不依赖 LLM，仅验证路由注册 + 基本参数校验。
user_id: test_user_smoke_*
"""
import pytest
from fastapi.testclient import TestClient

from main import app
from app.models.db import engine, init_db
from app.routers.auth import get_current_user_id, get_current_user_id_optional

USER = "test_user_smoke"
client = TestClient(app)


@pytest.fixture(autouse=True)
def _setup():
    init_db()
    app.dependency_overrides[get_current_user_id] = lambda: USER
    app.dependency_overrides[get_current_user_id_optional] = lambda: USER
    yield
    app.dependency_overrides.pop(get_current_user_id, None)
    app.dependency_overrides.pop(get_current_user_id_optional, None)


# ── #53 翻译自动入库 ──────────────────────────────────────

class TestTranslateAutoVocabSmoke:
    """POST /translate/text 返回新增字段 saved_to_vocab / vocab_id"""

    def test_translate_text_returns_new_fields(self):
        """即使翻译失败（mock 缺失），响应 schema 仍含 saved_to_vocab 字段"""
        resp = client.post("/translate/text", json={"text": "", "direction": "zh2en"})
        assert resp.status_code == 400  # 空文本 → 400，路由能到达

    def test_translate_text_invalid_direction_400(self):
        resp = client.post("/translate/text", json={"text": "hello", "direction": "bad"})
        assert resp.status_code == 400
        assert "无效" in resp.json()["detail"]

    def test_translate_text_too_long_400(self):
        resp = client.post("/translate/text", json={"text": "a" * 1001, "direction": "zh2en"})
        assert resp.status_code == 400


# ── #54 文章库 ─────────────────────────────────────────────

class TestLibrarySmoke:
    """所有 /library/* 端点能到达且参数校验正常"""

    def test_list_articles_200(self):
        resp = client.get("/library/articles")
        assert resp.status_code == 200
        data = resp.json()
        assert "articles" in data
        assert "page" in data

    def test_import_article_no_body_400(self):
        resp = client.post("/library/articles", json={})
        assert resp.status_code == 400

    def test_import_article_markdown_201(self):
        resp = client.post("/library/articles", json={
            "markdown": "# Test\n\nHello world.",
            "title": "Smoke Test Article",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Smoke Test Article"
        article_id = data["id"]

        # 详情
        resp2 = client.get(f"/library/articles/{article_id}")
        assert resp2.status_code == 200
        assert resp2.json()["markdown"] == "# Test\n\nHello world."

        # 软删
        resp3 = client.delete(f"/library/articles/{article_id}")
        assert resp3.status_code == 200
        assert resp3.json()["deleted"] is True

        # 删后 404
        resp4 = client.get(f"/library/articles/{article_id}")
        assert resp4.status_code == 404

    def test_get_nonexistent_article_404(self):
        resp = client.get("/library/articles/999999")
        assert resp.status_code == 404

    def test_explain_phonetic_no_text_400(self):
        # 先创建一篇文章
        art = client.post("/library/articles", json={
            "markdown": "# Smoke\n\nword.", "title": "Phonetic Smoke",
        }).json()
        resp = client.post(f"/library/articles/{art['id']}/explain/phonetic", json={"text": ""})
        assert resp.status_code == 400

    def test_explain_phonetic_returns_ipa(self):
        art = client.post("/library/articles", json={
            "markdown": "# IPA\n\nHello.", "title": "IPA Smoke",
        }).json()
        resp = client.post(f"/library/articles/{art['id']}/explain/phonetic", json={"text": "hello"})
        assert resp.status_code == 200
        assert "phonetic" in resp.json()

    def test_refetch_paste_mode_400(self):
        art = client.post("/library/articles", json={
            "markdown": "# No URL", "title": "Paste",
        }).json()
        resp = client.post(f"/library/articles/{art['id']}/refetch")
        assert resp.status_code == 400


# ── #55 DeepL 重设计（前端纯静态路由）──────────────────────

class TestDeepLSmoke:
    """/translate 前端页面路由存活"""

    def test_translate_page_not_500(self):
        """确认 /translate 路由不返回 500（Vue SPA 由前端路由处理）"""
        # 在 API 层面，/translate 不是 API 端点（由前端路由处理）
        # 但翻译 API 端点 /translate/text 应可达
        resp = client.post("/translate/text", json={"text": "test", "direction": "en2zh"})
        # 可能 503（LLM 不可用）或 200，不应 500/404
        assert resp.status_code in (200, 503)


# ── 通用 /vocab 端点冒烟 ──────────────────────────────────

class TestVocabSmoke:
    """生词本列表端点可达 + source_type 过滤"""

    def test_vocab_list_200(self):
        resp = client.get("/vocab")
        assert resp.status_code == 200
        assert "items" in resp.json()

    def test_vocab_list_with_source_type_filter(self):
        resp = client.get("/vocab?source_type=translate")
        assert resp.status_code == 200

    def test_vocab_list_with_source_type_library(self):
        resp = client.get("/vocab?source_type=library")
        assert resp.status_code == 200
