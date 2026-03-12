import torch
import numpy as np
from enum import Enum
from silero_vad import load_silero_vad

SAMPLE_RATE = 16000
SILENCE_THRESHOLD_SECONDS = 2.0
MISFIRE_MAX_COUNT = 3
MIN_TRANSCRIPT_LENGTH = 2  # 少于2字符视为误触


class VADState(Enum):
    IDLE          = "idle"          # 待机，页面加载初始状态
    LISTENING     = "listening"     # 监听中
    RECORDING     = "recording"     # 录音中（检测到语音）
    PROCESSING    = "processing"    # 识别中
    ALEX_SPEAKING = "alex_speaking" # Alex TTS 播放中


class VADService:
    def __init__(self):
        self.model = load_silero_vad()
        self.misfire_count = 0
        self.state = VADState.IDLE  # 初始为待机，BUG-003/004 修复

    def set_state(self, state: VADState):
        self.state = state

    def pause(self):
        """Alex 说话时调用，暂停 VAD 检测（BUG-003 修复）"""
        self.state = VADState.ALEX_SPEAKING

    def resume(self):
        """Alex 说话结束后调用，恢复监听（BUG-003 修复）"""
        self.state = VADState.LISTENING

    def can_detect(self) -> bool:
        """只有 LISTENING 状态才处理音频"""
        return self.state == VADState.LISTENING

    def is_speech(self, audio_chunk: np.ndarray) -> bool:
        """判断音频块是否包含语音"""
        tensor = torch.FloatTensor(audio_chunk)
        confidence = self.model(tensor, SAMPLE_RATE).item()
        return confidence > 0.5

    def is_misfire(self, transcript: str) -> bool:
        """判断识别结果是否为误触"""
        return len(transcript.strip()) < MIN_TRANSCRIPT_LENGTH

    def record_misfire(self) -> bool:
        """记录一次误触，返回是否达到提示阈值"""
        self.misfire_count += 1
        return self.misfire_count >= MISFIRE_MAX_COUNT

    def reset_misfire_count(self):
        self.misfire_count = 0

    def get_silence_threshold(self) -> float:
        return SILENCE_THRESHOLD_SECONDS
