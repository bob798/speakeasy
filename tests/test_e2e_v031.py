"""
e2e 测试 — V0.3.1 Voice Settings + Hands Free

覆盖两类入口：
  A. 用户主动操作（点击 ⚙️ → 切换选项）
  B. 页面刷新恢复（持久化状态是否自动生效）

运行前置条件：
  uvicorn main:app --reload  （另开终端）

运行命令：
  pytest tests/test_e2e_v031.py -v --headed
  pytest tests/test_e2e_v031.py -v          # headless
"""
import pytest
import requests as req
from playwright.sync_api import Page, expect
from sqlalchemy.orm import Session
from app.models.db import engine, UserSettings

BASE_URL = "http://localhost:8000"
TEST_USER = "test_user_v031_e2e"
LS_KEY = "speakeasy_uid"   # utils.js 中 getUserId() 使用的 localStorage key


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def cleanup_settings():
    """每个测试前后清理 user_settings 表，保证隔离"""
    _delete_settings()
    yield
    _delete_settings()


def _delete_settings():
    with Session(engine) as s:
        s.query(UserSettings).filter_by(user_id=TEST_USER).delete()
        s.commit()


def _open_app(page: Page) -> None:
    """
    打开应用，注入固定 userId 到 localStorage，再 reload 让 JS 读取。
    这样所有 /settings/{user_id} 请求都使用 TEST_USER，便于 API 断言和数据清理。
    """
    page.goto(BASE_URL)
    page.evaluate(f"localStorage.setItem('{LS_KEY}', '{TEST_USER}')")
    page.reload()
    page.wait_for_load_state("networkidle")


def _open_settings(page: Page) -> None:
    """点击 ⚙️ 打开 Voice Settings bottom sheet"""
    page.click("#settings-btn")
    expect(page.locator("#voice-settings-sheet")).to_be_visible()


def _set_via_api(updates: dict) -> None:
    """直接通过 REST API 写入 TEST_USER 的设置"""
    req.post(f"{BASE_URL}/settings/{TEST_USER}", json=updates)


# ── A 类入口：用户主动操作 ────────────────────────────────────────────────────

class TestSettingsSheetUI:
    """⚙️ 打开 / 关闭 / 选项切换"""

    def test_settings_btn_visible_in_header(self, page: Page):
        """Header 右侧存在 ⚙️ 按钮"""
        _open_app(page)
        expect(page.locator("#settings-btn")).to_be_visible()

    def test_sheet_opens_on_click(self, page: Page):
        """点击 ⚙️ → bottom sheet 出现"""
        _open_app(page)
        _open_settings(page)
        expect(page.locator("#voice-settings-sheet")).to_be_visible()

    def test_sheet_closes_on_x_button(self, page: Page):
        """点击 ✕ → sheet 消失"""
        _open_app(page)
        _open_settings(page)
        page.locator("#voice-settings-sheet button", has_text="✕").click()
        expect(page.locator("#voice-settings-sheet")).to_be_hidden()

    def test_sheet_closes_on_overlay_click(self, page: Page):
        """点击遮罩层 → sheet 消失"""
        _open_app(page)
        _open_settings(page)
        page.click("#voice-settings-overlay")
        expect(page.locator("#voice-settings-sheet")).to_be_hidden()

    def test_default_voice_warm_highlighted(self, page: Page):
        """初始状态 Warm 高亮"""
        _open_app(page)
        _open_settings(page)
        expect(page.locator("#voice-options .vs-option[data-value='warm']")).to_have_class(
            lambda c: "active" in c
        )

    def test_default_speed_normal_highlighted(self, page: Page):
        """初始状态 Normal 高亮"""
        _open_app(page)
        _open_settings(page)
        expect(page.locator("#speed-options .vs-option[data-value='normal']")).to_have_class(
            lambda c: "active" in c
        )

    def test_default_push_to_talk_checked(self, page: Page):
        """初始状态 Push to talk 有勾选"""
        _open_app(page)
        _open_settings(page)
        expect(page.locator("#check-push-to-talk")).to_have_text("✓")

    def test_select_voice_bright_highlights_bright(self, page: Page):
        """点击 Bright → Bright 高亮，Warm 不高亮，API 被调用"""
        _open_app(page)
        _open_settings(page)
        with page.expect_response(lambda r: "/settings/" in r.url and r.request.method == "POST"):
            page.locator("#voice-options .vs-option[data-value='bright']").click()
        expect(page.locator("#voice-options .vs-option[data-value='bright']")).to_have_class(
            lambda c: "active" in c
        )
        expect(page.locator("#voice-options .vs-option[data-value='warm']")).not_to_have_class(
            lambda c: "active" in c
        )

    def test_select_speed_slow_highlights_slow(self, page: Page):
        """点击 Slow → Slow 高亮，Normal 不高亮"""
        _open_app(page)
        _open_settings(page)
        with page.expect_response(lambda r: "/settings/" in r.url and r.request.method == "POST"):
            page.locator("#speed-options .vs-option[data-value='slow']").click()
        expect(page.locator("#speed-options .vs-option[data-value='slow']")).to_have_class(
            lambda c: "active" in c
        )

    def test_select_hands_free_shows_header_badge(self, page: Page):
        """切换 Hands free → Header 出现 '· Hands free 🟢' badge"""
        _open_app(page)
        _open_settings(page)
        with page.expect_response(lambda r: "/settings/" in r.url and r.request.method == "POST"):
            page.locator("text=Hands free").first.click()
        expect(page.locator("#hands-free-badge")).to_be_visible()

    def test_select_hands_free_shows_listening_indicator(self, page: Page):
        """
        切换 Hands free → Listening... 指示器出现
        （覆盖 V0.3.1 Bug 1 的回归验证：切换后必须真正启动监听）
        """
        _open_app(page)
        _open_settings(page)
        with page.expect_response(lambda r: "/settings/" in r.url and r.request.method == "POST"):
            page.locator("text=Hands free").first.click()
        expect(page.locator("#listening-indicator")).to_be_visible(timeout=5000)

    def test_switch_back_to_push_to_talk_hides_indicator(self, page: Page):
        """切换回 Push to talk → Listening... 消失，badge 消失"""
        _open_app(page)
        _open_settings(page)
        page.locator("text=Hands free").first.click()
        page.wait_for_timeout(500)
        with page.expect_response(lambda r: "/settings/" in r.url and r.request.method == "POST"):
            page.locator("text=Push to talk").first.click()
        expect(page.locator("#listening-indicator")).to_be_hidden()
        expect(page.locator("#hands-free-badge")).to_be_hidden()

    def test_settings_api_called_with_correct_value(self, page: Page):
        """切换 voice → POST 请求 body 包含正确的 voice 值"""
        _open_app(page)
        _open_settings(page)
        with page.expect_response(lambda r: "/settings/" in r.url and r.request.method == "POST") as resp_info:
            page.locator("#voice-options .vs-option[data-value='steady']").click()
        body = resp_info.value.request.post_data
        assert '"steady"' in body


# ── B 类入口：页面刷新恢复 ────────────────────────────────────────────────────

class TestSettingsPersistence:
    """
    持久化状态必须在「页面加载」时自动恢复。
    通过 API 预写入设置，再加载页面，验证 UI 正确反映。
    """

    def test_voice_bright_persists_after_reload(self, page: Page):
        """预设 voice=bright → 刷新 → Bright 仍高亮"""
        _set_via_api({"voice": "bright"})
        _open_app(page)
        _open_settings(page)
        expect(page.locator("#voice-options .vs-option[data-value='bright']")).to_have_class(
            lambda c: "active" in c
        )

    def test_speed_fast_persists_after_reload(self, page: Page):
        """预设 speed=fast → 刷新 → Fast 仍高亮"""
        _set_via_api({"speed": "fast"})
        _open_app(page)
        _open_settings(page)
        expect(page.locator("#speed-options .vs-option[data-value='fast']")).to_have_class(
            lambda c: "active" in c
        )

    def test_hands_free_badge_auto_appears_on_reload(self, page: Page):
        """
        预设 activation=hands_free → 刷新 → badge 自动出现
        （覆盖 V0.3.1 Bug 2 的回归验证）
        """
        _set_via_api({"activation": "hands_free"})
        _open_app(page)
        page.wait_for_timeout(1000)  # 等 loadSettings() 完成
        expect(page.locator("#hands-free-badge")).to_be_visible()

    def test_listening_indicator_auto_starts_on_reload(self, page: Page):
        """
        预设 activation=hands_free → 刷新 → Listening... 自动出现
        （覆盖 V0.3.1 Bug 2 的回归验证）
        """
        _set_via_api({"activation": "hands_free"})
        _open_app(page)
        page.wait_for_timeout(1500)  # 等 initSTT() + loadSettings() + startHandsFreeMode()
        expect(page.locator("#listening-indicator")).to_be_visible(timeout=5000)

    def test_push_to_talk_no_listening_on_reload(self, page: Page):
        """预设 activation=push_to_talk → 刷新 → Listening... 不出现"""
        _set_via_api({"activation": "push_to_talk"})
        _open_app(page)
        page.wait_for_timeout(1000)
        expect(page.locator("#listening-indicator")).to_be_hidden()

    def test_hands_free_check_mark_in_settings_on_reload(self, page: Page):
        """预设 activation=hands_free → 刷新 → 打开设置面板 → 勾选在 Hands free"""
        _set_via_api({"activation": "hands_free"})
        _open_app(page)
        _open_settings(page)
        expect(page.locator("#check-hands-free")).to_have_text("✓")
        expect(page.locator("#check-push-to-talk")).to_have_text("")
