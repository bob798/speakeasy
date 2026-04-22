"""
V0.5 翻译改造 — 按行拆分 + 缓存 + 批量 JSON 请求
user_id: test_user_v05_translate_batch
"""
import json

import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, Base, TranslationCache
from app.services.translate_service import translate_text


def _mock_translations(*lines: str) -> str:
    return json.dumps({"translations": list(lines)}, ensure_ascii=False)


@pytest.fixture(autouse=True)
def cleanup_cache():
    Base.metadata.create_all(engine)
    with OrmSession(engine) as s:
        s.query(TranslationCache).delete()
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(TranslationCache).delete()
        s.commit()


# ── 按行拆分 ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_multiline_each_line_translated():
    """多行输入：每行独立翻译，顺序保持"""
    with patch("app.services.translate_service.get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(
            return_value=_mock_translations("保持/仍然", "无与伦比的", "提示词塞入")
        )
        mock_get.return_value = mock_client

        src = "remain\nunmatched\nPrompt Stuffing"
        result = await translate_text(src, "en2zh")

        lines = result.split("\n")
        assert len(lines) == 3
        assert "保持" in lines[0]
        assert "无与伦比" in lines[1]
        assert "提示词塞入" in lines[2]


@pytest.mark.asyncio
async def test_batch_sends_single_llm_call():
    """多行应合并成一次 LLM 调用"""
    with patch("app.services.translate_service.get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(
            return_value=_mock_translations("A", "B", "C")
        )
        mock_get.return_value = mock_client

        await translate_text("中文A\n中文B\n中文C", "zh2en")
        assert mock_client.complete.await_count == 1

        # 验证 user payload 是 JSON 数组
        call_args = mock_client.complete.call_args[0][0]
        user_msg = [m for m in call_args if m["role"] == "user"][0]
        payload = json.loads(user_msg["content"])
        assert payload["lines"] == ["中文A", "中文B", "中文C"]


@pytest.mark.asyncio
async def test_empty_lines_preserved_not_sent_to_llm():
    """空行 / 纯标点行直接保留，不送 LLM"""
    with patch("app.services.translate_service.get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(
            return_value=_mock_translations("Hello", "World")
        )
        mock_get.return_value = mock_client

        src = "你好\n\n；；；\n世界"
        result = await translate_text(src, "zh2en")

        lines = result.split("\n")
        assert len(lines) == 4
        assert "Hello" in lines[0]
        assert lines[1] == ""
        assert lines[2] == "；；；"
        assert "World" in lines[3]

        # 只送了 2 行给 LLM
        call_args = mock_client.complete.call_args[0][0]
        user_msg = [m for m in call_args if m["role"] == "user"][0]
        payload = json.loads(user_msg["content"])
        assert payload["lines"] == ["你好", "世界"]


@pytest.mark.asyncio
async def test_output_count_mismatch_raises():
    """LLM 返回行数不对 → 抛 ValueError，触发 503 兜底"""
    with patch("app.services.translate_service.get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(
            return_value=_mock_translations("only one")
        )
        mock_get.return_value = mock_client

        with pytest.raises(ValueError, match="行数不匹配"):
            await translate_text("line1\nline2\nline3", "zh2en")


@pytest.mark.asyncio
async def test_code_fence_wrapping_tolerated():
    """LLM 误加 ```json ... ``` 代码块，应能解析"""
    with patch("app.services.translate_service.get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(
            return_value='```json\n{"translations":["hi"]}\n```'
        )
        mock_get.return_value = mock_client

        result = await translate_text("你好", "zh2en")
        assert "hi" in result


# ── 缓存命中 ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cache_hit_skips_llm():
    """第二次相同输入应命中缓存，不再调 LLM"""
    with patch("app.services.translate_service.get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(
            return_value=_mock_translations("Hello world")
        )
        mock_get.return_value = mock_client

        r1 = await translate_text("你好世界", "zh2en")
        r2 = await translate_text("你好世界", "zh2en")

        assert r1 == r2
        # 只调了一次 LLM
        assert mock_client.complete.await_count == 1


@pytest.mark.asyncio
async def test_cache_partial_hit_only_misses_sent():
    """3 行里有 2 行命中缓存 → LLM 只收到 1 行未命中"""
    with patch("app.services.translate_service.get_client") as mock_get:
        mock_client = AsyncMock()
        # 第一轮：送 3 行
        mock_client.complete = AsyncMock(
            return_value=_mock_translations("A", "B", "C")
        )
        mock_get.return_value = mock_client

        await translate_text("甲\n乙\n丙", "zh2en")
        assert mock_client.complete.await_count == 1

        # 第二轮：只有"丁"是新的，其他 2 行缓存命中
        mock_client.complete = AsyncMock(
            return_value=_mock_translations("D")
        )
        result = await translate_text("甲\n丁\n丙", "zh2en")

        lines = result.split("\n")
        assert lines[0] == "A"
        assert lines[1] == "D"
        assert lines[2] == "C"

        # LLM 只收到 1 行
        user_msg = [m for m in mock_client.complete.call_args[0][0] if m["role"] == "user"][0]
        payload = json.loads(user_msg["content"])
        assert payload["lines"] == ["丁"]


@pytest.mark.asyncio
async def test_cache_separates_directions():
    """同一文本在不同 direction 下缓存互相独立"""
    with patch("app.services.translate_service.get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(
            return_value=_mock_translations("zh2en result")
        )
        mock_get.return_value = mock_client

        await translate_text("hello", "zh2en")   # 第一次
        await translate_text("hello", "zh2en")   # 命中缓存

        # 换方向应不命中
        mock_client.complete = AsyncMock(
            return_value=_mock_translations("en2zh result")
        )
        mock_get.return_value = mock_client
        result = await translate_text("hello", "en2zh")
        assert "en2zh result" in result


@pytest.mark.asyncio
async def test_cache_writes_row():
    """翻译后应写入 translation_cache 表"""
    with patch("app.services.translate_service.get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(
            return_value=_mock_translations("Hello")
        )
        mock_get.return_value = mock_client

        await translate_text("你好", "zh2en")

        with OrmSession(engine) as s:
            rows = s.query(TranslationCache).filter_by(direction="zh2en").all()
            assert len(rows) == 1
            assert rows[0].source_text == "你好"
            assert rows[0].translated_text == "Hello"
            assert rows[0].hit_count == 1


@pytest.mark.asyncio
async def test_cache_hit_increments_count():
    """命中缓存时 hit_count 自增"""
    with patch("app.services.translate_service.get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(
            return_value=_mock_translations("Hello")
        )
        mock_get.return_value = mock_client

        await translate_text("你好", "zh2en")
        await translate_text("你好", "zh2en")
        await translate_text("你好", "zh2en")

        with OrmSession(engine) as s:
            row = s.query(TranslationCache).filter_by(
                direction="zh2en", source_text="你好"
            ).first()
            assert row.hit_count == 3
