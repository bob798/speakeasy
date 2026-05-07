"""知识库 · V0.11 #6"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

_KB_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def load_liaison_patterns() -> Dict:
    """读取 liaison_patterns.json · 缓存"""
    p = _KB_DIR / "liaison_patterns.json"
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def liaison_prompt_block(max_examples_per_pattern: int = 2) -> str:
    """生成插入 EXPLAIN_SENTENCE_PROMPT 的连读 KB 块（紧凑可读）"""
    kb = load_liaison_patterns()
    lines = ["连读模式知识库（解释时必须用「听感比喻」+ 通俗类比，不要只说「元音 + 元音」）："]
    for i, p in enumerate(kb["patterns"], 1):
        examples = p.get("examples", [])[:max_examples_per_pattern]
        ex_str = " / ".join(examples) if examples else ""
        lines.append(
            f"{i}. {p['name']} [pattern_id={p['pattern_id']}]\n"
            f"   通俗解释：{p['plain']}\n"
            f"   听感：{p['feel']}\n"
            f"   例：{ex_str}"
        )
    lines.append(
        "\n生成 liaison 数组时，每条 tip 必须用上面 KB 的「通俗解释 / 听感」语言风格。"
        "可在 tip 末尾用方括号标注 [pattern_id]，便于前端定位 KB 条目，例：「t 夹在元音中间软化成 d [t_flap]」。"
    )
    return "\n".join(lines)
