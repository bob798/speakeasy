"""集成测试 — 跨服务端到端流程验证

不 mock 内部 service，只 mock 外部 LLM。验证：
  - 翻译 → 占位 → 回填 → 生词本可查 的完整链路
  - 文章导入 → 解读 → 生词本入库 → 列表可见 的完整链路
  - 跨 source_type 数据隔离
user_id: test_user_integration_*
"""
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.orm import Session as OrmSession

from main import app
from app.models.db import engine, init_db, Vocabulary, LibraryArticle
from app.routers.auth import get_current_user_id, get_current_user_id_optional

USER = "test_user_integration_new"


@pytest.fixture(autouse=True)
def setup():
    init_db()
    app.dependency_overrides[get_current_user_id] = lambda: USER
    app.dependency_overrides[get_current_user_id_optional] = lambda: USER
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter(Vocabulary.user_id == USER).delete()
        s.query(LibraryArticle).filter(LibraryArticle.user_id == USER).delete()
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter(Vocabulary.user_id == USER).delete()
        s.query(LibraryArticle).filter(LibraryArticle.user_id == USER).delete()
        s.commit()
    app.dependency_overrides.pop(get_current_user_id, None)
    app.dependency_overrides.pop(get_current_user_id_optional, None)


def _get_vocab_items(source_type=None):
    with OrmSession(engine) as s:
        q = s.query(Vocabulary).filter_by(user_id=USER, status="active")
        if source_type:
            q = q.filter_by(source_type=source_type)
        return [
            {"id": v.id, "source_text": v.source_text, "translated_text": v.translated_text,
             "source_type": v.source_type, "source_ref": v.source_ref,
             "item_type": v.item_type, "explanation_json": v.explanation_json}
            for v in q.all()
        ]


# ── 翻译自动入库完整链路 ──────────────────────────────────

class TestTranslateAutoVocabIntegration:
    """翻译 → 占位 → LLM 返回 → 回填 → /vocab 可查"""

    @pytest.mark.asyncio
    async def test_translate_then_vocab_visible(self):
        """翻译一段文本后，通过 /vocab 端点能查到对应条目"""
        with patch("app.routers.translate.translate_text",
                   new_callable=AsyncMock, return_value="Good morning"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
                resp = await c.post("/translate/text", json={
                    "text": "早上好", "direction": "zh2en",
                })

        assert resp.status_code == 200
        data = resp.json()
        assert data["saved_to_vocab"] is True
        vid = data["vocab_id"]

        # 通过 /vocab 端点查询（集成层面，非直查 DB）
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            resp2 = await c.get("/vocab?source_type=translate")

        items = resp2.json()["items"]
        match = [i for i in items if i["id"] == vid]
        assert len(match) == 1
        assert match[0]["source_text"] == "早上好"
        assert match[0]["translated_text"] == "Good morning"
        assert match[0]["source_type"] == "translate"
        assert match[0]["item_type"] == "sentence"

    @pytest.mark.asyncio
    async def test_translate_twice_same_text_idempotent_in_vocab(self):
        """翻译同一文本两次，生词本只有一条记录，translated_text 为最新"""
        for expected in ["v1", "v2"]:
            with patch("app.routers.translate.translate_text",
                       new_callable=AsyncMock, return_value=expected):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
                    await c.post("/translate/text", json={
                        "text": "重复测试", "direction": "zh2en",
                    })

        items = _get_vocab_items(source_type="translate")
        matching = [i for i in items if i["source_text"] == "重复测试"]
        assert len(matching) == 1
        assert matching[0]["translated_text"] == "v2"


# ── 文章库完整链路 ────────────────────────────────────────

class TestLibraryIntegration:
    """导入 → 解读 → vocab 入库 → vocab 列表可见"""

    @pytest.mark.asyncio
    async def test_import_explain_vocab_flow(self):
        """导入文章 → 解读单词 → 检查 vocab 有 source_type=library 条目"""
        # 1. 导入文章
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r1 = await c.post("/library/articles", json={
                "markdown": "# Integration Test\n\nThe quick brown fox jumps.",
                "title": "Integration Article",
            })
        assert r1.status_code == 201
        article_id = r1.json()["id"]

        # 2. 解读单词（mock LLM）
        mock_result = {
            "explanation": {
                "phonetic": "/kwɪk/",
                "meaning": "快的",
                "meanings": ["快速的", "敏捷的"],
                "example": "She gave a quick answer.",
            }
        }
        with patch("app.routers.library.explain_text",
                   new_callable=AsyncMock, return_value=mock_result):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
                r2 = await c.post(f"/library/articles/{article_id}/explain", json={
                    "text": "quick", "kind": "word", "context": "The quick brown fox",
                })
        assert r2.status_code == 200

        # 3. 检查 vocab — source_type=library 有条目
        items = _get_vocab_items(source_type="library")
        match = [i for i in items if i["source_text"] == "quick"]
        assert len(match) == 1
        assert match[0]["source_ref"] == str(article_id)
        assert match[0]["item_type"] == "word"
        # explanation_json 已回填
        exp = json.loads(match[0]["explanation_json"])
        assert exp["phonetic"] == "/kwɪk/"
        assert exp["meaning"] == "快的"

    @pytest.mark.asyncio
    async def test_library_phonetic_creates_vocab_entry(self):
        """phonetic 端点也会创建 vocab 占位条目"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r1 = await c.post("/library/articles", json={
                "markdown": "# Phonetic\n\nHello world.", "title": "Phonetic Test",
            })
        article_id = r1.json()["id"]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r2 = await c.post(f"/library/articles/{article_id}/explain/phonetic", json={
                "text": "hello",
            })
        assert r2.status_code == 200
        assert "phonetic" in r2.json()

        items = _get_vocab_items(source_type="library")
        match = [i for i in items if i["source_text"] == "hello"]
        assert len(match) == 1
        assert match[0]["source_ref"] == str(article_id)

    @pytest.mark.asyncio
    async def test_delete_article_does_not_cascade_vocab(self):
        """软删文章后，vocab 条目仍存在（不级联）"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r1 = await c.post("/library/articles", json={
                "markdown": "# Cascade\n\nTest cascade.", "title": "Cascade",
            })
        article_id = r1.json()["id"]

        # 先通过 phonetic 创建 vocab 条目
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            await c.post(f"/library/articles/{article_id}/explain/phonetic", json={
                "text": "cascade",
            })

        # 删文章
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            await c.delete(f"/library/articles/{article_id}")

        # vocab 仍在
        items = _get_vocab_items(source_type="library")
        assert any(i["source_text"] == "cascade" for i in items)


# ── 跨 source_type 数据隔离 ──────────────────────────────

class TestCrossSourceTypeIsolation:
    """不同来源的 vocab 条目互不干扰"""

    @pytest.mark.asyncio
    async def test_translate_and_library_vocab_isolated(self):
        """同一用户翻译入库和文章解读入库分别在不同 source_type 下"""
        # 翻译
        with patch("app.routers.translate.translate_text",
                   new_callable=AsyncMock, return_value="Hello"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
                await c.post("/translate/text", json={
                    "text": "你好", "direction": "zh2en",
                })

        # 文章
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r1 = await c.post("/library/articles", json={
                "markdown": "# Isolation\n\nfoo bar.", "title": "Iso",
            })
        article_id = r1.json()["id"]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            await c.post(f"/library/articles/{article_id}/explain/phonetic", json={
                "text": "foo",
            })

        # 分别查询
        translate_items = _get_vocab_items(source_type="translate")
        library_items = _get_vocab_items(source_type="library")

        assert len(translate_items) >= 1
        assert all(i["source_type"] == "translate" for i in translate_items)

        assert len(library_items) >= 1
        assert all(i["source_type"] == "library" for i in library_items)

        # translate 里没有 library 的，反之亦然
        translate_texts = {i["source_text"] for i in translate_items}
        library_texts = {i["source_text"] for i in library_items}
        assert "foo" not in translate_texts
        assert "你好" not in library_texts
