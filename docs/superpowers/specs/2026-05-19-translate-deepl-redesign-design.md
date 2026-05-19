# Translate Page DeepL-style Redesign — Design Spec

**Status:** Draft → 待 Human 确认
**Author:** Claude (brainstorm session with bob798)
**Date:** 2026-05-19
**Target version:** V0.11
**Scope:** `frontend/src/views/Translate.vue` 整体重写；后端零改动

---

## 1. 背景与动机

当前 `/translate` 页（Vue 3 版，V0.9.4 重设计）有以下被确认的体验问题：

1. **视觉粗糙**：译文区最小高度 180px，无内容时大片空白；textarea 与 result 视觉权重相同，缺层次。
2. **swap 交互反直觉**：右上角「中→英 ⇄」按钮 swap 时把译文塞回输入框、清空译文，第一次点击的用户必踩坑（`Translate.vue:67-71`）。
3. **生词本 ↔ FSRS 脱节**：V0.10 已把 vocab 接入 FSRS（commit `2c840c1`），但 Translate.vue 的「已掌握/翻牌」仍写 `localStorage` `MASTERED_KEY`（`Translate.vue:79-102, 191-198`），复习数据是孤岛，不进入全局 SRS 循环。
4. **缺学习闭环**：项目主战场是「英语私教 + FSRS 复习」，但翻译页是纯翻译工具——无发音、无单词解读、无追问，不复用已有的 `/practice/explain/phonetic` `/practice/explain/stream` `/ask/threads` 能力。
5. **PC 端体验弱**：当前是「移动优先 + 响应式」，但翻译这个功能用户主要在 PC 端用，宽屏没有充分利用。

用户决策（brainstorm 已确认）：
- 翻译页**单独 PC 端优先**（与项目整体「移动优先」决策不同，因为该功能的实际使用场景偏 PC）
- 改版幅度：**重构为 DeepL 风**（不是小修小补）
- 自动翻译：**停顿 800ms 自动译**（debounce）
- 单词交互：**hover 出 IPA（本地），click 才调 LLM**

---

## 2. 目标与非目标

### 目标
- PC 端打造 DeepL 风格的「左输入 / 右译文 + 右侧 sidebar」布局
- 译文区单词级交互：hover 出 IPA，click 出完整词卡（释义/例句/收藏）
- 800ms debounce 自动翻译，前端缓存去重，不增加后端成本
- 生词本与 V0.10 FSRS 打通，删除孤立的 localStorage 掌握状态
- 历史记录（最近 50 条，localStorage 本地存）
- 移动端做响应式降级（不当主战场）
- **后端零改动**

### 非目标
- 不新增数据表
- 不新增后端接口
- 不实现「实时流式翻译」（停顿后整段返回足够）
- 不引入新的 npm 依赖（除非必要）
- 不动 `static/translate.html`（legacy，已退役到 `/legacy/translate`）

---

## 3. 整体架构

```
┌──────────────────────────────────────────────────────────────────┐
│ ←返回   Speakeasy · 翻译         [中文⇄English]          📖 ▢   │  ← top bar
├─────────────────────────┬────────────────────────┬───────────────┤
│                         │                        │ 📖 生词本 (3) │
│  输入中文…              │  I had a great time…   │ [生词本][历史]│
│                         │  /aɪ hæd ə ɡreɪt taɪm/ │               │
│                         │  [▶][⤵][⭐]            │ · had  /hæd/  │
│                         │  ·· hover 单词 ··      │   ⏰ 今天到期 │
│                         │                        │   [Again][Hard]│
│                         │  ── 译于 17:32 ──      │   [Good][Easy] │
│              12/1000    │                        │ · great…      │
└─────────────────────────┴────────────────────────┴───────────────┘
        左栏 input              右栏 result               右侧 sidebar
        (1fr)                   (1fr)                     (320px)
```

### 组件拆分（Vue 3 SFC）

```
Translate.vue                       — 顶层容器，编排 state + 三栏布局
├─ TopBar.vue                       — ←返回 + 标题 + 方向切换 + sidebar 折叠按钮
├─ TranslateInput.vue                — 左栏：textarea + 计数 + 自动检测方向标签
├─ TranslateResult.vue               — 右栏：译文卡 + 单词分词 + 工具栏
│   ├─ WordToken.vue                — 单个单词 span，hover/click 浮层
│   └─ WordCard.vue                  — click 后的完整词卡（IPA/释义/例句/收藏）
└─ TranslateSidebar.vue              — 右侧 sidebar
    ├─ VocabularyTab.vue            — 生词本（接入后端 FSRS）
    └─ HistoryTab.vue                — 历史（localStorage）
```

**为何拆**：当前 `Translate.vue` 单文件 ~730 行，已超「文件做太多事」的临界点。拆分后每个组件职责单一，便于后续单测/调整。

---

## 4. 功能细节

### 4.1 自动翻译 (debounce 800ms)

- **canonical 输入**：`canonicalText = source.trim()`，**同时用于 cache key 和请求体**（保留大小写敏感，英文专名/句首需要它）
- **触发**：输入变化后 `setTimeout(800ms)`，停顿后判定 `canonicalText.length > 0 && canonicalText.length <= 1000`
- **前端 cache**：`Map<JSON.stringify([canonicalText, direction]), translated>`，LRU 100 条，session 级（不持久化）
- **命中 cache** → 立即渲染，不发请求
- **未命中 → 发 `POST /translate/text`**，并按下面的并发模型处理
- **不触发**：`canonicalText` 与上一次相同（仅前后空白变化）
- **swap 后**：保留 `source` / `translated` 文本不动，但 `translated` 视为 `stale`（视觉加角标「切换方向后请重新翻译」，下次用户编辑 source 或显式 Cmd/Ctrl+Enter 才刷新）—— 这样既符合 swap「不动文本」的语义，又避免显示与当前方向不匹配的旧译文

**并发模型（防 stale response 覆盖）**：

只 abort 上一个请求不够 —— abort 前已 resolve 的响应仍可能晚于新请求落地。必须：

```
let requestId = 0
let abortCtrl = null

async function doTranslate(canonicalText, direction) {
  const myId = ++requestId
  abortCtrl?.abort()
  abortCtrl = new AbortController()
  const cacheKey = JSON.stringify([canonicalText, direction])

  // cache 命中：仍要校验 myId 仍是最新
  if (cache.has(cacheKey)) {
    if (myId === requestId) renderResult(cache.get(cacheKey))
    return
  }

  try {
    const data = await fetchTranslate(canonicalText, direction, { signal: abortCtrl.signal })
    // ⚠️ stale 防御：await 后必须再次校验
    if (myId !== requestId) return
    cache.set(cacheKey, data.translated_text)
    renderResult(data.translated_text)
    pushHistory({ source: canonicalText, translated: data.translated_text, direction })
  } catch (e) {
    if (e.name === 'AbortError' || myId !== requestId) return
    showError(e)
  }
}
```

**生命周期**：`onUnmounted` 时 `clearTimeout(debounceTimer)` + `abortCtrl?.abort()`，避免组件卸载后还在写响应式 state。

### 4.2 方向自动检测

- 实时检测（输入时同步算）：中文 unicode 比例（`/[一-龥]/`）≥ 30% → `zh2en`，否则 `en2zh`
- TopBar 显示当前方向标签：`中文 ⇄ English`，左侧高亮源语言
- 用户可点 swap 手动覆盖；手动覆盖后 5 秒内不再自动重判（避免抖动）
- swap 行为：**只切方向**，不动 source/translated 文本（修正当前 bug）

### 4.3 译文区单词分词与交互

**分词**（按 Unicode script 区分，纯函数，不引入额外库）：

```ts
function tokenize(text: string): Token[] {
  const tokens: Token[] = []
  let i = 0
  while (i < text.length) {
    const ch = text[i]
    if (/\s/.test(ch)) { tokens.push({ kind: 'space', text: ch }); i++; continue }
    // CJK：逐字 token（中文必须按字符切，单一正则会把连续中文归一个 token）
    if (/[一-鿿㐀-䶿]/.test(ch)) {
      tokens.push({ kind: 'cjk', text: ch, interactive: true })
      i++
      continue
    }
    // 英文词（含连字符 well-known / 缩略 don't）
    const m = text.slice(i).match(/^[A-Za-z][A-Za-z'-]*/)
    if (m) { tokens.push({ kind: 'word', text: m[0], interactive: true }); i += m[0].length; continue }
    // 标点、数字、其它：单字符 token，不可交互
    tokens.push({ kind: 'punct', text: ch })
    i++
  }
  return tokens
}
```

- `interactive: true` 的 token 才挂事件、才能 hover/click
- 标点/空白/数字不可交互（视觉上正常显示，跳过事件）

**渲染**（a11y 友好）：
- 可交互 token 渲染为 `<button type="button" tabindex="0">`（或 `<span role="button" tabindex="0">` 若不想要 button 默认样式），支持 Enter / Space 触发 click 行为
- 非交互 token 渲染为普通文本节点（不入 tab 序）
- 整体 `aria-label="译文"` 包裹，读屏器读连贯句子；交互 token 不要 `aria-hidden`，但每个不要单独 `aria-label`（否则读屏器会拆碎成单词朗读）
- 事件用事件委托：父容器单个 `mouseover/mouseout/click/keydown` 监听，根据 `event.target` 的 `data-token-index` 派发，避免 200 个独立监听器

**hover 行为**（仅 `(hover: hover) and (pointer: fine)` 桌面，CSS @media 判定）：
- 鼠标停留 100ms → 调 `POST /practice/explain/phonetic` payload `{text: word}`，返回 `{phonetic: "/hæd/" | null}`，本地 eng-to-ipa 毫秒级
- 浮层（原生 CSS `position: absolute` 即可，不引入 Popper.js）显示：
  ```
  had
  /hæd/  🔊
  ```
- **sticky hover 区**：浮层与 token 之间留 0 间距 + `pointer-events: auto`，鼠标进入浮层不消失，移开 200ms 才隐藏
- Esc / blur / token 外 click → 立即隐藏
- 未知词（phonetic=null）显示「无音标」占位，不调 LLM

**click / Enter / Space 行为**（桌面 + 移动 tap）：
- 调 `POST /practice/explain`，payload `{text: word, kind: 'word', context: 整句 translated_text, refresh: false}`
- 后端 `explain_text` 返回包含 IPA / 释义 / 例句的完整 JSON（带服务端缓存，重复点同词秒回）
- 移动端词卡顶部**先展示本地 phonetic**（已有 hover 缓存或单独调一次），LLM 解读 loading 后追加，避免空窗
- 浮层展开为完整词卡：
  ```
  had
  /hæd/  🔊
  have 的过去式。
  1. 拥有  2. 必须  3. 经历
  例：I had breakfast at 7.
  [⭐ 加入生词本]
  ```
- **「加入生词本」**：调 `POST /vocab`，payload：
  ```json
  {
    "source_text": "had",
    "translated_text": "have 的过去式",
    "direction": "en2zh",
    "context": "I had a great time...",
    "item_type": "word",
    "source_type": "translate",
    "source_ref": "translate:word:had",
    "explanation_json": "<LLM 返回的完整 JSON>"
  }
  ```
- **`source_ref` 必须给稳定值**（如 `translate:word:{lemma}`），否则后端去重键 `(user_id, source_text, source_ref)` 会让同一个词与其它来源的同 source_text 条目冲突。**已存在则后端只复活 status、不覆盖 explanation_json**（这是 V0.10 的有意设计，spec 接受这个行为：同词只保留首次解读）
- 同一个词的解读结果用 `Map<word, explainResult>` 缓存 session 期

**性能优化**：分词只对 translated_text 做（最长 1000 字符 × 英文平均词长 5 ≈ 200 个 token，浏览器 paint < 16ms 可接受）；事件委托避免 200 个独立监听器。

### 4.4 工具栏（右栏顶部）

- `▶ 发音`：整句 TTS（复用 `useTTS` composable）
- `⤵ 反向校验`：把当前 translated 作为 source 倒译一次，对照翻译质量。**必须独立于 debounce 主流程**，否则会出现 (a) 灌入 source 立刻触发 800ms debounce 多打一次 LLM，(b) backcheck 结果覆盖 history / translated 主字段
  - **实现**：新增状态 `mode: 'normal' | 'backcheck'`，进入 backcheck 时：
    1. 暂存当前 `{source, translated, direction}` 为 `snapshot`
    2. `mode = 'backcheck'`，禁用 source watcher 的 debounce（watcher 内 `if (mode === 'backcheck') return`）
    3. 直接调 `POST /translate/text`，payload `{text: snapshot.translated, direction: 反转(snapshot.direction)}`
    4. backcheck 结果只渲染到一个独立的「反向校验」浮层 / 折叠区，**不写入 `translated`、不入 history**
  - **退出**：再次点击 ⤵ / Esc / 用户开始编辑 source → 还原 snapshot，`mode = 'normal'`
- `⭐ 收藏整句`：调 `POST /vocab`，payload：
  ```json
  {
    "source_text": "<整句源文>",
    "translated_text": "<整句译文>",
    "direction": "zh2en" | "en2zh",
    "item_type": "sentence",
    "source_type": "translate",
    "source_ref": null
  }
  ```
  - 句子级收藏不传 `source_ref`，去重键依赖 `(user_id, source_text, NULL)`，避免和单词级 `translate:word:*` 冲突
  - **去重坑提醒**：如果用户先收藏了句子 A，过 5 分钟改了一字又收藏，后端只复活旧条目、不覆盖 translated_text。需要前端在 toast 区分「⭐ 新增」/ 「📌 已在生词本」（用返回的 `created_at` 与当前时间差判定）

### 4.5 右侧 Sidebar

**整体**：
- 默认展开 320px；点 TopBar 📖 折叠/展开
- 折叠时主区扩到全宽
- 移动端 (< 1024px) sidebar 始终隐藏，📖 改为打开 bottom-sheet

**Tab 1 · 生词本**：

- **接口现状（实读 `app/services/vocab_service.py` 确认）**：
  - `GET /vocab` 仅支持 `item_type / source_ref / due / limit / offset`，**没有 `source_type` 查询参数**
  - 返回字段：`{id, source_text, translated_text, direction, item_type, source_type, source_ref, explanation_json, status, created_at, last_reviewed_at, due, is_due}` —— **没有 `next_review_at`**
  - `due=true` 时后端先全量加载再本地 filter，最后才分页 → **`?due=true&limit=1` 的 count 不是总到期数**，最多为 1
  - `POST /vocab/{id}/rate` 返回 `{id, due, item}`，`item` 是 `_to_dict(v)` 完整字典
- **本期不改后端**，按下面方案前端兜底：
  - **列表加载**：`GET /vocab?limit=500`（拉全量），前端按 `source_type === 'translate'` 本地过滤
  - **到期 badge**：用本地过滤后的 `items.filter(v => v.is_due).length`，**不要靠 `?due=true&limit=1`**
  - **倒计时**：用返回的 `due`（ISO 字符串）算 `Date.parse(due) - Date.now()`；过期显示「待复习」徽标
- **替换** 当前 `MASTERED_KEY` localStorage 逻辑 → 用后端 FSRS（`is_due` 字段）
- 每条目下方 4 档按钮（与 practice 风格一致）：`[Again] [Hard] [Good] [Easy]` → `POST /vocab/{id}/rate` payload `{rating: "again"|"hard"|"good"|"easy"}`
- **评分后立即更新本地列表**：用返回的 `item` 字典原地替换该 id 的条目；若当前视图是「仅到期」且 `item.is_due === false`，从可见列表移除并 badge -1
- 列表筛选：搜索框（>5 条出现）+ item_type chip（单词 / 句子 / 全部）；默认「全部」
- **未来后端优化** TODO（不在本期 spec）：`GET /vocab/due_count?source_type=translate` 聚合接口，避免全量拉取。本期 500 条上限足够。

**Tab 2 · 历史**：
- localStorage key `v1:translate.history`
- 结构：`[{ source, translated, direction, timestamp }]`，FIFO 50 条
- 每次成功翻译 push 一条（去重：连续相同 source/direction 不重复）
- 点条目 → source/translated 灌回主区
- 「清空历史」按钮

### 4.6 移动端响应式 (< 1024px)

- TopBar：标题缩短、方向切换图标化
- 主区单列堆叠：输入 → swap 按钮（圆形悬浮，居中）→ 译文
- sidebar 改 FAB（右下角 📖）打开 bottom-sheet
- 单词无 hover（CSS `@media (hover: none)` 不挂 mouseover），tap = click 行为
- safe-area inset 处理（沿用 `--safe-top` `--safe-bottom` 变量）

**bottom-sheet 实现**：

- **复用 `Practice.vue` / `VoiceSettings.vue` 已有的 sheet 模式**（Teleport / scroll lock / focus restore / inert 背景 / Esc 关闭 / safe-area-bottom），不造拖拽轮子
- **本期不做拖拽展开**：固定高度 `min(60vh, calc(100vh - var(--safe-top) - 48px))`，顶部一个 grip handle 提示（视觉装饰，不绑手势）
- **a11y 必做**：
  - 打开后焦点初始落在 sheet 内第一个可聚焦元素
  - Esc / 遮罩 click 关闭
  - 关闭后焦点回到触发的 📖 FAB
  - 打开期间背景 `inert` + `body { overflow: hidden }`（scroll lock）
- 若 Practice 的 sheet 还没抽成共享组件，本期顺手抽 `frontend/src/components/BottomSheet.vue`（至少覆盖 a11y 行为），后续 memory/practice/translate 共用

### 4.7 视觉与样式

- 沿用项目 design tokens（`--accent` `--bg` `--border` 等）
- 关键改动：
  - 译文区 `min-height` 改为 `120px`（无内容时不那么空旷）
  - 输入框焦点态 accent 边框 + 微弱阴影
  - 单词 span hover 高亮：`background: var(--accent-soft)`
  - 浮层：`box-shadow: 0 4px 16px rgba(0,0,0,0.12)`，`border-radius: var(--radius)`
- 字体沿用现有，无新增字体加载

---

## 5. 数据流

```
用户输入 → onInput (immediate)
  ├─ 计 canonicalText = source.trim()
  ├─ 字符计数 + 方向检测 + 错误状态
  ↓ (debounce 800ms)
  ↓ if mode === 'backcheck' → return (反向校验期间禁用 debounce)
  ↓ if canonicalText 与上次相同 → return
  ↓ requestId++; abortCtrl?.abort(); new AbortController
  ↓ cacheKey = JSON.stringify([canonicalText, direction])
  ├─ 命中 → 校验 myId === requestId → 渲染 translated
  └─ 未命中 → POST /translate/text {text, direction} (signal)
                ↓ 返回 → 校验 myId === requestId (stale 防御)
                ↓ cache.set + 渲染 translated + push history
                ↓ AbortError 或 myId 已过期 → 静默 return
                ↓ 其它错误 → inline error，不清空 translated

渲染 translated
  ↓ tokenize(text) (按 Unicode script，CJK 逐字 + 英文词)
  ↓ 父容器事件委托：mouseover / mouseout / click / keydown
  ↓
hover 可交互 token (桌面 @media hover:hover) →
  100ms 后 POST /practice/explain/phonetic {text: word}
  → 浮层显示 IPA + 🔊；sticky hover 区允许鼠标进入

click / Enter / Space 可交互 token →
  POST /practice/explain {text: word, kind: 'word', context: 整句, refresh: false}
  → 展开 WordCard（先显示已缓存 phonetic，LLM 解读 loading 后追加）
  → ⭐ → POST /vocab {item_type: 'word', source_type: 'translate',
                      source_ref: 'translate:word:<word>', explanation_json}
       → 用返回 item 插入 sidebar 列表头部，badge +1

工具栏 ⤵ 反向校验 →
  mode = 'backcheck'，snapshot 当前 {source, translated, direction}
  → POST /translate/text {text: snapshot.translated, direction: 反转}
  → 结果渲染到独立浮层（不写 translated/history）
  → 退出：再次点击 / Esc / 用户编辑 source → 还原 snapshot，mode = 'normal'

生词本 4 档评分 →
  POST /vocab/{id}/rate {rating}
  → 用返回的 item 原地替换条目；若视图为「仅到期」且 item.is_due === false → 移出
```

---

## 6. 测试策略

### 单元测试（Vitest）
- 分词函数 `tokenize(text)` 边界：英文缩略 (`don't`) / 连字符 (`well-known`) / 标点 / 中英混排 / **连续中文必须逐字 token**（不是一整段一个 token）
- 方向检测函数 `detectDirection(text)` 的临界比例（30% 中文字符）
- LRU cache 容量与 key canonicalize（`source.trim()` 一致性）
- History localStorage 去重 + FIFO
- **stale response 防御**：模拟 A 请求慢、B 请求快、A 晚于 B 返回，断言 `translated` 仍是 B 的结果

### E2E / 手测清单

**翻译流程**：
- [ ] 输入中文，800ms 停顿后自动出译文
- [ ] 编辑中途快速改动 → 旧请求被 abort
- [ ] **stale 防御**：人为延迟使旧请求晚返回，断言不覆盖新结果
- [ ] 相同文本（含 trim 前后空白差异）第二次输入 → 命中 cache，无网络请求
- [ ] swap 按钮：只切方向，不动文本；切方向后 translated 视为 stale（视觉标记）
- [ ] 反向校验：进入 backcheck 后编辑 source **不触发** debounce 译；Esc / 再次点击退出 → 还原 snapshot

**单词交互**：
- [ ] hover 英文单词 100ms 后出 IPA 浮层；鼠标从 token 移到浮层不消失（sticky 区）
- [ ] **键盘可达**：Tab 进入可交互 token，Enter / Space 打开词卡；Esc 关闭
- [ ] **读屏器**：整句仍读连贯，不把每个词单独读一遍（aria-label 不冗余）
- [ ] click 单词 → 调 `POST /practice/explain` (kind='word')，展开词卡 → ⭐ 收藏单词
- [ ] 同一单词二次点击 → 命中 session cache，不重复调 LLM

**生词本**：
- [ ] ⭐ 收藏整句 → sidebar 生词本立即出现新条目（badge +1）
- [ ] 重复收藏同句子 → toast 显示「📌 已在生词本」，不增条
- [ ] 4 档评分 → 后端 FSRS 更新；返回的 `item` 替换条目；`is_due` false 且视图为「到期」时移出
- [ ] item_type chip 过滤：单词 / 句子 / 全部
- [ ] `due` 倒计时显示正确（过期、X 小时后、X 天后）

**历史**：
- [ ] 历史 tab：最近 50 条；连续相同 source 不重复

**布局/移动端**：
- [ ] sidebar 折叠 → 主区扩全宽
- [ ] 移动端 (< 1024px)：sidebar 隐藏，FAB 打开 bottom-sheet
- [ ] **sheet a11y**：打开后焦点落到 sheet 内；Esc / 遮罩关闭；关闭后焦点回 FAB；背景 inert + scroll lock
- [ ] safe-area：iPhone 刘海/底栏不遮挡

### 回归
- `/practice` `/chat` `/memory` 页面无影响（共享 composables 不动）
- `/legacy/translate` 不受影响

---

## 7. 风险与待定项

| 风险 | 缓解 |
|---|---|
| 生词本 500 条上限：高频用户超出会拉不全 | 本期 500 上限够（典型用户 < 100 条）；超出后顶部显示「仅显示最新 500 条」+「下载全部 CSV」入口（CSV 走 sidebar 一个按钮，不入 spec 核心范围） |
| hover 浮层在密集中文译文上抖动 | 浮层 100ms 延迟出现，移开 200ms 延迟消失，sticky 区允许鼠标进入浮层；Esc / 外 click 立即关 |
| 分词对长文本（接近 1000 字）的 DOM 性能 | 1000 字英文 ≈ 200 个 token，事件委托 + 单一父监听器，浏览器 paint < 16ms。如有问题再做虚拟化（暂不做） |
| 单词解读 LLM 调用过频 | session 级 `Map<word, explainResult>`；后端 `explain_text` 也有缓存（V0.11 #8 schema 版本控制） |
| 单词进 FSRS 后与 sentence 混在到期列表 | sidebar item_type chip 过滤；badge 默认计「全部到期」，可切到「仅单词」/「仅句子」 |
| 后端去重坑：同 source_text 的 word / sentence 入库后只复活 status 不覆盖 explanation | 单词收藏给稳定 `source_ref="translate:word:<word>"` 隔离命名空间；句子收藏 `source_ref=null`；toast 用 `created_at` 与当前时间差判定是「新增」还是「📌 已在」 |
| stale response 覆盖最新结果 | requestId 递增 + await 后校验；详见 § 4.1 并发模型 |
| 反向校验与 debounce 主流程互相污染 | `mode='backcheck'` 状态位，watcher 内显式 return；详见 § 4.4 |

---

## 8. 实施计划（高层）

详细分步任务由后续 writing-plans 阶段生成。**每个 PR 都要保证 ship 后页面可用、无半成品入口**。

### PR 1 · 结构 + 翻译主流程（用户可见：体验和现版接近，bug 修了）

1. 拆分 5 个 SFC 文件骨架（Translate / TopBar / TranslateInput / TranslateResult / TranslateSidebar），先把当前内容平移
2. 三栏布局（左输入 / 右译文 / 右 sidebar，sidebar 内**只保留现有生词本列表 + 翻牌**，不动评分逻辑）
3. **重写翻译触发**：debounce 800ms + canonicalText + LRU cache + requestId stale 防御 + AbortController + 生命周期清理
4. swap 改为纯方向切换，不动文本（修当前 bug）
5. 方向自动检测

**ship 后页面状态**：用户进来看到的还是「输入+译文+生词本」，但翻译延迟更短、bug 修了；翻牌 tab 仍在用旧 localStorage（PR3 才删）；译文还是纯文本（PR2 才分词）。

### PR 2 · 单词交互（用户可见：hover/click 单词出词卡）

5. 译文分词 + WordToken（事件委托 + a11y button/tabindex）
6. hover → `POST /practice/explain/phonetic`（sticky 浮层）
7. click / Enter / Space → `POST /practice/explain` (kind='word')，展开词卡
8. **本 PR 词卡里暂不露出 ⭐ 收藏按钮** —— sidebar 还没接通 FSRS，避免收藏后用户看不到反馈

**ship 后页面状态**：单词可 hover/click 查 IPA + 解读；收藏入口隐藏（PR3 开放）；生词本仍是 PR1 状态。

### PR 3 · Sidebar 接通 FSRS + 收藏闭环（用户可见：完整收藏 + 复习）

9. Sidebar 生词本 tab 改用 `GET /vocab?limit=500` + 本地过滤 source_type
10. 评分按钮 4 档 → `POST /vocab/{id}/rate` → 用返回 item 替换条目
11. badge 用本地 count；item_type chip 过滤；`due` 倒计时
12. **删** `MASTERED_KEY` localStorage / 翻牌复习 tab / `flashIdx` 等代码（spec § 9）
13. WordCard 露出 ⭐ → `POST /vocab` (item_type=word, source_ref="translate:word:*")
14. 工具栏 ⭐ 整句收藏 → `POST /vocab` (item_type=sentence, source_ref=null)
15. 工具栏 ⤵ 反向校验（mode='backcheck' 状态位）
16. Sidebar 历史 tab + localStorage `v1:translate.history`

**ship 后页面状态**：完整桌面体验，所有收藏/评分入口可用。

### PR 4 · 移动端 + QA（用户可见：手机可用）

17. 抽 `BottomSheet.vue` 共享组件（Teleport / focus / scroll lock / Esc / inert / safe-area），Practice/VoiceSettings 也迁过来
18. 移动端 < 1024px：sidebar → FAB + bottom-sheet；主区单列；CSS `@media (hover: none)` 关 hover 行为
19. 手测全清单（§ 6）+ 回归 `/practice` `/chat` `/memory`

**ship 后页面状态**：移动端可用，验收。

预估工期 3–4 天，4 个 PR 串行合入主战场分支后再合 main。

---

## 9. 删除的功能与代码

**PR 3 中删除**（一次性删除，避免在 PR1/PR2 中留半成品 fallback）：

- `Translate.vue:79-102` — `_loadMastered` `_saveMastered` `toggleMastered` + `MASTERED_KEY` 常量
- `Translate.vue:166-198` — `flashIdx` `flashRevealed` `flashPool` `flashCurrent` `flashReveal` `flashNext` `flashMaster`（翻牌复习独立 tab → 改为生词本条目内 4 档评分）
- 模板里 Flashcard Tab 块（`Translate.vue:325-354`）
- 翻牌卡片相关 CSS（`Translate.vue:597-698`）

**PR 1 中修改**：

- `Translate.vue:67-71` — swap 函数：删除 `source.value = translated.value; translated.value = ''`，改为纯方向切换

---

## 10. 不动的部分

- 后端 `app/routers/translate.py` / `app/services/translate_service.py` / `app/prompts/translate.py`
- `static/translate.html`（legacy `/legacy/translate`）
- 其他 Vue views / composables / stores（**例外**：本期会抽 `frontend/src/components/BottomSheet.vue` 共享组件并把 `Practice.vue` / `VoiceSettings.vue` 的 sheet 迁过来，因为这是 sheet a11y 的合理收口；该改动在 PR4 范围内）
- V0.10 FSRS 后端实现
- 路由 `frontend/src/router/index.js` 的 `/translate` 入口

---

## 11. 验收标准

**翻译流程**：
1. 桌面端打开 `/translate`，呈现三栏布局，sidebar 默认展开
2. 输入中文，800ms 停顿后自动出英文译文
3. swap 按钮切方向，不动现有文本
4. stale response 测试：A 慢 / B 快 / A 晚返回 → translated 仍是 B 的结果
5. 反向校验：mode='backcheck' 期间编辑 source 不触发 debounce 译；退出后还原 snapshot

**单词交互**：
6. hover 英文单词 ≤ 200ms 出 IPA + 🔊；鼠标移到浮层不消失（sticky）
7. Tab 键可进入可交互 token，Enter / Space 打开词卡，Esc 关闭
8. click 英文单词调 `POST /practice/explain` (kind='word')，词卡内可收藏到生词本

**生词本**：
9. 整句收藏 → sidebar 生词本即时刷新（badge +1）
10. 4 档评分（`POST /vocab/{id}/rate`）→ 用返回 `item` 替换列表条目；`is_due` 变为 false 时从「到期」视图移出
11. 生词本显示 `due` 字段倒计时（不是 `next_review_at`）
12. item_type chip 过滤：单词 / 句子 / 全部

**历史**：
13. sidebar 历史 tab 显示最近 50 条；连续相同 source 不重复

**移动端**：
14. < 1024px 单列布局可用，sidebar 隐藏为 FAB
15. bottom-sheet a11y：打开后焦点落到 sheet 内；Esc / 遮罩关闭；关闭后焦点回 FAB；背景 inert + scroll lock

**清理**：
16. 删除 `MASTERED_KEY` / 翻牌相关代码，无 localStorage 残留
