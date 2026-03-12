"""
Step 3 测试：TTS 层集成语速与音色
通过 /tts 端点传入 user_id，验证 edge_tts.Communicate 使用了正确的 voice 和 rate。
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from main import app
from app.models.db import UserSettings, engine
from sqlalchemy.orm import sessionmaker

TEST_USER = "test_user_v031_step3"
client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup():
    yield
    Session = sessionmaker(bind=engine)
    session = Session()
    session.query(UserSettings).filter_by(user_id=TEST_USER).delete()
    session.commit()
    session.close()


def _make_mock_communicate(captured: dict):
    """生成 mock Communicate，捕获 voice 和 rate 参数"""
    def mock_communicate(text, voice, rate="+0%", **kwargs):
        captured["voice"] = voice
        captured["rate"] = rate
        mock = MagicMock()
        mock.stream = AsyncMock(return_value=aiter([{"type": "audio", "data": b"fake_audio"}]))
        return mock
    return mock_communicate


async def aiter(items):
    for item in items:
        yield item


def test_tts_uses_warm_voice_by_default():
    """默认设置下 TTS 使用 JennyNeural，rate +0%"""
    captured = {}

    async def fake_stream():
        yield {"type": "audio", "data": b"x" * 100}

    def mock_communicate(text, voice, rate="+0%", **kwargs):
        captured["voice"] = voice
        captured["rate"] = rate
        m = MagicMock()
        m.stream.return_value = fake_stream()
        return m

    with patch("app.services.tts_service.edge_tts.Communicate", side_effect=mock_communicate):
        resp = client.post("/tts", json={"text": "Hello!", "user_id": TEST_USER})

    assert resp.status_code == 200
    assert captured.get("voice") == "en-US-JennyNeural"
    assert captured.get("rate") == "+0%"


def test_tts_uses_steady_voice_after_setting_change():
    """切换到 Steady 后 TTS 使用 GuyNeural"""
    client.post(f"/settings/{TEST_USER}", json={"voice": "steady"})
    captured = {}

    async def fake_stream():
        yield {"type": "audio", "data": b"x" * 100}

    def mock_communicate(text, voice, rate="+0%", **kwargs):
        captured["voice"] = voice
        captured["rate"] = rate
        m = MagicMock()
        m.stream.return_value = fake_stream()
        return m

    with patch("app.services.tts_service.edge_tts.Communicate", side_effect=mock_communicate):
        resp = client.post("/tts", json={"text": "Hello!", "user_id": TEST_USER})

    assert resp.status_code == 200
    assert captured.get("voice") == "en-US-GuyNeural"


def test_tts_uses_slow_rate_after_setting_change():
    """切换到 Slow 后 TTS rate 为 -25%"""
    client.post(f"/settings/{TEST_USER}", json={"speed": "slow"})
    captured = {}

    async def fake_stream():
        yield {"type": "audio", "data": b"x" * 100}

    def mock_communicate(text, voice, rate="+0%", **kwargs):
        captured["voice"] = voice
        captured["rate"] = rate
        m = MagicMock()
        m.stream.return_value = fake_stream()
        return m

    with patch("app.services.tts_service.edge_tts.Communicate", side_effect=mock_communicate):
        resp = client.post("/tts", json={"text": "Hello!", "user_id": TEST_USER})

    assert resp.status_code == 200
    assert captured.get("rate") == "-25%"


def test_tts_fast_rate():
    """切换到 Fast 后 TTS rate 为 +25%"""
    client.post(f"/settings/{TEST_USER}", json={"speed": "fast"})
    captured = {}

    async def fake_stream():
        yield {"type": "audio", "data": b"x" * 100}

    def mock_communicate(text, voice, rate="+0%", **kwargs):
        captured["voice"] = rate
        captured["rate"] = rate
        m = MagicMock()
        m.stream.return_value = fake_stream()
        return m

    with patch("app.services.tts_service.edge_tts.Communicate", side_effect=mock_communicate):
        resp = client.post("/tts", json={"text": "Hello!", "user_id": TEST_USER})

    assert resp.status_code == 200
    assert captured.get("rate") == "+25%"
