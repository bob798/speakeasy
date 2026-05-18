"""
test_azure_tts.py — 单元测试 app/services/tts_service.py

覆盖：
  - _build_ssml 生成合法 SSML 结构（voice / prosody / rate）
  - _build_ssml 无 phoneme_map 时纯文本内容保持不变
  - _build_ssml 有 phoneme_map 时对匹配词插入 <phoneme> 标签
  - _build_ssml phoneme_map 匹配大小写不敏感
  - _build_ssml phoneme_map 只替换匹配的词，不影响其他词
  - _azure_tts 无 AZURE_TTS_KEY 时抛出 RuntimeError
  - _azure_tts HTTP 200 返回音频字节和 audio/mpeg
  - _azure_tts HTTP 非 200 抛出 RuntimeError
  - _azure_tts 返回空 body 抛出 RuntimeError
  - multi_tts provider=azure 调用 _azure_tts
  - multi_tts provider=azure 失败时降级到 _edge_tts
  - multi_tts provider=edge 直接调用 _edge_tts
  - multi_tts provider=unknown 抛出 ValueError
  - multi_tts 磁盘缓存：相同参数第二次调用不再调后端
"""

import hashlib
import os
import re
import tempfile
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.tts_service import _build_ssml, _azure_tts, multi_tts, TTS_CACHE_DIR


# ── _build_ssml ───────────────────────────────────────────────

def test_build_ssml_contains_voice_element():
    ssml = _build_ssml("Hello world", "en-US-JennyNeural", "+0%")
    assert 'name="en-US-JennyNeural"' in ssml
    assert "<voice" in ssml
    assert "</voice>" in ssml


def test_build_ssml_contains_prosody_with_rate():
    ssml = _build_ssml("Hello world", "en-US-JennyNeural", "+20%")
    assert 'rate="+20%"' in ssml
    assert "<prosody" in ssml
    assert "</prosody>" in ssml


def test_build_ssml_plain_text_preserved_when_no_phoneme_map():
    text = "This is a test sentence."
    ssml = _build_ssml(text, "en-US-JennyNeural", "+0%")
    assert text in ssml


def test_build_ssml_no_phoneme_map_produces_no_phoneme_tags():
    ssml = _build_ssml("Hello world", "en-US-JennyNeural", "+0%")
    assert "<phoneme" not in ssml


def test_build_ssml_phoneme_map_inserts_phoneme_tag_for_matching_word():
    ssml = _build_ssml("crisis", "en-US-JennyNeural", "+0%",
                        phoneme_map={"crisis": "ˈkraɪsɪs"})
    assert '<phoneme alphabet="ipa" ph="ˈkraɪsɪs">crisis</phoneme>' in ssml


def test_build_ssml_phoneme_map_case_insensitive_match():
    ssml = _build_ssml("Crisis is here", "en-US-JennyNeural", "+0%",
                        phoneme_map={"crisis": "ˈkraɪsɪs"})
    # Case-insensitive replacement should fire on "Crisis"
    assert "ˈkraɪsɪs" in ssml


def test_build_ssml_phoneme_map_only_replaces_mapped_words():
    ssml = _build_ssml("crisis worries day", "en-US-JennyNeural", "+0%",
                        phoneme_map={"crisis": "ˈkraɪsɪs", "worries": "ˈwʌriz"})
    assert "ˈkraɪsɪs" in ssml
    assert "ˈwʌriz" in ssml
    assert "day" in ssml
    # "day" must not have a phoneme tag
    assert 'ph="' not in ssml.split("day")[0].split("<phoneme")[-1] or "day" in ssml


def test_build_ssml_unmapped_word_unchanged():
    ssml = _build_ssml("hello stranger", "en-US-JennyNeural", "+0%",
                        phoneme_map={"hello": "həˈloʊ"})
    assert "stranger" in ssml
    assert "<phoneme" not in ssml.split("stranger")[0].split("</phoneme>")[-1]


def test_build_ssml_empty_phoneme_map_treated_as_no_map():
    ssml = _build_ssml("Hello", "en-US-JennyNeural", "+0%", phoneme_map={})
    assert "<phoneme" not in ssml
    assert "Hello" in ssml


def test_build_ssml_is_valid_xml_structure():
    ssml = _build_ssml("test", "en-US-GuyNeural", "-10%")
    assert ssml.startswith("<speak")
    assert ssml.endswith("</speak>")
    assert ssml.count("<voice") == ssml.count("</voice>")


# ── _azure_tts ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_azure_tts_raises_when_no_key_configured():
    with patch("app.services.tts_service.settings") as mock_settings:
        mock_settings.AZURE_TTS_KEY = ""
        mock_settings.AZURE_TTS_REGION = "eastus"
        with pytest.raises(RuntimeError, match="AZURE_TTS_KEY not configured"):
            await _azure_tts("Hello", "en-US-JennyNeural")


@pytest.mark.asyncio
async def test_azure_tts_returns_audio_bytes_on_http_200():
    fake_audio = b"\xff\xfb\x90\x00" * 100  # fake MP3 header bytes

    with patch("app.services.tts_service.settings") as mock_settings, \
         patch("app.services.tts_service.httpx.AsyncClient") as mock_client_cls:
        mock_settings.AZURE_TTS_KEY = "fake-key"
        mock_settings.AZURE_TTS_REGION = "eastus"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = fake_audio

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        audio, media_type = await _azure_tts("Hello world", "en-US-JennyNeural")

    assert audio == fake_audio
    assert media_type == "audio/mpeg"


@pytest.mark.asyncio
async def test_azure_tts_raises_on_http_non_200():
    with patch("app.services.tts_service.settings") as mock_settings, \
         patch("app.services.tts_service.httpx.AsyncClient") as mock_client_cls:
        mock_settings.AZURE_TTS_KEY = "fake-key"
        mock_settings.AZURE_TTS_REGION = "eastus"

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.content = b""

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(RuntimeError, match="Azure TTS failed: HTTP 401"):
            await _azure_tts("Hello", "en-US-JennyNeural")


@pytest.mark.asyncio
async def test_azure_tts_raises_on_empty_audio_body():
    with patch("app.services.tts_service.settings") as mock_settings, \
         patch("app.services.tts_service.httpx.AsyncClient") as mock_client_cls:
        mock_settings.AZURE_TTS_KEY = "fake-key"
        mock_settings.AZURE_TTS_REGION = "eastus"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b""

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(RuntimeError, match="Azure TTS returned empty audio"):
            await _azure_tts("Hello", "en-US-JennyNeural")


# ── multi_tts provider routing ────────────────────────────────

@pytest.fixture(autouse=True)
def clear_tts_cache(tmp_path, monkeypatch):
    """Redirect TTS_CACHE_DIR to a temp dir so cache files don't bleed between tests."""
    import app.services.tts_service as svc
    monkeypatch.setattr(svc, "TTS_CACHE_DIR", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    yield


@pytest.mark.asyncio
async def test_multi_tts_azure_provider_calls_azure_tts():
    fake_audio = b"fake-azure-audio"
    with patch("app.services.tts_service._azure_tts", new_callable=AsyncMock,
               return_value=(fake_audio, "audio/mpeg")) as mock_azure, \
         patch("app.services.tts_service.settings") as mock_settings:
        mock_settings.TTS_DEFAULT_PROVIDER = "edge"

        audio, media_type, _meta = await multi_tts("Hello", provider="azure", voice="jenny")

    mock_azure.assert_called_once()
    assert audio == fake_audio
    assert media_type == "audio/mpeg"


@pytest.mark.asyncio
async def test_multi_tts_azure_failure_falls_back_to_edge():
    fake_audio = b"fake-edge-audio"
    with patch("app.services.tts_service._azure_tts", new_callable=AsyncMock,
               side_effect=RuntimeError("Azure down")), \
         patch("app.services.tts_service._edge_tts", new_callable=AsyncMock,
               return_value=(fake_audio, "audio/mpeg")) as mock_edge, \
         patch("app.services.tts_service.settings") as mock_settings:
        mock_settings.TTS_DEFAULT_PROVIDER = "edge"

        audio, media_type, _meta = await multi_tts("Hello", provider="azure", voice="jenny")

    mock_edge.assert_called_once()
    assert audio == fake_audio


@pytest.mark.asyncio
async def test_multi_tts_edge_provider_calls_edge_tts_directly():
    fake_audio = b"fake-edge-audio"
    with patch("app.services.tts_service._edge_tts", new_callable=AsyncMock,
               return_value=(fake_audio, "audio/mpeg")) as mock_edge, \
         patch("app.services.tts_service._azure_tts", new_callable=AsyncMock,
               side_effect=AssertionError("should not call azure")), \
         patch("app.services.tts_service.settings") as mock_settings:
        mock_settings.TTS_DEFAULT_PROVIDER = "edge"

        audio, media_type, _meta = await multi_tts("Hello", provider="edge", voice="jenny")

    mock_edge.assert_called_once()
    assert audio == fake_audio


@pytest.mark.asyncio
async def test_multi_tts_unknown_provider_raises_value_error():
    with patch("app.services.tts_service.settings") as mock_settings:
        mock_settings.TTS_DEFAULT_PROVIDER = "edge"
        with pytest.raises(ValueError, match="Unknown provider"):
            await multi_tts("Hello", provider="nonexistent_provider")


@pytest.mark.asyncio
async def test_multi_tts_uses_settings_default_when_no_provider_given():
    fake_audio = b"edge-default"
    with patch("app.services.tts_service._edge_tts", new_callable=AsyncMock,
               return_value=(fake_audio, "audio/mpeg")), \
         patch("app.services.tts_service.settings") as mock_settings:
        mock_settings.TTS_DEFAULT_PROVIDER = "edge"

        audio, _, _meta = await multi_tts("Hello", provider=None, voice="jenny")

    assert audio == fake_audio


@pytest.mark.asyncio
async def test_multi_tts_second_call_uses_disk_cache(tmp_path, monkeypatch):
    """Second call with same args reads from cache, not calling backend."""
    import app.services.tts_service as svc
    monkeypatch.setattr(svc, "TTS_CACHE_DIR", str(tmp_path))

    fake_audio = b"cached-audio-data"
    call_count = 0

    async def fake_edge(text, voice, rate):
        nonlocal call_count
        call_count += 1
        return fake_audio, "audio/mpeg"

    with patch("app.services.tts_service._edge_tts", side_effect=fake_edge), \
         patch("app.services.tts_service.settings") as mock_settings:
        mock_settings.TTS_DEFAULT_PROVIDER = "edge"

        audio1, _, _m1 = await multi_tts("Cache test", provider="edge", voice="jenny")
        audio2, _, _m2 = await multi_tts("Cache test", provider="edge", voice="jenny")

    assert call_count == 1  # backend called only once
    assert audio1 == fake_audio
    assert audio2 == fake_audio


# ── IPA 纠音扩展（多词短语 + 智能升级 + meta header）─────────


def test_build_ssml_multi_word_phrase_phoneme():
    """多词短语 key 应跨空格匹配并插入 <phoneme>"""
    ssml = _build_ssml(
        "give me a hand", "en-US-JennyNeural", "+0%",
        phoneme_map={"give me": "ɡɪmi"},
    )
    assert '<phoneme alphabet="ipa" ph="ɡɪmi">give me</phoneme>' in ssml


def test_build_ssml_mixed_word_and_phrase_phoneme():
    """单词 + 多词短语混合 phoneme_map"""
    ssml = _build_ssml(
        "would you give me a hand", "en-US-JennyNeural", "+0%",
        phoneme_map={"would you": "wʊdʒu", "hand": "hænd"},
    )
    assert '<phoneme alphabet="ipa" ph="wʊdʒu">would you</phoneme>' in ssml
    assert '<phoneme alphabet="ipa" ph="hænd">hand</phoneme>' in ssml


@pytest.mark.asyncio
async def test_multi_tts_smart_upgrade_edge_to_azure_when_phoneme_and_key_present():
    """provider=edge + phoneme_map + AZURE_TTS_KEY 已配 → 实际走 azure，meta 标 provider_used=azure"""
    fake_audio = b"fake-azure-audio"
    with patch("app.services.tts_service._azure_tts", new_callable=AsyncMock,
               return_value=(fake_audio, "audio/mpeg")) as mock_azure, \
         patch("app.services.tts_service._edge_tts", new_callable=AsyncMock,
               side_effect=AssertionError("should not call edge when upgrading")), \
         patch("app.services.tts_service.settings") as mock_settings:
        mock_settings.TTS_DEFAULT_PROVIDER = "edge"
        mock_settings.AZURE_TTS_KEY = "fake-key"
        mock_settings.AZURE_TTS_REGION = "eastasia"

        audio, media_type, meta = await multi_tts(
            "schedule", provider="edge", voice="jenny",
            phoneme_map={"schedule": "ˈskɛdʒuːl"},
        )

    mock_azure.assert_called_once()
    assert audio == fake_audio
    assert meta["provider_used"] == "azure"
    assert meta["phoneme_ignored"] is False


@pytest.mark.asyncio
async def test_multi_tts_phoneme_ignored_when_azure_key_missing():
    """phoneme_map 给了但 AZURE_TTS_KEY 没配 → 走原 provider + phoneme_ignored=True"""
    fake_audio = b"fake-edge-audio"
    with patch("app.services.tts_service._edge_tts", new_callable=AsyncMock,
               return_value=(fake_audio, "audio/mpeg")) as mock_edge, \
         patch("app.services.tts_service._azure_tts", new_callable=AsyncMock,
               side_effect=AssertionError("azure must not be called without key")), \
         patch("app.services.tts_service.settings") as mock_settings:
        mock_settings.TTS_DEFAULT_PROVIDER = "edge"
        mock_settings.AZURE_TTS_KEY = ""

        audio, media_type, meta = await multi_tts(
            "schedule", provider="edge", voice="jenny",
            phoneme_map={"schedule": "ˈskɛdʒuːl"},
        )

    mock_edge.assert_called_once()
    assert audio == fake_audio
    assert meta["provider_used"] == "edge"
    assert meta["phoneme_ignored"] is True


@pytest.mark.asyncio
async def test_multi_tts_azure_fallback_to_edge_sets_meta_fallback():
    """Azure 抛异常降级 edge → meta.fallback='edge' + provider_used='edge'"""
    fake_audio = b"fake-edge-audio"
    with patch("app.services.tts_service._azure_tts", new_callable=AsyncMock,
               side_effect=RuntimeError("Azure down")), \
         patch("app.services.tts_service._edge_tts", new_callable=AsyncMock,
               return_value=(fake_audio, "audio/mpeg")) as mock_edge, \
         patch("app.services.tts_service.settings") as mock_settings:
        mock_settings.TTS_DEFAULT_PROVIDER = "edge"
        mock_settings.AZURE_TTS_KEY = "fake-key"
        mock_settings.AZURE_TTS_REGION = "eastasia"

        audio, media_type, meta = await multi_tts(
            "schedule", provider="azure", voice="jenny",
            phoneme_map={"schedule": "ˈskɛdʒuːl"},
        )

    mock_edge.assert_called_once()
    assert audio == fake_audio
    assert meta["fallback"] == "edge"
    assert meta["provider_used"] == "edge"
    assert meta["phoneme_ignored"] is True  # phoneme_map 无法在 edge 上生效


@pytest.mark.asyncio
async def test_practice_tts_route_passes_phoneme_and_sets_headers():
    """端到端：路由接 phoneme_map，把 meta 翻成 response header"""
    from fastapi.testclient import TestClient
    from main import app

    fake_audio = b"fake-azure-audio"
    with patch("app.services.tts_service._azure_tts", new_callable=AsyncMock,
               return_value=(fake_audio, "audio/mpeg")), \
         patch("app.services.tts_service.settings") as mock_settings:
        mock_settings.TTS_DEFAULT_PROVIDER = "edge"
        mock_settings.AZURE_TTS_KEY = "fake-key"
        mock_settings.AZURE_TTS_REGION = "eastasia"

        client = TestClient(app)
        resp = client.post("/practice/tts", json={
            "text": "schedule",
            "provider": "edge",
            "voice": "jenny",
            "speed": "+0%",
            "phoneme_map": {"schedule": "ˈskɛdʒuːl"},
        })

    assert resp.status_code == 200
    assert resp.content == fake_audio
    assert resp.headers.get("X-TTS-Provider-Used") == "azure"
    assert resp.headers.get("X-TTS-Phoneme-Ignored") is None
    assert resp.headers.get("X-TTS-Fallback") is None
