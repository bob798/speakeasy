"""V0.11 #6 · 连读知识库单测"""
import pytest

from app.knowledge import load_liaison_patterns, liaison_prompt_block


def test_kb_loads():
    kb = load_liaison_patterns()
    assert kb["version"] >= 1
    assert len(kb["patterns"]) >= 8


def test_kb_pattern_shape():
    """每条 pattern 必须有完整字段"""
    required = {"pattern_id", "name", "trigger", "plain", "feel", "examples", "tip"}
    kb = load_liaison_patterns()
    for p in kb["patterns"]:
        missing = required - p.keys()
        assert not missing, f"{p.get('pattern_id')} 缺字段: {missing}"
        assert isinstance(p["examples"], list)
        assert len(p["examples"]) >= 2


def test_pattern_ids_unique():
    kb = load_liaison_patterns()
    ids = [p["pattern_id"] for p in kb["patterns"]]
    assert len(ids) == len(set(ids))


def test_prompt_block_contains_all_patterns():
    block = liaison_prompt_block()
    kb = load_liaison_patterns()
    for p in kb["patterns"]:
        assert p["pattern_id"] in block, f"{p['pattern_id']} 未出现在 prompt block"


def test_prompt_block_uses_plain_language():
    """KB 应用「听感」/「听起来像」类通俗描述，不只是「元音 + 辅音」"""
    block = liaison_prompt_block()
    assert "听感" in block
    assert "听起来" in block or "听感" in block


def test_explain_prompt_formats_with_kb():
    """EXPLAIN_SENTENCE_PROMPT 必须能 format(cefr_level=..., liaison_kb=...)"""
    from app.prompts.explain import EXPLAIN_SENTENCE_PROMPT
    out = EXPLAIN_SENTENCE_PROMPT.format(cefr_level="B1", liaison_kb=liaison_prompt_block())
    assert "B1" in out
    assert "听感" in out
    assert "pattern_id" in out


def test_schema_version_bumped():
    """V0.11 #6 should bump _SCHEMA_VERSION to invalidate old caches"""
    from app.services.explain_service import _SCHEMA_VERSION
    assert _SCHEMA_VERSION >= 6
