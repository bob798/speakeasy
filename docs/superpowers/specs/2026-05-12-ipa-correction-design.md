# IPA 纠音示范功能设计

> Date: 2026-05-12
> Owner: Claude Code（实现）· Human（验收）
> 范围：让 Azure TTS 的 IPA 纠音能力从「后端能力」变「用户可用功能」
> 关联：PR #28（Azure TTS 接入）· `docs/integrations/azure-speech-tts.md`

## 目标

让英语学习者**听到任意词 / 连读组的标准发音**：在解读弹窗里点 🎧，TTS 按词典级 IPA 合成音频，而不是靠拼写规则猜读音。

## 现状（V0.12 hotfix 后）

**已有：**
- `_azure_tts(text, voice, rate, phoneme_map)` 后端能力完整（`tts_service.py`）
- `_build_ssml` 构造 `<phoneme alphabet="ipa" ph="...">` 元素
- `tests/test_azure_tts.py` 含 5 个 phoneme_map 用例
- `quick_phonetic(word)` 本地返回 IPA（`eng_to_ipa` 库，美式）
- `/practice/explain/phonetic` 路由
- ExplanationModal 已展示单词 phonetic 和 liaison chunks 的 ipa
- ExplanationModal 已能用 `useTTS().enqueue(word)` 朗读（但不带 phoneme_map）

**缺失：**
- `/practice/tts` 的 `PracticeTTSRequest` 不接受 `phoneme_map`
- ExplanationModal 没有「按 IPA 标准音读」的 UI 入口
- `_build_ssml` 不支持多词短语 key（regex 用 `\b` 词边界）

## 设计

### 后端契约

#### `/practice/tts` 加 `phoneme_map`

```python
class PracticeTTSRequest(BaseModel):
    text: str = ""
    provider: str = ""
    voice: str = "jenny"
    speed: str = "+0%"
    segment_path: Optional[str] = None
    phoneme_map: Optional[Dict[str, str]] = None  # ← 新增
```

参数透传到 `multi_tts(text, provider, voice, speed, phoneme_map)`，已经支持。

#### `multi_tts` 智能升级

收到 `phoneme_map` 时：

| provider 入参 | AZURE_TTS_KEY | 行为 |
|---|---|---|
| `azure` | 已配 | 正常调 `_azure_tts(phoneme_map=...)` |
| `azure` | 未配 | 降级 edge + 忽略 phoneme_map + warning log |
| `edge` / `google` / `openai` | azure 已配 | **偷偷升级到 azure**（保留 phoneme_map）+ info log |
| `edge` / 等 | azure 未配 | 走原 provider + 忽略 phoneme_map + warning log |

「偷偷升级」让用户不用感知后端 provider 切换 —— 想要 IPA 纠音就给 phoneme_map，后端自己选最合适的 engine。

#### `_build_ssml` 支持多词短语

当前：

```python
for word, ipa in phoneme_map.items():
    pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
```

`\b` 是单词边界，不能跨空格。多词短语（如 `"give me"`）匹配失败。

改后：

```python
for phrase, ipa in phoneme_map.items():
    if ' ' in phrase:
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)         # 多词整串匹配
    else:
        pattern = re.compile(r'\b' + re.escape(phrase) + r'\b', re.IGNORECASE)
```

#### Response header 暴露 fallback

后端响应加可选 header 让前端知道实际走了哪条路径：

| Header | 含义 | 触发条件 |
|---|---|---|
| `X-TTS-Provider-Used: <name>` | 实际生效的 provider | 总是返回，方便诊断 |
| `X-TTS-Phoneme-Ignored: 1` | phoneme_map 被忽略 | 用户传了 phoneme_map 但 Azure 不可用 |
| `X-TTS-Fallback: edge` | Azure 失败降级 edge | Azure 抛异常时 |

`multi_tts` 返回类型从 `(audio, media_type)` 改为 `(audio, media_type, meta)`。当前 `multi_tts` 只有一个调用者（`/practice/tts` 路由），一起更新即可，无外部 API 变动。

### 前端 UI

`ExplanationModal.vue` 两处加 🎧：

#### A. 单词解读区

```
schedule
/ˈskɛdʒuːl/  🎧      ← IPA 旁
n. 时间表 / v. 安排
...
```

点 🎧：
- 立即视觉 loading（图标 → ⏳）
- 发 `POST /practice/tts`：
  ```json
  {
    "text": "schedule",
    "provider": "azure",
    "voice": "jenny",
    "speed": "+0%",
    "phoneme_map": { "schedule": "ˈskɛdʒuːl" }
  }
  ```
- 收 mp3 → `new Audio(blobUrl).play()`
- 播完 → 图标恢复
- 失败 → 图标变 ⚠️ 5s 复原 + tooltip 文案

#### B. 连读 chunk 区

```
🔊 连读 · 发音

• give me
  /ɡɪmi/  🎧
  T-flap, /v/ 弱化

• would you
  /wʊdʒu/  🎧
  /d/ + /j/ → /dʒ/
```

点 🎧：同 A，但 `phoneme_map = { chunk: chunk_ipa }`。

#### 视觉规范

- 🎧 按钮：26×26 圆形 / `--accent-soft` 底 / `--accent` 图标
- loading：图标变 ⏳ + opacity 0.6
- 播放中：IPA 文本本身 `border-bottom: 2px var(--accent)`
- 错误：图标变 ⚠️ + tooltip 「TTS 失败，已降级」5s 复原
- a11y：`aria-label="按 IPA 标准音读 schedule"`，`aria-busy` 在 loading 时为 true

#### 隐藏条件（不渲染 🎧）

- `phonetic` 字段为空 / null
- 当前 voice 是中文（`xiaoxiao` / `yunxi`），IPA 跟中文 voice 不兼容
- 当前 provider 是 `original`（句子原音播放，无 TTS 合成）

### 状态机约束

1. **并发保护** — 同一 🎧 二次点击：先 `AbortController.abort()` 上次 fetch + 释放上次 Audio，再起新的
2. **跨 🎧 互斥** — 单词 🎧 播放期间点连读 🎧，停掉单词的，播连读的（同一个 `_activeAudio` 槽）
3. **关弹窗清理** — modal 关闭时 abort + release
4. **stale 响应丢弃** — 触发新请求前必须 abort 旧 fetch + 释放旧 Audio；具体机制（AbortController / requestKey 比对）落地时定

### 测试

#### 后端单测（`tests/test_azure_tts.py` 扩展）

- `_build_ssml` 多词短语正确插入 `<phoneme>`，不影响其它内容
- `_build_ssml` 单词和短语 phoneme_map 混合使用
- `multi_tts` provider=edge + phoneme_map + AZURE_KEY 配好 → 实际调 `_azure_tts`（mock 验证）
- `multi_tts` provider=edge + phoneme_map + AZURE_KEY 未配 → 调 `_edge_tts`，phoneme_map 被忽略
- `/practice/tts` 路由端 phoneme_map 透传 + response header 标 fallback

#### 组件单测（`@vue/test-utils`）

- ExplanationModal `phonetic` 存在 → 渲染 🎧 按钮
- ExplanationModal `phonetic` 为空 → 不渲染 🎧
- ExplanationModal voice=xiaoxiao → 不渲染 🎧
- ExplanationModal liaison 数组每项一个 🎧
- 点 🎧 → 发出预期 POST body（mock fetch）

#### E2E（与 issue #32 P0 共同做）

- 进 Practice → 选词 → 弹 ExplanationModal → 点单词 🎧 → Network 看 /practice/tts body 含 phoneme_map + 返回 200 + audio/mpeg
- 同上但点连读 chunk 的 🎧

## 文件清单

```
后端：
├─ app/routers/practice.py          [MODIFY] PracticeTTSRequest + phoneme_map 透传
├─ app/services/tts_service.py      [MODIFY] _build_ssml 多词支持 + multi_tts 升级逻辑 + header 标记
└─ tests/test_azure_tts.py           [MODIFY] 加 5 个新用例

前端：
├─ frontend/src/components/ExplanationModal.vue   [MODIFY] 单词区 + liaison chunk 加 🎧 + 状态机
└─ frontend/src/components/__tests__/             [NEW]    ExplanationModal.spec.js
```

## Out of Scope（v1 不做）

- **用户编辑 IPA**（power-user 功能）— 未来增强
- **美式 / 英式音标切换** — 需新 IPA 源，本次只用 eng_to_ipa 美式
- **自动检测读错触发 🎧** — 需要 STT 录音评分，独立功能
- **整句 IPA 纠音按钮** — 整句 phoneme_map 需要词典级 batch 解析，复杂度高
- **桌面端 PracticePlayer 加 🎧** — V0.12 桌面端冻结，本次只动 modal

## 验收标准

- [ ] `/practice/tts` 接受 `phoneme_map` 字段，向下兼容（旧 client 不传也工作）
- [ ] provider=edge + phoneme_map + AZURE_KEY 已配 → 实际走 Azure（log 可验证）
- [ ] AZURE_KEY 未配 → phoneme_map 被忽略且不报错
- [ ] ExplanationModal 单词区有 🎧（phonetic 非空时）
- [ ] ExplanationModal 每个 liaison chunk 有 🎧
- [ ] 点 🎧 → 听到 IPA 强制的发音（用 `schedule` 美 vs 英对照验证）
- [ ] 中文 voice / phonetic 为空时 🎧 隐藏
- [ ] 并发点击安全（不重叠播放，不内存泄漏）
- [ ] 后端单测扩 5+ 用例全过
- [ ] 组件单测覆盖 4+ 用例
- [ ] frontend bundle 增量 < 5 KB gzip（无新大依赖）

## 关联

- PR #28（Azure 接入 + 移除豆包）
- PR #30（Azure 对接文档）
- PR #31（TTS 链路日志）
- Issue #32（测试覆盖缺口 · 本功能的 e2e 会落在 P0）
- Issue #26（手机端评分 · 无关但同期）
