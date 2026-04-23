"""
V0.7 后续修复 2：
  · 连读按钮无声 → 放弃 inline onclick（双引号冲突），改 data-speak + 事件委托
  · 连读音标标注 → 三行布局（原文 / 音标 / 说明），带中文 label
  · 标题平铺 → 去掉 max-height / overflow-y
"""
from pathlib import Path

PRACTICE_HTML = Path("static/practice.html")


# ── 引号 bug 绝迹 ───────────────────────────────────────────

def test_no_inline_onclick_for_drawer_speak():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    # 原来是 onclick="drawerSpeak(${JSON.stringify(...)},...)" — 会在浏览器里被 "..." 截断
    # 修复后不应再出现 inline onclick 调 drawerSpeak 的写法
    assert 'onclick="drawerSpeak(' not in src
    assert "onclick='drawerSpeak(" not in src


def test_buttons_use_data_speak():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    # 例句、同反义词、连读点三处都要带 data-speak
    assert "data-speak=" in src
    assert "data-speed=" in src
    # 还要带慢速按钮（连读用）
    assert 'data-speed="-25%"' in src


def test_delegated_click_handler_attached():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    # 文档级委托：closest('[data-speak]')
    assert "closest('[data-speak]')" in src
    # 且限定在 #explainDrawer 内
    assert "closest('#explainDrawer')" in src
    # 最终调用 drawerSpeak
    assert "drawerSpeak(text, speed)" in src


# ── 连读音标标注 ───────────────────────────────────────────

def test_liaison_three_row_layout():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    # 3 个中文 label：原文 / 音标 / 说明
    assert '<span class="liaison-label">原文</span>' in src
    assert '<span class="liaison-label">音标</span>' in src
    assert '<span class="liaison-label">说明</span>' in src
    # 音标 CSS 改得更醒目（accent 色、monospace、字号 13）
    ipa_css_start = src.index('.explain-body .liaison-ipa')
    ipa_css_end   = src.index('}', ipa_css_start)
    rule = src[ipa_css_start:ipa_css_end]
    assert "var(--accent)" in rule
    assert "monospace" in rule


def test_liaison_speak_buttons_placed_on_ipa_row():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    # 查找 liaison 渲染代码块
    start = src.index('Array.isArray(ex.liaison)')
    end   = src.index("'</div>');", start)
    block = src[start:end]
    # 音标行里有 🔊 和 🐢 两个按钮
    assert 'liaison-label">音标' in block
    assert '🔊' in block
    assert '🐢' in block


# ── 标题平铺 ────────────────────────────────────────────────

def test_title_no_max_height_no_internal_scroll():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    css_start = src.index('.explain-title')
    css_end   = src.index('}', css_start)
    rule = src[css_start:css_end]
    assert "max-height" not in rule
    assert "overflow-y" not in rule
    assert "word-break:break-word" in rule
