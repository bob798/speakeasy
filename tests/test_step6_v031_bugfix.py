"""
BUG-003 修复验证：VAD 状态机完整生命周期
- 页面加载时初始为 IDLE
- Alex 说话时暂停
- Alex 说完后自动恢复
"""
import pytest
from unittest.mock import patch
from app.services.vad_service import VADService, VADState


def test_vad_initial_state_is_idle():
    """页面加载时 VAD 初始状态为 IDLE，不自动监听"""
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        assert vad.state == VADState.IDLE
        assert vad.can_detect() == False  # IDLE 状态不检测


def test_vad_pauses_when_alex_speaks():
    """Alex 开始说话时 VAD 暂停"""
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        vad.set_state(VADState.LISTENING)
        vad.pause()
        assert vad.state == VADState.ALEX_SPEAKING
        assert vad.can_detect() == False


def test_vad_resumes_after_alex_finishes():
    """Alex 说完后 VAD 自动恢复监听"""
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        vad.set_state(VADState.ALEX_SPEAKING)
        vad.resume()
        assert vad.state == VADState.LISTENING
        assert vad.can_detect() == True


def test_vad_does_not_detect_in_alex_speaking_state():
    """Alex 说话期间 VAD 不处理音频，避免 Alex 声音触发录音"""
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        vad.set_state(VADState.ALEX_SPEAKING)
        assert vad.can_detect() == False


def test_vad_resumes_after_tts_error():
    """TTS 播放出错时 VAD 也能恢复，不卡死"""
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        vad.set_state(VADState.ALEX_SPEAKING)
        vad.resume()  # onerror 回调中也调用 resume
        assert vad.state == VADState.LISTENING


def test_vad_listening_state_can_detect():
    """仅 LISTENING 状态下 can_detect 为 True"""
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        for state in VADState:
            vad.set_state(state)
            if state == VADState.LISTENING:
                assert vad.can_detect() == True
            else:
                assert vad.can_detect() == False
