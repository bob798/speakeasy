import pytest
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8000"


def test_action_bar_visible_on_hover(page):
    page.goto(BASE_URL)
    # 触发一条 AI 回复
    page.fill("[data-testid='chat-input']", "Tell me something interesting.")
    page.click("[data-testid='send-button']")
    # Wait for completed AI bubble (not loading-dots)
    page.wait_for_selector("[data-testid='ai-bubble']", timeout=30000)

    bubble = page.locator("[data-testid='ai-bubble']").first
    action_bar = page.locator("[data-testid='action-bar']").first

    # 默认半透明（不 hover 时）
    opacity_before = action_bar.evaluate("el => window.getComputedStyle(el).opacity")
    assert float(opacity_before) < 1.0

    bubble.hover()
    # Wait for CSS transition to complete (0.15s + buffer)
    page.wait_for_timeout(300)
    opacity_after = action_bar.evaluate("el => window.getComputedStyle(el).opacity")
    assert float(opacity_after) == 1.0


def test_explain_button_sends_message(page):
    page.goto(BASE_URL)
    page.fill("[data-testid='chat-input']", "The deadline is really looming.")
    page.click("[data-testid='send-button']")
    # Wait for first completed AI bubble
    page.wait_for_selector("[data-testid='ai-bubble']", timeout=30000)

    page.locator("[data-testid='ai-bubble']").first.hover()
    page.locator("[data-testid='explain-button']").first.click()

    # 自动发送后等待第二条 AI 回复（有内容）
    page.wait_for_function(
        "document.querySelectorAll('[data-testid=\"ai-bubble\"]').length >= 2",
        timeout=30000
    )
    # Wait for the second bubble to have content
    page.wait_for_timeout(500)
    last_bubble = page.locator("[data-testid='ai-bubble']").last.inner_text()
    # Alex 的回复应该有内容
    assert len(last_bubble) > 10
