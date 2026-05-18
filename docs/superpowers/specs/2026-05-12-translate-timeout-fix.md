# 翻译批量调用超时修复

> Date: 2026-05-12
> Owner: Claude Code（实现）· Human（验收）
> 范围：修复 `/translate/text` 在长输入下稳定 503 的根因，让长文/技术文本翻译可用
> 关联：`app/services/translate_service.py` · `app/services/model_client.py` · `tests/test_v05_translate_batch.py`

## 目标

让翻译页对 **20 行以上 / 含技术 token + 中文 gloss** 的批量请求**稳定返回**，不再因模型生成耗时超 30s 触发 SDK 三连重试 → 503。

## 现状

### 已有

- `translate_text()` 按行拆分 → 跳过空白/纯标点行 → 未命中缓存的批量送 `_translate_batch()`
- `_translate_batch()` 把所有未命中行一次塞进单个 LLM 请求，`max_tokens=4000`
- `OpenAICompatibleClient` 初始化 `OpenAI(timeout=30.0)`（`model_client.py:226`），SDK 默认 `max_retries=2`
- `BaseModelClient.complete(messages_or_prompt, max_tokens, scene)` 异步包装同步 `_complete_sync_messages`
- `tests/test_v05_translate_batch.py` 10 个用例覆盖按行拆分 / 缓存命中 / JSON 解析 / 错误兜底

### 根因证据（已确认）

线上 docker 日志：

```
2026-05-12 18:17:05 | ERROR | translate | [-] 翻译失败: Request timed out.
Traceback (most recent call last):
  File ".../httpx/_transports/default.py", line 250, in handle_request
    resp = self._pool.handle_request(req)
  ...
  File ".../openai/_base_client.py", line 1095, in _retry_request
    return self._request(...
```

触发条件：单次 21 行混合 EN→ZH 输入（含 `SPRING_PROFILE` / `micrometer-tracing-bridge-brave` 等需附中文 gloss 的技术 token），LLM 生成 JSON 数组耗时 > 30s。

| 因素 | 当前值 | 问题 |
|---|---|---|
| 客户端 timeout | 30s（全局） | 长批量翻译偏紧，且 chat/explain 等场景不需要这么长 |
| SDK `max_retries` | 默认 2 | 失败后再硬撑两次，最坏总耗时 ~90s 才回错 |
| 批量逻辑 | 无切片，N 行全送一次 | 输入越长越容易触发上述超时 |
| 缓存策略 | 已有，按 (text_hash, direction) | 重复输入命中后无问题；首次长输入仍受超时影响 |

### 缺失

- `complete()` / `_complete_sync_messages()` 不支持**按调用覆盖 timeout**，所有场景共用同一个 30s
- `_translate_batch()` 没有切片策略，行数越多越容易超时
- 无关于"翻译场景应该给多少时间"的统一约束

## 设计

### A) 按调用覆盖 timeout

`BaseModelClient.complete()` 加可选 `timeout`，透传到底层 SDK：

```python
class BaseModelClient:
    async def complete(
        self,
        messages_or_prompt,
        max_tokens: int = 1000,
        scene: str = "default",
        timeout: float | None = None,
    ) -> str:
        ...
        return await loop.run_in_executor(
            None,
            lambda: self._complete_sync_messages(messages, max_tokens, scene, timeout),
        )

    def _complete_sync_messages(
        self, messages: list, max_tokens: int, scene: str = "default",
        timeout: float | None = None,
    ) -> str: ...
```

两个子类实现各自把 `timeout` 透传到 SDK 的 `messages.create(...)` / `chat.completions.create(...)`：

- **OpenAI 兼容**：`self.client.chat.completions.create(..., timeout=timeout)` —— openai SDK 支持 per-request `timeout`，传 `None` 时回落到 client 默认 30s
- **Anthropic**：`self.client.messages.create(..., timeout=timeout)` —— anthropic SDK 同样支持，行为一致

**关键约束：默认行为不变**。`timeout=None` 时所有现有调用（chat / explain / review / facts / ask / polish / bbc_question_gen）继续走 client 全局 30s，**零影响**。

### B) 切片批量调用

`_translate_batch()` 把 `lines` 按 `TRANSLATE_BATCH_CHUNK_SIZE` 切片，每片单独走一次 `complete()`，多片用 `asyncio.gather` 并发：

```python
TRANSLATE_BATCH_CHUNK_SIZE = 8
TRANSLATE_BATCH_TIMEOUT_S = 60.0

async def _translate_batch(lines: List[str], direction: str) -> List[str]:
    if not lines:
        return []
    chunks = [
        lines[i : i + TRANSLATE_BATCH_CHUNK_SIZE]
        for i in range(0, len(lines), TRANSLATE_BATCH_CHUNK_SIZE)
    ]
    results = await asyncio.gather(
        *(_translate_one_chunk(c, direction) for c in chunks)
    )
    flat: List[str] = []
    for r in results:
        flat.extend(r)
    return flat

async def _translate_one_chunk(lines, direction):
    # 现 _translate_batch 主体，加 timeout=TRANSLATE_BATCH_TIMEOUT_S
```

| 项 | 值 | 理由 |
|---|---|---|
| `CHUNK_SIZE` | 8 | 现有测试最多送 3 行 / 单批，8 行内不触发切片，老测试断言 `await_count == 1` 不破；同时 8 行带 gloss 在 60s 内绰绰有余 |
| `TIMEOUT_S` | 60 | 8 行 + 4000 max_tokens 经验值在 15~30s 区间，60s 给 2× 余量 |
| 并发 | `asyncio.gather` | 21 行→3 片并行 ≈ 单片耗时；不开并发会回到原状 |
| 切片粒度 | 行级，保序 | 行级 chunk 天然保持顺序，`flat.extend(r)` 即拼回 |

### 错误传播

任一 chunk 抛 `ValueError`（行数对不上 / JSON 解析失败）或超时，`asyncio.gather` 默认 `return_exceptions=False` 直接冒泡 → `translate_text()` 不变 → 路由层 503，与现状一致。

### 不做

- 切片粒度按 token 估算（行级切片够用，token 估算引入新依赖）
- 跨 chunk 共享 cache 写入事务（每 chunk 内部独立 `_cache_set`，并发安全靠 `IntegrityError` 回滚兜底，已有逻辑）
- 流式翻译（需要全量 JSON 才能解析数组，流式无收益）
- 把 30s 全局超时直接调大（污染所有场景，违反最小改动原则）
- 把 `MODEL_SCENE_TRANSLATE` 默认切换到更快的模型（属于配置层决策，可后续按需）

## 测试

### 单测扩展（`tests/test_v05_translate_batch.py`）

新增用例：

1. **小批不切片** — 送 3 行，`mock_client.complete.await_count == 1`（守住现有断言）
2. **超阈值切片** — 送 17 行，`await_count == 3`（17 → ceil(17/8)=3），每次 payload `lines` 长度 ≤ 8，顺序拼回正确
3. **切片错误冒泡** — 其中一片返回行数不对，`pytest.raises(ValueError, match="行数不匹配")`
4. **timeout 透传** — `mock_client.complete.call_args.kwargs.get("timeout") == 60.0`

### 现有用例保护

- `test_batch_sends_single_llm_call`（3 行 → 1 次调用）
- `test_cache_partial_hit_only_misses_sent`（pending=1 行 → 1 次调用）
- `test_cache_hit_skips_llm`（缓存命中 → 0 次调用）
- `test_output_count_mismatch_raises`（行数不匹配 → ValueError）

切片阈值 8 设计上**保证以上不破**。

### 手工回归

部署后用线上原报错的 21 行混合输入（issue 里附原文）跑一次，预期：

- 200 OK，2× 业务模型生成时间内返回
- docker logs 看到 3 次翻译 LLM 调用、无 timeout
- 第二次同样输入命中缓存，0 次 LLM 调用

## 文件清单

```
app/
├─ services/model_client.py            [MODIFY]
│   · BaseModelClient.complete() 加 timeout 参数
│   · BaseModelClient._complete_sync_messages() 加 timeout 参数
│   · AnthropicClient._complete_sync_messages() 透传 timeout
│   · OpenAICompatibleClient._complete_sync_messages() 透传 timeout
└─ services/translate_service.py       [MODIFY]
    · 新增 TRANSLATE_BATCH_CHUNK_SIZE / TRANSLATE_BATCH_TIMEOUT_S 常量
    · _translate_batch 改为切片 + asyncio.gather
    · 抽 _translate_one_chunk 承载单片逻辑
    · 顶部 import asyncio

tests/
└─ test_v05_translate_batch.py         [MODIFY]
    · +4 新用例（切片不切、切片切、错误冒泡、timeout 透传）
```

## Out of Scope（本次不做）

- **token-aware 切片** — 等出现"单行就超 4000 token"的真实样本再加
- **逐 chunk 进度回传前端** — 翻译不像 chat 流式有用户预期，全量返回足够
- **重试策略调优**（如 `max_retries=0`）— 切片 + 长 timeout 已经能让首发就成功；保留 SDK 默认 2 次重试做兜底
- **切换默认 provider/模型** — 属配置决策，留给运维侧
- **前端 loading 文案优化**（"翻译中（21 行，约需 X 秒）..."）— UX 增强，独立任务

## 验收标准

- [ ] `complete(timeout=N)` 透传到底层 SDK，OpenAI 兼容与 Anthropic 两路径都生效
- [ ] 不传 `timeout` 时所有其他场景（chat/explain/review/facts/ask/polish）行为零变化（grep 调用方 + 跑全量回归）
- [ ] 21 行混合 EN→ZH 输入（issue 里附原文）线上 200 OK 并返回正确翻译
- [ ] docker logs 显示翻译被切成 3 次并发调用，无 `Request timed out`
- [ ] 同输入第二次命中缓存，0 次 LLM 调用
- [ ] `pytest tests/test_v05_translate_batch.py -v` 全绿（含 4 个新用例）
- [ ] `pytest tests/ -v` 全量回归全绿
- [ ] 文档同步：本 spec + `CLAUDE.md` 接口清单无变化（路由签名未动，不更新）

## 关联

- 报错日志原文：见 issue body
- 现有翻译批量测试：`tests/test_v05_translate_batch.py`
- 三层模型抽象：`docs/architecture/c4-container.md`（如有 model_client 流程图，本改动不动结构，无需更新）
