"""
V0.7 Step 9 — narration 字段 + 讲给我听
"""
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, Base, ExplanationCache
from app.services.explain_service import explain_text, _SCHEMA_VERSION
from app.prompts.explain import EXPLAIN_SENTENCE_PROMPT, EXPLAIN_WORD_PROMPT
from app.services.tts_service import VOICES

TEST_USER = "test_user_v07_step9"


@pytest.fixture(autouse=True)
def cleanup():
    Base.metadata.create_all(engine)
    with OrmSession(engine) as s:
        s.query(ExplanationCache).delete()
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(ExplanationCache).delete()
        s.commit()


def test_narration_in_both_prompts():
    for p in (EXPLAIN_SENTENCE_PROMPT, EXPLAIN_WORD_PROMPT):
        assert '"narration"' in p or '"narration":' in p or "narration" in p


def test_schema_version_bumped_to_3_or_higher():
    # narration 语言规则已升级到 v4；继续向后兼容
    assert _SCHEMA_VERSION >= 3


def test_chinese_voices_registered():
    assert "xiaoxiao" in VOICES
    assert VOICES["xiaoxiao"].startswith("zh-CN")


MOCK_SENTENCE = (
    '{"meaning":"今天下雨","grammar":"主谓","phrases":[],"liaison":[],'
    '"current_level_points":[],"next_level_points":[],'
    '"narration":"这句话说今天下雨了。用的是一般现在时，描述的是现在正在发生的事情。"}'
)


@pytest.mark.asyncio
async def test_explain_returns_narration():
    with patch("app.services.explain_service.get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=MOCK_SENTENCE)
        mock_get.return_value = mock_client
        out = await explain_text(
            text="It is raining today.",
            kind="sentence",
            user_id=TEST_USER,
            context="",
        )
    nar = out["explanation"].get("narration")
    assert nar is not None
    assert "下雨" in nar
    assert "一般现在时" in nar


# ── frontend ───────────────────────────────────────────────

PRACTICE_HTML = Path("static/practice.html")


def test_narration_button_present():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    assert 'id="explainNarrationBtn"' in src
    assert 'playExplainNarration()' in src
    assert '▶️' in src


def test_narration_uses_level_aware_voice():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    start = src.index('async function playExplainNarration')
    body  = src[start:src.index('\n}\n', start)]
    # 基础字段
    assert "/practice/tts" in body
    assert "narration" in body
    # A~B 用 xiaoxiao，C1+ 用 jenny
    assert "'xiaoxiao'" in body
    assert "'jenny'" in body
    assert "C1" in body and "C2" in body


def test_narration_falls_back_when_missing():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    # 没 narration 时 toast 提示
    assert "没有讲解稿" in src
