"""
BUG-004 修复验证：页面加载只返回偏好，API 不携带自动启动指令
"""
import pytest
from fastapi.testclient import TestClient
from main import app
from app.models.db import UserSettings, engine
from sqlalchemy.orm import sessionmaker

TEST_USER = "test_user_v031_step5_bugfix"
client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup():
    yield
    Session = sessionmaker(bind=engine)
    session = Session()
    session.query(UserSettings).filter_by(user_id=TEST_USER).delete()
    session.commit()
    session.close()


def test_hands_free_preference_persists_without_auto_activating():
    """
    设置 hands_free 后，再次读取仍是 hands_free，
    但这只是偏好，不代表 VAD 已启动（VAD 启动是前端行为，
    此处验证 API 层不返回任何"自动启动"指令）
    """
    client.post(f"/settings/{TEST_USER}", json={"activation": "hands_free"})
    resp = client.get(f"/settings/{TEST_USER}")
    data = resp.json()
    assert data["activation"] == "hands_free"
    # API 响应中不包含任何 auto_start 字段
    assert "auto_start" not in data
    assert "vad_active" not in data


def test_page_load_settings_only_returns_preference():
    """页面加载读取设置，返回偏好而非活跃状态"""
    client.post(f"/settings/{TEST_USER}", json={"activation": "hands_free"})
    resp = client.get(f"/settings/{TEST_USER}")
    # 只返回三个偏好字段
    data = resp.json()
    assert set(data.keys()) == {"voice", "speed", "activation"}
