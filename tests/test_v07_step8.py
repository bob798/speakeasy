"""
V0.7 Step 8 — 连读 liaison 字段 + 慢速 TTS
"""
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, Base, ExplanationCache, UserProfile
from app.services.explain_service import explain_text, _SCHEMA_VERSION
from app.prompts.explain import EXPLAIN_SENTENCE_PROMPT

TEST_USER = "test_user_v07_step8"


@pytest.fixture(autouse=True)
def cleanup():
    Base.metadata.create_all(engine)
    with OrmSession(engine) as s:
        s.query(ExplanationCache).delete()
        s.query(UserProfile).filter_by(user_id=TEST_USER).delete()
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(ExplanationCache).delete()
        s.query(UserProfile).filter_by(user_id=TEST_USER).delete()
        s.commit()


# ── prompt ──────────────────────────────────────────────────

def test_sentence_prompt_contains_liaison_spec():
    assert "liaison" in EXPLAIN_SENTENCE_PROMPT
    # 结构说明
    assert "chunk" in EXPLAIN_SENTENCE_PROMPT
    assert "ipa" in EXPLAIN_SENTENCE_PROMPT
    assert "tip" in EXPLAIN_SENTENCE_PROMPT


# ── schema 版本隔离 ─────────────────────────────────────────

def test_schema_version_bumped_past_1():
    assert _SCHEMA_VERSION >= 2


# ── explain_text 产出 liaison ───────────────────────────────

MOCK_SENTENCE_JSON = (
    '{"meaning":"捡起来","grammar":"动补","phrases":[],'
    '"liaison":[{"chunk":"pick it up","ipa":"/pɪˈkɪtʌp/","tip":"t 连到 i，k 轻化"}],'
    '"current_level_points":["动词连读"],"next_level_points":[]}'
)


@pytest.mark.asyncio
async def test_explain_sentence_returns_liaison():
    with patch("app.services.explain_service.get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=MOCK_SENTENCE_JSON)
        mock_get.return_value = mock_client

        out = await explain_text(
            text="Please pick it up.",
            kind="sentence",
            user_id=TEST_USER,
            context="",
        )
    lia = out["explanation"].get("liaison") or []
    assert len(lia) == 1
    assert lia[0]["chunk"] == "pick it up"
    assert "/" in lia[0]["ipa"]


# ── 前端 ────────────────────────────────────────────────────

PRACTICE_HTML = Path("static/practice.html")


def test_liaison_section_in_renderer():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    assert "ex.liaison" in src
    assert "连读点" in src
    assert "liaison-chunk" in src
    assert "liaison-ipa" in src


def test_liaison_has_normal_and_slow_speak():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    # 正常 + 慢读两个按钮（改 data-speed 后保持两档）
    assert 'data-speed="+0%"' in src
    assert 'data-speed="-25%"' in src
    assert "🐢" in src


def test_drawer_speak_passes_speed_to_tts():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    # drawerSpeak 接受 speed 参数并向后传
    assert "async function drawerSpeak(text, speed)" in src
    assert "speed: speed" in src
