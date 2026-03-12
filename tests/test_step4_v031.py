import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from app.services.vad_service import VADService


def test_vad_service_initializes():
    with patch("app.services.vad_service.load_silero_vad") as mock_load:
        mock_load.return_value = MagicMock()
        vad = VADService()
        assert vad.model is not None
        assert vad.misfire_count == 0


def test_is_misfire_empty_transcript():
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        assert vad.is_misfire("") == True
        assert vad.is_misfire(" ") == True


def test_is_misfire_single_char():
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        assert vad.is_misfire("a") == True


def test_is_not_misfire_valid_transcript():
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        assert vad.is_misfire("ok") == False
        assert vad.is_misfire("这个 deadline") == False


def test_misfire_count_accumulates():
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        assert vad.record_misfire() == False  # 1次，未达阈值
        assert vad.record_misfire() == False  # 2次，未达阈值
        assert vad.record_misfire() == True   # 3次，达到阈值


def test_misfire_count_resets():
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        vad.record_misfire()
        vad.record_misfire()
        vad.reset_misfire_count()
        assert vad.misfire_count == 0


def test_silence_threshold_is_2_seconds():
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        assert vad.get_silence_threshold() == 2.0
