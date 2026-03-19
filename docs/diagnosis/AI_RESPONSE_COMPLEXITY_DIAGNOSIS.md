# AI 回复复杂度诊断报告

> 生成日期：2026-03-16
> 问题描述：AI（Alex）回复内容对普通用户（中国职场英语学习者）过于复杂，导致体验挫败

---

## 一、根因分析

### 根因 1：System Prompt 缺少词汇难度约束（最关键）

**文件**：`app/prompts/system.py`

System Prompt 对回复长度有约束（≤3 句），但**完全没有规定用词难度**：

- 没有明确目标用户英语水平（A2/B1/B2）
- 没有要求回避高级习语、复杂从句、低频词汇
- 模型的默认行为 = 母语者对母语者的表达方式

### 根因 2：MAX_TOKENS = 1024 过于宽松

**文件**：`app/config.py:11`

```python
MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "1024"))
```

3 句话最多需要 60-80 tokens。1024 tokens 的空间让模型每句话都可以写得异常复杂，即便遵守了"3句话"规则，单句复杂度仍不受控。

### 根因 3：流式接口绕过记忆注入（Bug）

**文件**：`app/routers/chat.py:97`

```
/chat        → 调用 build_system_prompt() → 注入 grammar_cards ✅
/chat/stream → 直接调用 client.chat_stream() → 硬编码 SYSTEM_PROMPT ❌
```

流式路径从未走过 `build_system_prompt()`，memory_service 对流式响应完全无效。

### 根因 4：系统无 Level 概念，无法分级（产品设计缺失）

整个系统没有"用户英语水平"字段。V0.3 规划了 Level 评估，但当前缺少默认兜底策略——系统在不知道用户水平的情况下，默认用母语者水平回复。

---

## 二、现有测试的覆盖缺口

`tests/test_alex_behavior.py` 已有 D1-D4 四个维度，但缺少：

| 缺失维度 | 具体覆盖点 |
|---|---|
| D5 词汇难度 | 回复不含 B2+ 高频词汇（LLM-as-Judge） |
| D5 句式复杂度 | 不含多重从句、倒装句 |
| D5 一致性 | 所有场景均 ≤3 句（含历史对话） |
| D5 理解可达性 | 对初学者特征输入，回复本身可被 B1 用户读懂 |

---

## 三、全局视角：产品价值链断裂点

```
产品承诺：「和朋友聊天，英语悄悄变好」
    ↓
用户实际画像：中国职场人，大多 B1 及以下
    ↓
当前 AI 输出：母语者水平的表达（缺少约束）
    ↓
用户感受：看不懂回复 → 体验挫败 → 流失
```

这不是单点 Bug，而是**产品设计缺失**：V0.3 的 Level 评估是正确方向，但当前缺少默认策略作为兜底。

---

## 四、解决方案（按优先级）

### P0-A：System Prompt 加词汇难度约束

**目标**：立竿见影，无需部署新功能。

在 `app/prompts/system.py` 的 Rule 4 之后增加：

```
5. Language level — default to B1, adapt upward only if user clearly shows higher ability
   - Use common everyday words (top 3000 English vocabulary)
   - One idea per sentence — short is clear
   - Avoid: advanced idioms, rare phrasal verbs, complex subordinate clauses
   - If you use a harder word, immediately rephrase it simply in the same sentence
   - Never use jargon or academic vocabulary
```

**验收**：LLM-as-Judge 评估 10 条测试回复的词汇难度均在 B1 以下。

---

### P0-B：降低 MAX_TOKENS 至 300

**目标**：从物理层面约束回复的可能复杂度。

**改动**：`app/config.py:11`

```python
# 改前
MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "1024"))

# 改后
MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "300"))
```

**注意**：review_service 和 memory_service 的 LLM 调用使用自己的 max_tokens 参数（如 1000），不受此全局变量影响，无需改动。

**验收**：重启服务后，/chat 接口回复平均 token 数 < 100。

---

### P1：修复流式接口绕过 build_system_prompt() 的 Bug

**目标**：让流式接口与非流式接口行为对齐，grammar_cards 记忆对流式生效。

**改动**：`app/routers/chat.py:83-119`

```python
@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    if req.user_id and req.session_id:
        await upsert_session(db, req.session_id, req.user_id)
        await save_message(db, req.session_id, "user", req.message)
        await db.commit()

    # ✅ 新增：与 /chat 对齐，注入 grammar_cards 记忆
    system_prompt = await build_system_prompt(req.user_id or "")

    client     = chat_service.get_client()
    history    = [msg.model_dump() for msg in req.history]
    session_id = req.session_id

    async def generate():
        full = []
        try:
            # ✅ 改为传入完整 messages（含注入后的 system_prompt）
            messages = (
                [{"role": "system", "content": system_prompt}]
                + history
                + [{"role": "user", "content": req.message}]
            )
            async for chunk in client.chat_stream_messages(messages):
                ...
```

**注意**：需要在 `BaseModelClient` 增加 `chat_stream_messages(messages)` 方法，接收完整 messages 列表，与 `complete()` 的接口设计保持一致。

**验收**：新增 `tests/test_step_stream_memory.py`，验证流式接口的 system_prompt 包含 grammar_cards 内容。

---

### P2：新增 D5 测试维度（词汇复杂度）

**目标**：建立可量化的"回复难度"自动评估，防止回归。

**改动**：在 `tests/test_alex_behavior.py` 增加 `TestD5VocabularyLevel` 类：

```python
JUDGE_D5 = """
你是一个英语教学产品的质量评估员。

评估 Alex 的回复是否适合英语水平为 B1（中级，能理解常见话题的基本英语）的用户阅读理解。

Alex 回复：{alex_response}

评估标准：
- 词汇：主要使用 3000 高频词，避免生僻词/学术词
- 句式：每句一个主要信息，无复杂从句嵌套
- 习语：不使用对中级学习者陌生的固定表达

返回 JSON：
{{
  "accessible_b1": true或false,
  "difficult_words": ["列出", "发现的难词"],
  "complex_structures": ["列出复杂句式"],
  "reason": "一句话总结"
}}
只返回 JSON。
"""
```

**覆盖用例**：

| 用例 ID | 场景 | 验收标准 |
|---|---|---|
| D5-TC001 | 普通日常对话输入 | accessible_b1 = true |
| D5-TC002 | 用户展示高水平英语 | Alex 可适度提升，但仍不超过 B2 |
| D5-TC003 | 所有场景的句子数 | response.count('.') + '?' + '!' ≤ 3 |
| D5-TC004 | 情绪类输入 | 词汇更简单，避免复杂安慰措辞 |

---

## 五、如何避免此类问题再次出现（流程改进）

### 5.1 Prompt 变更必须经过行为测试

当前流程：写 Prompt → 主观感觉对 → 上线

改进流程：写 Prompt → `pytest test_alex_behavior.py` 全绿 → 上线

**落地**：在 CLAUDE.md 的「完成标志」中增加规则：
> 凡修改 `app/prompts/` 下任意文件，必须同时运行 `pytest tests/test_alex_behavior.py -v` 全绿。

### 5.2 新功能「路径对称性」检查

每次新增 API 路由时，必须检查同一功能是否有多条路径（如 `/chat` vs `/chat/stream`），确保每条路径都走相同的 middleware 和 service 逻辑。

**落地**：在 CLAUDE.md 的「必须遵守」中增加规则：
> 新增或修改路由时，列出同一功能的所有路径入口，确认每条路径均有等价的业务逻辑处理。

### 5.3 MAX_TOKENS 等关键参数显式说明

关键参数缺少注释时，开发者容易忽视其影响范围。

**落地**：在 `config.py` 的 MAX_TOKENS 旁边增加注释，说明其设计意图和合理范围。

### 5.4 V0.3 Level 评估完成前的默认策略

在没有用户 Level 数据时，系统应明确声明默认假设（B1），而不是隐式依赖模型行为。这个默认策略应写进 System Prompt，等 Level 评估功能上线后再动态替换。

---

## 六、变更记录

> 完成日期：2026-03-16

| 任务 | 状态 | 涉及文件 |
|---|---|---|
| P0-A: System Prompt 加 Rule 5（B1 词汇约束） | ✅ 已完成 | `app/prompts/system.py` |
| P0-B: MAX_TOKENS 1024 → 300 + 注释说明 | ✅ 已完成 | `app/config.py` |
| P1: 修复流式接口绕过 build_system_prompt() | ✅ 已完成 | `app/services/model_client.py`（新增 `chat_stream_messages()`）、`app/routers/chat.py` |
| P1: 新增流式记忆注入测试 | ✅ 已完成 | `tests/test_stream_memory_fix.py`（4 个用例全绿） |
| P2: 新增 D5 词汇复杂度测试维度 | ✅ 已完成 | `tests/test_alex_behavior.py`（4 个 D5 用例 + 报告更新） |
| 修复 test_alex_behavior.py 的 httpx 兼容性 | ✅ 顺手修复 | `tests/test_alex_behavior.py`（`AsyncClient(app=)` → `ASGITransport`） |

**全量回归结果：72/72 PASSED**

---

## 七、修复优先级汇总

| 优先级 | 任务 | 影响 | 工作量 |
|---|---|---|---|
| P0-A | System Prompt 加词汇约束 | 立即改善用户体验 | 30 分钟 |
| P0-B | MAX_TOKENS 降至 300 | 物理约束复杂度 | 5 分钟 |
| P1 | 修复流式接口 grammar_cards 注入 Bug | 记忆功能对主路径生效 | 2 小时 |
| P2 | 新增 D5 测试维度 | 防止回归 | 1 小时 |
| 流程 | CLAUDE.md 规则更新 | 预防同类问题 | 15 分钟 |
