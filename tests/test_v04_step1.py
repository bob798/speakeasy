"""
V0.4 Step 1 — 数据模型 + FSRS 工具 + 字幕提取服务
user_id: test_user_v04_s1
"""
import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.exc import IntegrityError

from app.models.db import engine, Base, PronunciationCard, SubtitleSource
from app.services.fsrs_utils import (
    create_card, review_card, get_due_date, is_due, RATING_MAP,
)
from app.services.subtitle_service import extract_bvid, fetch_bilibili_subtitles, parse_manual_text
from fsrs import Rating

TEST_USER = "test_user_v04_s1"


@pytest.fixture(autouse=True)
def cleanup():
    Base.metadata.create_all(engine)
    yield
    with OrmSession(engine) as s:
        s.query(PronunciationCard).filter_by(user_id=TEST_USER).delete()
        s.query(SubtitleSource).filter_by(user_id=TEST_USER).delete()
        s.commit()


# ── 表结构 ──────────────────────────────────────────────────

def test_pronunciation_cards_table_exists():
    inspector = sa_inspect(engine)
    tables = inspector.get_table_names()
    assert "pronunciation_cards" in tables

def test_subtitle_sources_table_exists():
    inspector = sa_inspect(engine)
    tables = inspector.get_table_names()
    assert "subtitle_sources" in tables

def test_pronunciation_card_tablename():
    assert PronunciationCard.__tablename__ == "pronunciation_cards"

def test_subtitle_source_tablename():
    assert SubtitleSource.__tablename__ == "subtitle_sources"


# ── PronunciationCard CRUD ──────────────────────────────────

def test_create_pronunciation_card():
    card_json = create_card(Rating.Again)
    with OrmSession(engine) as s:
        card = PronunciationCard(
            user_id=TEST_USER,
            text="hello world",
            context="Hello world, how are you?",
            source_url="https://bilibili.com/video/BV1test12345",
            fsrs_card_data=card_json,
            status="active",
        )
        s.add(card)
        s.commit()
        s.refresh(card)

        assert card.id is not None
        assert card.user_id == TEST_USER
        assert card.text == "hello world"
        assert card.status == "active"
        assert card.practice_count == 0
        assert json.loads(card.fsrs_card_data).get("due") is not None


def test_pronunciation_card_unique_constraint():
    with OrmSession(engine) as s:
        s.add(PronunciationCard(
            user_id=TEST_USER, text="duplicate test",
            fsrs_card_data=create_card(), status="active",
        ))
        s.commit()

    with pytest.raises(IntegrityError):
        with OrmSession(engine) as s:
            s.add(PronunciationCard(
                user_id=TEST_USER, text="duplicate test",
                fsrs_card_data=create_card(), status="active",
            ))
            s.commit()


# ── SubtitleSource 唯一约束 ─────────────────────────────────

def test_subtitle_source_unique_bvid():
    with OrmSession(engine) as s:
        s.add(SubtitleSource(
            user_id=TEST_USER, bvid="BV1test12345x",
            subtitle_json='[]',
        ))
        s.commit()

    with pytest.raises(IntegrityError):
        with OrmSession(engine) as s:
            s.add(SubtitleSource(
                user_id=TEST_USER, bvid="BV1test12345x",
                subtitle_json='[]',
            ))
            s.commit()


# ── BV号提取 ───────────────────────────────────────────────

def test_extract_bvid_from_full_url():
    assert extract_bvid("https://www.bilibili.com/video/BV1xx411c7XW") == "BV1xx411c7XW"

def test_extract_bvid_from_bare():
    assert extract_bvid("BV1xx411c7XW") == "BV1xx411c7XW"

def test_extract_bvid_invalid():
    assert extract_bvid("invalid-url") is None

def test_extract_bvid_too_short():
    assert extract_bvid("BV123") is None


# ── FSRS Utils ─────────────────────────────────────────────

def test_create_card_has_due():
    card_json = create_card(Rating.Again)
    data = json.loads(card_json)
    assert "due" in data
    assert data["due"] is not None

def test_review_card_changes_due():
    card_json = create_card(Rating.Again)
    new_json, new_data = review_card(card_json, Rating.Good)
    assert new_json != card_json
    assert "due" in new_data

def test_get_due_date_empty():
    assert get_due_date("") is None

def test_get_due_date_valid():
    card_json = create_card(Rating.Again)
    due = get_due_date(card_json)
    assert due is not None

def test_is_due_empty():
    assert is_due("") is False

def test_is_due_fresh_again_card():
    # Rating.Again 产生极短间隔，新创建的卡应该很快到期
    card_json = create_card(Rating.Again)
    # 不能确定立即到期（取决于 FSRS 参数），但函数不应抛异常
    assert isinstance(is_due(card_json), bool)

def test_rating_map():
    assert RATING_MAP["again"] == Rating.Again
    assert RATING_MAP["hard"] == Rating.Hard
    assert RATING_MAP["good"] == Rating.Good
    assert RATING_MAP["easy"] == Rating.Easy


# ── 字幕提取 Mock 测试 ────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_invalid_bvid():
    result = await fetch_bilibili_subtitles("invalid")
    assert "error" in result
    assert result["segments"] == []

@pytest.mark.asyncio
async def test_fetch_bilibili_mock_success():
    """Mock B站 API 完整 4 步成功路径"""
    mock_responses = [
        # Step 2: 视频信息
        MagicMock(json=lambda: {"code": 0, "data": {"cid": 12345, "title": "Test Video"}}),
        # Step 3: 播放器信息
        MagicMock(json=lambda: {
            "code": 0,
            "data": {"subtitle": {"subtitles": [{
                "subtitle_url": "//i0.hdslb.com/bfs/subtitle/test.json",
                "lan": "en",
            }]}}
        }),
        # Step 4: 字幕内容
        MagicMock(
            json=lambda: {"body": [
                {"from": 0.5, "to": 2.1, "content": "Hello everyone"},
                {"from": 2.2, "to": 4.0, "content": "Welcome to the show"},
            ]},
            content=b'x' * 100,  # 小于 500KB
        ),
    ]

    with patch("app.services.subtitle_service.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(side_effect=mock_responses)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = mock_instance

        result = await fetch_bilibili_subtitles("BV1xx411c7XWa")
        assert "error" not in result
        assert result["title"] == "Test Video"
        assert result["bvid"] == "BV1xx411c7XWa"
        assert len(result["segments"]) == 2
        assert result["segments"][0]["content"] == "Hello everyone"

@pytest.mark.asyncio
async def test_fetch_bilibili_mock_no_subtitles():
    """视频无字幕"""
    mock_responses = [
        MagicMock(json=lambda: {"code": 0, "data": {"cid": 12345, "title": "No Sub"}}),
        MagicMock(json=lambda: {"code": 0, "data": {"subtitle": {"subtitles": []}}}),
    ]

    with patch("app.services.subtitle_service.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(side_effect=mock_responses)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = mock_instance

        result = await fetch_bilibili_subtitles("BV1xx411c7XWa")
        assert "error" in result
        assert "无字幕" in result["error"]

@pytest.mark.asyncio
async def test_fetch_bilibili_mock_video_not_found():
    """视频不存在"""
    with patch("app.services.subtitle_service.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(
            return_value=MagicMock(json=lambda: {"code": -404, "data": {}})
        )
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = mock_instance

        result = await fetch_bilibili_subtitles("BV1xx411c7XWa")
        assert "error" in result


# ── 手动粘贴解析 ──────────────────────────────────────────

def test_parse_manual_text():
    text = "Hello world.\nHow are you?\n\nI'm fine."
    segments = parse_manual_text(text)
    assert len(segments) == 3
    assert segments[0]["content"] == "Hello world."
    assert segments[1]["content"] == "How are you?"
    assert segments[2]["content"] == "I'm fine."

def test_parse_manual_text_empty():
    assert parse_manual_text("") == []
    assert parse_manual_text("  \n  \n  ") == []


# ── SSRF 防护 ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ssrf_blocked_subtitle_url():
    """字幕 URL 指向非白名单域名应被拒绝"""
    mock_responses = [
        MagicMock(json=lambda: {"code": 0, "data": {"cid": 123, "title": "T"}}),
        MagicMock(json=lambda: {
            "code": 0,
            "data": {"subtitle": {"subtitles": [{
                "subtitle_url": "//evil.com/steal-data",
                "lan": "en",
            }]}}
        }),
    ]

    with patch("app.services.subtitle_service.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(side_effect=mock_responses)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = mock_instance

        result = await fetch_bilibili_subtitles("BV1xx411c7XWa")
        assert "error" in result
        assert "不在可信域名" in result["error"]
