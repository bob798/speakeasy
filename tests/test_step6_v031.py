import pytest
from unittest.mock import patch, MagicMock
from app.services.vad_service import VADService
from app.models.db import UserSettings, engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from main import app

TEST_USER = "test_user_v031_step6"
client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup():
    yield
    Session = sessionmaker(bind=engine)
    session = Session()
    session.query(UserSettings).filter_by(user_id=TEST_USER).delete()
    session.commit()
    session.close()


def test_activation_switches_to_hands_free():
    resp = client.post(f"/settings/{TEST_USER}", json={"activation": "hands_free"})
    assert resp.status_code == 200
    assert resp.json()["settings"]["activation"] == "hands_free"


def test_activation_switches_back_to_push_to_talk():
    client.post(f"/settings/{TEST_USER}", json={"activation": "hands_free"})
    resp = client.post(f"/settings/{TEST_USER}", json={"activation": "push_to_talk"})
    assert resp.json()["settings"]["activation"] == "push_to_talk"


def test_misfire_threshold_triggers_at_3():
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        assert vad.record_misfire() == False
        assert vad.record_misfire() == False
        result = vad.record_misfire()
        assert result == True  # 第3次触发提示


def test_misfire_does_not_auto_switch_mode():
    """误触达到阈值后，activation 设置不自动改变"""
    client.post(f"/settings/{TEST_USER}", json={"activation": "hands_free"})
    # 模拟3次误触
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        for _ in range(3):
            vad.record_misfire()
    # 验证 activation 仍为 hands_free
    resp = client.get(f"/settings/{TEST_USER}")
    assert resp.json()["activation"] == "hands_free"


def test_chinese_english_mixed_input_passes_through():
    """中英混合输入不被过滤"""
    with patch("app.services.vad_service.load_silero_vad"):
        vad = VADService()
        mixed_text = "这个 deadline 能不能 push 一下"
        assert vad.is_misfire(mixed_text) == False
