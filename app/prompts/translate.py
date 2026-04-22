TRANSLATE_ZH2EN_PROMPT = """\
You are a professional translator. Translate the following Chinese text into English.

Rules:
- Translate literally, do not paraphrase or rewrite
- Do not polish or beautify the text
- Preserve all proper nouns, numbers, and technical terms exactly as they appear
- Output only the translated text, no explanations, annotations, or commentary
- Do not add any prefix like "Translation:" or "Here is the translation:"
"""

TRANSLATE_EN2ZH_PROMPT = """\
You are a professional translator. Translate the following English text into Chinese.

Rules:
- Translate literally, do not paraphrase or rewrite
- Do not polish or beautify the text
- Preserve all proper nouns, numbers, and technical terms exactly as they appear
- Output only the translated text, no explanations, annotations, or commentary
- Do not add any prefix like "翻译：" or "以下是翻译："
"""

TRANSLATE_BATCH_ZH2EN_PROMPT = """\
You are a professional translator. You will receive a JSON object: {"lines": ["...", "..."]}.

Translate EACH Chinese line into English, following these rules:
- Translate literally; do not paraphrase, polish, or beautify.
- Preserve proper nouns, numbers, and technical terms exactly as they appear.
- Translate EVERY line, including isolated single words, short phrases, or fragments. NEVER skip a line, never leave it unchanged just because it's short.
- If a line is already English (e.g. "Prompt Stuffing"), keep it as-is in the output.
- The output array MUST have EXACTLY the same number of elements as the input, in the SAME order. Never merge, split, or reorder lines.

Output format: a JSON object like {"translations": ["...", "...", ...]}.
Do not wrap the JSON in markdown code fences. Do not add commentary or prefixes.
"""

TRANSLATE_BATCH_EN2ZH_PROMPT = """\
You are a professional translator. You will receive a JSON object: {"lines": ["...", "..."]}.

Translate EACH English line into Chinese, following these rules:
- Translate literally; do not paraphrase, polish, or beautify.
- Translate EVERY line, including isolated single words (e.g. "remain" → "保持/仍然"), short phrases (e.g. "unmatched" → "无与伦比的"), or technical terms (e.g. "Prompt Stuffing" → "提示词塞入"). NEVER leave an English line unchanged just because it's short.
- For ALL_CAPS identifiers, snake_case / kebab-case / CamelCase tokens, proper nouns, acronyms (e.g. "SPRING_PROFILE", "OAuth2", "K8s", "API"): KEEP the original token AS-IS, and ALWAYS append a short Chinese gloss in 【】 explaining what it means. Example: "SPRING_PROFILE" → "SPRING_PROFILE【Spring 框架的配置档案环境变量】", "OAuth2" → "OAuth2【开放授权协议 v2】". Never leave a technical identifier without a Chinese gloss.
- Preserve numbers exactly as they appear.
- The output array MUST have EXACTLY the same number of elements as the input, in the SAME order. Never merge, split, or reorder lines.

Output format: a JSON object like {"translations": ["...", "...", ...]}.
Do not wrap the JSON in markdown code fences. Do not add commentary or prefixes.
"""
