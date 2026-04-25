"""
V0.3 Step 6 — Level 评估引导弹窗（前端 HTML 结构 + API 验证）
user_id: test_user_v03_s6
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from main import app
from app.models.db import engine, Base, UserProfile

TEST_USER = "test_user_v03_s6"


@pytest.fixture(autouse=True)
def cleanup():
    Base.metadata.create_all(engine)
    yield
    with OrmSession(engine) as s:
        s.query(UserProfile).filter_by(user_id=TEST_USER).delete()
        s.commit()


@pytest.fixture
def client():
    return TestClient(app)


# ── index.html 包含引导弹窗结构 ──────────────────────────────────────────────

# V0.8 迁到 /legacy/ (Pass 3 B3) · SPA 灰度期保留老版路径做回滚
def test_index_has_assessment_banner(client):
    r = client.get("/legacy/")
    assert "assessment-banner" in r.text


def test_index_assessment_banner_has_dismiss(client):
    r = client.get("/legacy/")
    assert "dismissAssessmentBanner" in r.text


def test_index_assessment_links_to_memory(client):
    r = client.get("/legacy/")
    # The banner has a link to /memory
    assert "/memory" in r.text


# ── memory.html 包含重新评估按钮 ─────────────────────────────────────────────

def test_memory_has_reassess_button(client):
    r = client.get("/legacy/memory")
    assert "reassess-btn" in r.text or "重新评估" in r.text


def test_memory_has_open_assessment(client):
    r = client.get("/legacy/memory")
    assert "openAssessment" in r.text


# ── assessment API 端到端验证 ─────────────────────────────────────────────────

def test_assessment_full_flow(client):
    """完整流程：评估 → profile 保存 → GET profile 返回 cefr_level"""
    # 1. 初始时无 profile
    r = client.get(f"/memory/profile?user_id={TEST_USER}")
    assert r.json()["cefr_level"] is None

    # 2. 提交评估
    r = client.post("/assessment/self", json={
        "user_id": TEST_USER,
        "answers": ["can", "can", "can", "partially", "cannot"],  # 7 → B2
    })
    assert r.status_code == 200
    assert r.json()["cefr_level"] == "B2"

    # 3. GET profile 返回已保存的 cefr_level
    r = client.get(f"/memory/profile?user_id={TEST_USER}")
    assert r.json()["cefr_level"] == "B2"


def test_reassessment_updates_level(client):
    """重新评估覆盖原有水平"""
    # 初始 B1
    client.post("/assessment/self", json={
        "user_id": TEST_USER,
        "answers": ["can", "can", "can", "cannot", "cannot"],  # 6 → B1
    })
    # 重新评估 → C1
    r = client.post("/assessment/self", json={
        "user_id": TEST_USER,
        "answers": ["can", "can", "can", "can", "can"],  # 10 → C1
    })
    assert r.json()["cefr_level"] == "C1"

    # 验证 DB 已更新
    r = client.get(f"/memory/profile?user_id={TEST_USER}")
    assert r.json()["cefr_level"] == "C1"


print("✅ Step 6 完成")
