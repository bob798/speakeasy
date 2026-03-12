"""
前端 UI 测试：验证 Voice Settings API 交互逻辑正确
（UI 渲染验证需人工打开浏览器确认，此处测试 API 层的配合）
"""
import pytest
from fastapi.testclient import TestClient
from main import app
from app.models.db import UserSettings, engine
from sqlalchemy.orm import sessionmaker

TEST_USER = "test_user_v031_step5"
client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup():
    yield
    Session = sessionmaker(bind=engine)
    session = Session()
    session.query(UserSettings).filter_by(user_id=TEST_USER).delete()
    session.commit()
    session.close()


def test_settings_page_returns_200():
    """前端页面可访问"""
    resp = client.get("/")
    assert resp.status_code == 200


def test_settings_api_roundtrip_voice():
    """前端保存音色后，再次读取值一致"""
    client.post(f"/settings/{TEST_USER}", json={"voice": "bright"})
    resp = client.get(f"/settings/{TEST_USER}")
    assert resp.json()["voice"] == "bright"


def test_settings_api_roundtrip_speed():
    """前端保存语速后，再次读取值一致"""
    client.post(f"/settings/{TEST_USER}", json={"speed": "fast"})
    resp = client.get(f"/settings/{TEST_USER}")
    assert resp.json()["speed"] == "fast"


def test_settings_api_roundtrip_activation():
    """前端保存激活方式后，再次读取值一致"""
    client.post(f"/settings/{TEST_USER}", json={"activation": "hands_free"})
    resp = client.get(f"/settings/{TEST_USER}")
    assert resp.json()["activation"] == "hands_free"


def test_all_three_settings_saved_together():
    """三项同时保存"""
    client.post(f"/settings/{TEST_USER}", json={
        "voice": "steady",
        "speed": "slow",
        "activation": "hands_free"
    })
    resp = client.get(f"/settings/{TEST_USER}")
    data = resp.json()
    assert data["voice"] == "steady"
    assert data["speed"] == "slow"
    assert data["activation"] == "hands_free"
