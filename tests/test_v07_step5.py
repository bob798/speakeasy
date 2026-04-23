"""
V0.7 Step 5 — practice drawer 接入 ask-panel（静态断言）
"""
from pathlib import Path

PRACTICE_HTML = Path("static/practice.html")


def test_ask_panel_script_included():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    assert '/static/js/ask-panel.js' in src


def test_ask_button_present_in_drawer_footer():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    # 按钮本身 + 文案
    assert 'id="explainAskBtn"' in src
    assert 'toggleExplainAsk()' in src
    assert '💬 追问' in src


def test_ask_container_present():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    assert 'id="explainAskContainer"' in src
    assert 'class="explain-ask"' in src


def test_toggle_creates_panel_with_scope_and_context():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    assert "window.AskPanel.create" in src
    assert "scope: 'practice_explain'" in src
    assert "refType: 'explanation'" in src
    # 上下文里带 kind/text/cefr_level/explanation 等
    for key in ("kind:", "text:", "cefr_level:", "explanation,"):
        assert key in src, f"context 缺 {key}"


def test_close_destroys_panel():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    # 用下游锚点限定闭包区间（函数末尾 }）
    close_start = src.index("function closeExplain()")
    # 找到函数体结束的 "\n}\n"
    close_end = src.index("\n}\n", close_start) + 2
    block = src[close_start:close_end]
    assert "destroyExplainAsk" in block


def test_destroy_calls_panel_destroy_and_resets_state():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    # 以下游锚点（toggleExplainAsk 定义）限定搜索区间
    dstart = src.index("function destroyExplainAsk()")
    dend   = src.index("function toggleExplainAsk()", dstart)
    block  = src[dstart:dend]
    assert "explainAskPanel.destroy" in block
    assert "explainAskPanel = null" in block
    assert "with-ask" in block   # 清掉 drawer class


def test_toggle_button_text_switches():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    assert "💬 收起追问" in src
