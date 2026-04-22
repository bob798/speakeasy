"""
V0.5 Step 2 — translate_service 翻译服务 + CRUD
user_id: test_user_v05_step2
"""
import json

import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, Base, Vocabulary, TranslationCache
from app.services.translate_service import (
    translate_text,
    save_vocabulary,
    list_vocabulary,
    delete_vocabulary,
)

TEST_USER = "test_user_v05_step2"


def _mock_translations(*lines: str) -> str:
    """生成符合 batch 协议的 JSON 返回"""
    return json.dumps({"translations": list(lines)}, ensure_ascii=False)


@pytest.fixture(autouse=True)
def cleanup():
    Base.metadata.create_all(engine)
    # 清空可能影响缓存命中的旧缓存行
    with OrmSession(engine) as s:
        s.query(TranslationCache).delete()
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter_by(user_id=TEST_USER).delete()
        s.query(TranslationCache).delete()
        s.commit()


# ── translate_text ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_translate_zh2en_basic():
    with patch("app.services.translate_service.get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(
            return_value=_mock_translations("I have worked on recommendation systems")
        )
        mock_get.return_value = mock_client

        result = await translate_text("我做过推荐系统", "zh2en")
        assert "recommendation" in result.lower()
        # 验证 messages 包含 zh2en batch system prompt
        call_args = mock_client.complete.call_args[0][0]
        assert any("system" == m["role"] for m in call_args)
        assert any("Chinese" in m["content"] for m in call_args if m["role"] == "system")


@pytest.mark.asyncio
async def test_translate_en2zh_basic():
    with patch("app.services.translate_service.get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=_mock_translations("我喜欢阅读"))
        mock_get.return_value = mock_client

        result = await translate_text("I love reading", "en2zh")
        assert any("\u4e00" <= ch <= "\u9fff" for ch in result)


@pytest.mark.asyncio
async def test_translate_empty_input_raises():
    with pytest.raises(ValueError, match="不能为空"):
        await translate_text("", "zh2en")

    with pytest.raises(ValueError, match="不能为空"):
        await translate_text("   ", "zh2en")


@pytest.mark.asyncio
async def test_translate_invalid_direction():
    with pytest.raises(ValueError, match="无效的翻译方向"):
        await translate_text("hello", "jp2en")


@pytest.mark.asyncio
async def test_translate_mixed_input():
    """中英混合输入不报错，正常返回"""
    with patch("app.services.translate_service.get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(
            return_value=_mock_translations("I use Python to build recommendation systems")
        )
        mock_get.return_value = mock_client

        result = await translate_text("我用 Python 做 recommendation", "zh2en")
        assert isinstance(result, str)
        assert len(result) > 0


@pytest.mark.asyncio
async def test_translate_long_input_over_1000_raises():
    """超 1000 字符应抛 ValueError"""
    long_text = "你好 " * 400  # > 1000 chars
    assert len(long_text) > 1000
    with pytest.raises(ValueError, match="1000"):
        await translate_text(long_text, "zh2en")


# ── CRUD ───────────────────────────────────────────────────

def test_save_vocabulary():
    item = save_vocabulary(
        user_id=TEST_USER,
        source_text="推荐系统",
        translated_text="recommendation system",
        direction="zh2en",
    )
    assert isinstance(item["id"], int) and item["id"] > 0
    assert item["user_id"] == TEST_USER
    assert item["source_text"] == "推荐系统"
    assert item["translated_text"] == "recommendation system"
    assert item["direction"] == "zh2en"
    assert item["status"] == "active"
    assert item["created_at"] is not None


def test_save_vocabulary_invalid_direction_raises():
    with pytest.raises(ValueError, match="无效的翻译方向"):
        save_vocabulary(
            user_id=TEST_USER,
            source_text="foo",
            translated_text="bar",
            direction="xx",
        )


def test_save_vocabulary_empty_source_raises():
    with pytest.raises(ValueError, match="源文本不能为空"):
        save_vocabulary(
            user_id=TEST_USER,
            source_text="   ",
            translated_text="bar",
            direction="zh2en",
        )


def test_list_vocabulary_excludes_deleted():
    save_vocabulary(TEST_USER, "苹果", "apple", "zh2en")
    save_vocabulary(TEST_USER, "香蕉", "banana", "zh2en")
    item = save_vocabulary(TEST_USER, "橙子", "orange", "zh2en")

    # 软删除 橙子
    delete_vocabulary(item["id"], TEST_USER)

    items = list_vocabulary(TEST_USER)
    texts = [v["source_text"] for v in items]
    assert "苹果" in texts
    assert "香蕉" in texts
    assert "橙子" not in texts


def test_delete_vocabulary():
    item = save_vocabulary(TEST_USER, "删除测试", "delete test", "zh2en")
    vid = item["id"]

    result = delete_vocabulary(vid, TEST_USER)
    assert result is True

    # 已删除的条目不出现在列表中
    items = list_vocabulary(TEST_USER)
    assert all(v["id"] != vid for v in items)


def test_delete_vocabulary_nonexistent():
    result = delete_vocabulary(99999, TEST_USER)
    assert result is False


def test_list_vocabulary_pagination():
    for i in range(5):
        save_vocabulary(TEST_USER, f"词{i}", f"word{i}", "zh2en")

    page1 = list_vocabulary(TEST_USER, limit=3, offset=0)
    page2 = list_vocabulary(TEST_USER, limit=3, offset=3)

    assert len(page1) == 3
    assert len(page2) == 2
