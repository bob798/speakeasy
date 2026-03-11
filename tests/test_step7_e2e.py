import pytest
from playwright.sync_api import sync_playwright
import requests
import json

BASE_URL = "http://localhost:8000"
TEST_USER = "test_user_v02b_step7"
TEST_SESSION = "test_session_step7"


def seed_review():
    """直接往数据库插入一条含错误的 session_review，跳过真实 LLM"""
    from sqlalchemy.orm import Session
    from app.models.db import engine, SessionReview, GrammarCard
    from fsrs import Card

    with Session(engine) as s:
        s.query(SessionReview).filter_by(session_id=TEST_SESSION).delete()
        s.query(GrammarCard).filter_by(user_id=TEST_USER).delete()
        review = SessionReview(
            session_id=TEST_SESSION,
            user_id=TEST_USER,
            errors=json.dumps([{
                "key": "go_went",
                "original": "I go yesterday",
                "corrected": "I went yesterday",
                "explanation_zh": "go → went（不规则动词）",
                "count": 2, "confidence": 0.9
            }]),
            highlights=json.dumps([{
                "original": "The meeting totally threw me off",
                "praise_zh": "throw sb off 是很地道的口语！"
            }]),
            stats=json.dumps({"turns": 14, "duration_seconds": 480}),
        )
        s.add(review)
        gc = GrammarCard(
            user_id=TEST_USER, key="go_went",
            content="常用 go 代替 went",
            status="active", frequency=2,
            fsrs_card_data=json.dumps(Card().to_dict()),
        )
        s.add(gc)
        s.commit()


def cleanup():
    from sqlalchemy.orm import Session
    from app.models.db import engine, SessionReview, GrammarCard
    with Session(engine) as s:
        s.query(SessionReview).filter_by(session_id=TEST_SESSION).delete()
        s.query(GrammarCard).filter_by(user_id=TEST_USER).delete()
        s.commit()


@pytest.fixture(autouse=True)
def setup():
    seed_review()
    yield
    cleanup()


def test_review_card_renders(page):
    # 打开复盘页（带 session_id 参数，或通过 UI 导航）
    page.goto(f"{BASE_URL}/review?session_id={TEST_SESSION}&user_id={TEST_USER}")
    page.wait_for_selector("text=查看详情", timeout=10000)

    assert page.locator("text=今天聊了").count() > 0
    assert page.locator("text=可以改进").count() > 0


def test_error_detail_expandable(page):
    page.goto(f"{BASE_URL}/review?session_id={TEST_SESSION}&user_id={TEST_USER}")
    page.wait_for_selector("text=查看详情")
    page.click("text=查看详情")
    assert page.locator("text=I go yesterday").count() > 0
    assert page.locator("text=I went yesterday").count() > 0


def test_good_button_calls_api(page):
    page.goto(f"{BASE_URL}/review?session_id={TEST_SESSION}&user_id={TEST_USER}")
    page.wait_for_selector("text=查看详情")
    page.click("text=查看详情")
    with page.expect_response(lambda r: "/rate" in r.url) as resp_info:
        page.click("text=我记住了")
    assert resp_info.value.status == 200


def test_highlights_separate_from_errors(page):
    page.goto(f"{BASE_URL}/review?session_id={TEST_SESSION}&user_id={TEST_USER}")
    page.wait_for_selector("text=今天用得很地道")
    errors_section = page.locator("[data-section='errors']")
    highlights_section = page.locator("[data-section='highlights']")
    assert errors_section.count() > 0
    assert highlights_section.count() > 0
    # 两个 section 是兄弟元素，不嵌套
    assert errors_section.locator("text=throw sb off").count() == 0


def test_tip_fallback_renders(page):
    # 插入一条 type=tip 场景（用不存在的 session）
    page.goto(f"{BASE_URL}/review?session_id=nonexistent&user_id={TEST_USER}")
    page.wait_for_selector("text=今日一句", timeout=15000)
    assert page.locator("text=今日一句").count() > 0
