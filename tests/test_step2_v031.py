import pytest
from fastapi.testclient import TestClient
from main import app
from app.models.db import Base, UserSettings, engine
from sqlalchemy.orm import sessionmaker

TEST_USER = "test_user_v031_step2"
client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup():
    yield
    Session = sessionmaker(bind=engine)
    session = Session()
    session.query(UserSettings).filter_by(user_id=TEST_USER).delete()
    session.commit()
    session.close()


def test_get_settings_returns_defaults_for_new_user():
    resp = client.get(f"/settings/{TEST_USER}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["voice"] == "warm"
    assert data["speed"] == "normal"
    assert data["activation"] == "push_to_talk"


def test_post_settings_updates_voice():
    resp = client.post(f"/settings/{TEST_USER}", json={"voice": "steady"})
    assert resp.status_code == 200
    assert resp.json()["settings"]["voice"] == "steady"


def test_post_settings_updates_speed():
    resp = client.post(f"/settings/{TEST_USER}", json={"speed": "slow"})
    assert resp.status_code == 200
    assert resp.json()["settings"]["speed"] == "slow"


def test_post_settings_updates_activation():
    resp = client.post(f"/settings/{TEST_USER}", json={"activation": "hands_free"})
    assert resp.status_code == 200
    assert resp.json()["settings"]["activation"] == "hands_free"


def test_post_settings_partial_update_preserves_other_fields():
    # 先设置完整状态
    client.post(f"/settings/{TEST_USER}", json={
        "voice": "bright", "speed": "fast", "activation": "hands_free"
    })
    # 只更新 speed
    resp = client.post(f"/settings/{TEST_USER}", json={"speed": "slow"})
    data = resp.json()["settings"]
    assert data["voice"] == "bright"           # 保持不变
    assert data["speed"] == "slow"             # 已更新
    assert data["activation"] == "hands_free"  # 保持不变


def test_post_settings_rejects_invalid_voice():
    resp = client.post(f"/settings/{TEST_USER}", json={"voice": "invalid_voice"})
    assert resp.status_code == 422


def test_settings_persist_across_requests():
    client.post(f"/settings/{TEST_USER}", json={"voice": "bright", "speed": "fast"})
    resp = client.get(f"/settings/{TEST_USER}")
    data = resp.json()
    assert data["voice"] == "bright"
    assert data["speed"] == "fast"
