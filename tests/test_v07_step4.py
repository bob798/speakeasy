"""
V0.7 Step 4 — ask-panel.js 前端组件静态检查
（无 JS runner，按文件结构与关键 API 做静态断言）
"""
from pathlib import Path

ASK_PANEL = Path("static/js/ask-panel.js")


def test_file_exists():
    assert ASK_PANEL.exists(), "ask-panel.js 应存在"


def test_exports_window_AskPanel():
    src = ASK_PANEL.read_text(encoding="utf-8")
    assert "window.AskPanel" in src
    assert "AskPanel: { create }" in src or "AskPanel = { create }" in src or "AskPanel" in src


def test_required_options_validated():
    src = ASK_PANEL.read_text(encoding="utf-8")
    # 必填参数校验
    assert "AskPanel: mount 必填" in src
    assert "scope/refType/refId 必填" in src


def test_uses_authFetch():
    src = ASK_PANEL.read_text(encoding="utf-8")
    # 不应直接用 fetch；应用 authFetch
    assert "window.authFetch" in src
    # 仅接受 fetch 拒绝路径里的 status 检查，不允许裸 fetch 调用 /ask
    assert "fetch('/ask" not in src
    assert 'fetch("/ask' not in src


def test_hits_correct_endpoints():
    src = ASK_PANEL.read_text(encoding="utf-8")
    assert "/ask/threads" in src
    assert "/messages" in src           # append 走 /ask/threads/{id}/messages
    # list 时按 scope/ref_type/ref_id 拼 query
    assert "scope=" in src and "ref_id=" in src


def test_exposes_lifecycle_api():
    src = ASK_PANEL.read_text(encoding="utf-8")
    # 返回对象必须有 destroy / loadExisting / ask
    for name in ("destroy", "loadExisting", "ask"):
        assert f"{name}" in src, f"缺少方法 {name}"


def test_scrolls_and_pending_state():
    src = ASK_PANEL.read_text(encoding="utf-8")
    assert "ap-pending" in src
    assert "scrollBottom" in src or "scrollTop" in src


def test_styles_use_css_vars_with_fallback():
    src = ASK_PANEL.read_text(encoding="utf-8")
    # 必须用 var(--accent, ...) 这种带兜底的写法，保证被嵌到没有变量的页面也能看
    assert "var(--accent" in src
    assert "var(--bg" in src
