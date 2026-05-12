"""
test_google_tts.py — 单元测试 _google_tts + _parse_speed_to_rate

覆盖：
  - _parse_speed_to_rate 正常/异常 input → speakingRate
  - _google_tts 无 GOOGLE_TTS_API_KEY 时抛 RuntimeError
  - _google_tts HTTP 200 返回 base64 解码后的音频字节
  - _google_tts HTTP 非 200 抛 RuntimeError
  - _google_tts 返回空 audioContent 抛 RuntimeError
  - multi_tts provider=google 调用 _google_tts
  - multi_tts provider=google 失败时降级 edge
"""
import base64
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.tts_service import _parse_speed_to_rate, _google_tts, multi_tts


# ── _parse_speed_to_rate ──────────────────────────────────────

@pytest.mark.parametrize("inp,expected", [
    ("+0%",   1.0),
    ("+20%",  1.2),
    ("-20%",  0.8),
    ("-40%",  0.6),
    ("+0",    1.0),     # no % suffix
    (None,    1.0),     # None defaults to +0%
    ("",      1.0),
    ("abc",   1.0),     # invalid input fall back to 1.0
    ("+1000%", 4.0),    # clamped upper bound
    ("-200%", 0.25),    # clamped lower bound
])
def test_parse_speed_to_rate(inp, expected):
    assert _parse_speed_to_rate(inp) == expected


# ── _google_tts ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_google_tts_missing_key():
    with patch("app.services.tts_service.settings") as mock_settings:
        mock_settings.GOOGLE_TTS_API_KEY = ""
        with pytest.raises(RuntimeError, match="GOOGLE_TTS_API_KEY"):
            await _google_tts("hello")


@pytest.mark.asyncio
async def test_google_tts_success():
    fake_audio = b"\x00\x01\x02FAKEMP3"
    fake_resp = MagicMock(status_code=200)
    fake_resp.json = MagicMock(return_value={
        "audioContent": base64.b64encode(fake_audio).decode("ascii"),
    })

    with patch("app.services.tts_service.settings") as mock_settings, \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_settings.GOOGLE_TTS_API_KEY = "test_key"
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(return_value=fake_resp)
        mock_client_cls.return_value = mock_client

        audio, media_type = await _google_tts("hello", "en-US-JennyNeural", "+20%")
        assert audio == fake_audio
        assert media_type == "audio/mpeg"

        # 验证 body 里 speakingRate 是 1.2、languageCode 是 en-US
        post_kwargs = mock_client.post.call_args.kwargs
        body = post_kwargs["json"]
        assert body["audioConfig"]["speakingRate"] == 1.2
        assert body["voice"]["languageCode"] == "en-US"


@pytest.mark.asyncio
async def test_google_tts_http_error():
    fake_resp = MagicMock(status_code=403, text="quota exceeded")
    with patch("app.services.tts_service.settings") as mock_settings, \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_settings.GOOGLE_TTS_API_KEY = "test_key"
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(return_value=fake_resp)
        mock_client_cls.return_value = mock_client

        with pytest.raises(RuntimeError, match="HTTP 403"):
            await _google_tts("hello")


@pytest.mark.asyncio
async def test_google_tts_empty_audio_content():
    fake_resp = MagicMock(status_code=200)
    fake_resp.json = MagicMock(return_value={"audioContent": ""})
    with patch("app.services.tts_service.settings") as mock_settings, \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_settings.GOOGLE_TTS_API_KEY = "test_key"
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(return_value=fake_resp)
        mock_client_cls.return_value = mock_client

        with pytest.raises(RuntimeError, match="empty audioContent"):
            await _google_tts("hello")


# ── multi_tts dispatch ────────────────────────────────────────

@pytest.mark.asyncio
async def test_multi_tts_routes_google():
    fake_audio = b"GOOGLE_AUDIO"
    with patch("app.services.tts_service._google_tts", new=AsyncMock(return_value=(fake_audio, "audio/mpeg"))) as mock_g, \
         patch("app.services.tts_service.os.path.exists", return_value=False), \
         patch("builtins.open", create=True):
        audio, media_type = await multi_tts(
            text="unique-google-test-text-abc123",
            provider="google",
            voice="jenny",
            speed="+0%",
        )
        assert audio == fake_audio
        assert media_type == "audio/mpeg"
        mock_g.assert_called_once()


@pytest.mark.asyncio
async def test_multi_tts_google_falls_back_to_edge():
    fake_edge_audio = b"EDGE_FALLBACK_AUDIO"
    with patch("app.services.tts_service._google_tts", new=AsyncMock(side_effect=RuntimeError("api down"))), \
         patch("app.services.tts_service._edge_tts", new=AsyncMock(return_value=(fake_edge_audio, "audio/mpeg"))) as mock_e, \
         patch("app.services.tts_service.os.path.exists", return_value=False), \
         patch("builtins.open", create=True):
        audio, media_type = await multi_tts(
            text="unique-google-fallback-text-xyz789",
            provider="google",
            voice="jenny",
            speed="+0%",
        )
        assert audio == fake_edge_audio
        assert media_type == "audio/mpeg"
        mock_e.assert_called_once()
