"""
V0.7 Step 7 — drawer 点读按钮（静态断言）
"""
from pathlib import Path

PRACTICE_HTML = Path("static/practice.html")


def test_title_speak_button_present():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    assert 'id="explainTitleSpeak"' in src
    assert 'drawerSpeakTitle()' in src


def test_drawer_speak_helper_defined():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    assert 'async function drawerSpeak(' in src
    assert 'function drawerSpeakTitle()' in src
    # 调 /practice/tts
    start = src.index('async function drawerSpeak(')
    end = src.index('function drawerSpeakTitle', start)
    body = src[start:end]
    assert "'/practice/tts'" in body
    assert 'drawerSpeakAudio.play' in body
    assert 'drawerSpeakAudio.pause' in body   # 停旧音频


def test_examples_get_mini_speak():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    assert 'class="mini-speak"' in src
    # 例句按钮调 drawerSpeak
    assert 'drawerSpeak(' in src


def test_synonyms_are_speakable():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    assert 'class="speakable"' in src
    # wordSpan helper 内应该调 drawerSpeak
    assert 'const wordSpan =' in src


def test_close_stops_drawer_audio():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    cstart = src.index('function closeExplain()')
    cend   = src.index('\n}\n', cstart) + 2
    block  = src[cstart:cend]
    assert 'drawerSpeakAudio' in block
    assert 'pause()' in block


def test_mini_speak_has_hover_css():
    src = PRACTICE_HTML.read_text(encoding="utf-8")
    # hover 样式
    assert '.explain-body .example:hover .mini-speak' in src
    assert '.explain-body .example .mini-speak' in src
