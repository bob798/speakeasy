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

- 输入变化后 `setTimeout(800ms)`，停顿后触发 `/translate/text`
- 前端 cache：`Map<`${text}::${direction}`, translated>`, LRU 100 条，session 级（不持久化）
- 编辑过程中若新输入命中 cache → 立即显示，不打 LLM
- 上一个未完成的请求 → AbortController cancel
- 触发条件：`source.trim().length > 0 && source.length <= 1000`
- **不触发**：仅空白字符变化、direction 切换时已有结果

### 4.2 方向自动检测

- 实时检测（输入时同步算）：中文 unicode 比例（`/[一-龥]/`）≥ 30% → `zh2en`，否则 `en2zh`
- TopBar 显示当前方向标签：`中文 ⇄ English`，左侧高亮源语言
- 用户可点 swap 手动覆盖；手动覆盖后 5 秒内不再自动重判（避免抖动）
- swap 行为：**只切方向**，不动 source/translated 文本（修正当前 bug）

### 4.3 译文区单词分词与交互

**分词**：纯 JS 正则 `/[\w'-]+|[^\s\w]+/g`，不引入额外库
- 英文分词：连字符词 `well-known`、缩略 `don't` 算一个 token
- 中文：按字符切（单字 token）
- 标点：独立 token，不可交互

**hover 行为**（仅 ≥1024px 桌面）：
- 鼠标停留 100ms → 调 `/practice/explain/phonetic`（GET 本地 IPA，毫秒级）
- 浮层（Popper.js 思路，但用原生 CSS `position: absolute`）显示：
  ```
  had
  /hæd/  🔊  ← 点这个朗读
  ```
- 鼠标移开 200ms 浮层消失

**click 行为**（桌面 + 移动 tap）：
- 调 `/practice/explain/stream`（NDJSON 流式，字段渐进）
- 浮层展开为完整词卡：
  ```
  had
  /hæd/  🔊
  have 的过去式。
  1. 拥有  2. 必须  3. 经历
  例：I had breakfast at 7.
  [⭐ 加入生词本]
  ```
- 词卡内的「加入生词本」直接调 `POST /vocab`（`item_type="word"`、`source_type="translate"`、`explanation_json` 存 LLM 解读结果以便复习时复用）
- 同一个词的解读结果用 `Map` 缓存 session 期

**性能优化**：分词只对 translated_text 做（最长 1000 字符 × 平均词长 5 ≈ 200 个 span，不卡 DOM）。

### 4.4 工具栏（右栏顶部）

- `▶ 发音`：整句 TTS（复用 `useTTS` composable）
- `⤵ 反向校验`：把当前 translated 作为 source，方向反过来重译，看翻译质量
  - 实现：source ← translated；direction ← 反转；触发翻译；translated 区临时显示「反向校验：xxx」
  - 再次点击恢复原文
- `⭐ 收藏整句`：调 `POST /vocab`（`item_type="sentence"`、`source_type="translate"`，V0.10 自动入 FSRS）

### 4.5 右侧 Sidebar

**整体**：
- 默认展开 320px；点 TopBar 📖 折叠/展开
- 折叠时主区扩到全宽
- 移动端 (< 1024px) sidebar 始终隐藏，📖 改为打开 bottom-sheet

**Tab 1 · 生词本**：
- 列表：`GET /vocab?source_type=translate&limit=200`（按需加 `item_type=word|sentence` 过滤 chip）
- 到期 badge：`GET /vocab?due=true&source_type=translate&limit=1` → 用 `count` 字段
- 每条目显示：source / translated / 下次复习倒计时（`vocab_service.list_items` 返回的 `next_review_at`，实现阶段确认字段名）
- **替换** 当前 `MASTERED_KEY` localStorage 逻辑 → 用后端 FSRS
- 每条目下方 4 档按钮（与 practice 风格一致）：`[Again] [Hard] [Good] [Easy]` → `POST /vocab/{id}/rate` payload `{rating: "again"|"hard"|"good"|"easy"}`
- 列表筛选：搜索框（>5 条出现）+ item_type chip（单词 / 句子 / 全部）

**Tab 2 · 历史**：
- localStorage key `v1:translate.history`
- 结构：`[{ source, translated, direction, timestamp }]`，FIFO 50 条
- 每次成功翻译 push 一条（去重：连续相同 source/direction 不重复）
- 点条目 → source/translated 灌回主区
- 「清空历史」按钮

### 4.6 移动端响应式 (< 1024px)

- TopBar：标题缩短、方向切换图标化
- 主区单列堆叠：输入 → swap 按钮（圆形悬浮，居中）→ 译文
- sidebar 改 FAB（右下角 📖）打开 bottom-sheet（高度 60vh，可拖拽）
- 单词无 hover，tap = click 行为
- safe-area inset 处理（沿用 `--safe-top` `--safe-bottom` 变量）

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
用户输入 → onInput
  ↓ (immediate)
  ├─ 字符计数 + 方向检测 + 错误状态
  ↓ (debounce 800ms)
  ↓ 检查前端 cache？
  ├─ 命中 → 直接渲染 translated
  └─ 未命中 → AbortController.abort() 上一个 → fetch /translate/text
                ↓ 返回 → cache.set + 渲染 + push history
                ↓ 错误 → 显示 inline error，不清空 translated
渲染 translated
  ↓ 分词（pure function, memoize on text）
  ↓ 每个词 span + 事件监听
  ↓
hover 词 → /practice/explain/phonetic (cache by word)
click 词 → /practice/explain/stream  (cache by word)
        → 展开词卡
        → ⭐ → POST /vocab (item_type=word)
```

---

## 6. 测试策略

### 单元测试（Vitest）
- 分词函数 `tokenize(text, lang)` 的边界用例（缩略、连字符、标点、中英混排）
- 方向检测函数 `detectDirection(text)` 的临界比例（30% 中文字符）
- LRU cache 容量行为
- History localStorage 去重 + FIFO

### E2E / 手测清单
- [ ] 输入中文，800ms 停顿后自动出译文
- [ ] 编辑中途快速改动 → 旧请求被 cancel
- [ ] 相同文本第二次输入 → 命中 cache，无网络请求
- [ ] swap 按钮：只切方向，不动文本
- [ ] hover 单词 100ms 后出 IPA 浮层
- [ ] click 单词 → 调 LLM，展开词卡 → ⭐ 收藏单词
- [ ] ⭐ 收藏整句 → sidebar 生词本立即出现新条目（badge +1）
- [ ] 生词本 4 档评分 → 后端 FSRS 更新（next_review_at 变化）
- [ ] 历史 tab：最近 50 条；连续相同 source 不重复
- [ ] sidebar 折叠 → 主区扩全宽
- [ ] 移动端 (< 1024px)：sidebar 隐藏，FAB 打开 bottom-sheet；hover 不触发
- [ ] safe-area：iPhone 刘海/底栏不遮挡

### 回归
- `/practice` `/chat` `/memory` 页面无影响（共享 composables 不动）
- `/legacy/translate` 不受影响

---

## 7. 风险与待定项

| 风险 | 缓解 |
|---|---|
| `next_review_at` 字段名 / 返回结构未确认 | 实现阶段先读 `app/services/vocab_service.py::list_items` 返回结构再下笔；若字段名不同同步改前端 |
| hover 浮层在密集中文译文上抖动 | 浮层 100ms 延迟出现，移开 200ms 延迟消失，且粘性区域允许鼠标进入浮层不消失 |
| 分词对长文本（接近 1000 字）的 DOM 性能 | 测试 1000 字英文 ≈ 200 个 span，浏览器 paint < 16ms 即可。如有问题改虚拟滚动（暂不做） |
| 单词解读 LLM 调用过频 | session 级 `Map<word, cache>`，同一个词只调一次 |
| 单词进 FSRS 后会和 sentence 一起出现在到期列表，影响主复习节奏 | 生词本 tab 加 item_type chip（单词 / 句子 / 全部），用户可独立控制；默认「全部」 |

---

## 8. 实施计划（高层）

详细分步任务由后续 writing-plans 阶段生成。粗粒度：

1. **拆分组件骨架** — 建 5 个 SFC 文件，先把当前 Translate.vue 内容平移过去
2. **三栏布局 + sidebar 折叠** — 静态 layout 先跑通，TopBar + 三栏可见
3. **debounce 自动译 + 前端 cache + 方向检测** — 替换现有翻译触发逻辑
4. **swap 修复** — 改为纯方向切换
5. **译文分词 + WordToken hover IPA** — 引入 `/practice/explain/phonetic`
6. **WordCard click 解读 + 单词收藏** — 引入 `/practice/explain/stream`
7. **反向校验 + 工具栏完善**
8. **Sidebar 生词本接入 FSRS（删 MASTERED_KEY）** — 评分按钮 + 倒计时
9. **Sidebar 历史 tab + localStorage**
10. **移动端响应式 + bottom-sheet**
11. **手测 + 回归**

预估工期 3–4 天，可分 PR：
- PR 1：1–4（结构 + 翻译流程）
- PR 2：5–7（单词交互）
- PR 3：8–9（sidebar）
- PR 4：10–11（移动端 + QA）

---

## 9. 删除的功能与代码

- `Translate.vue:79-102` — `_loadMastered` `_saveMastered` `toggleMastered` + `MASTERED_KEY` 常量
- `Translate.vue:166-198` — `flashIdx` `flashRevealed` `flashPool` `flashCurrent` `flashReveal` `flashNext` `flashMaster`（翻牌复习独立 tab → 改为生词本条目内 4 档评分）
- `Translate.vue:218-220` — swap 按钮把 translated 塞回 source 的逻辑
- 模板里 Flashcard Tab 块（`Translate.vue:325-354`）
- 翻牌卡片相关 CSS（`Translate.vue:597-698`）

---

## 10. 不动的部分

- 后端 `app/routers/translate.py` / `app/services/translate_service.py` / `app/prompts/translate.py`
- `static/translate.html`（legacy `/legacy/translate`）
- 其他 Vue views / composables / stores
- V0.10 FSRS 后端实现
- 路由 `frontend/src/router/index.js` 的 `/translate` 入口

---

## 11. 验收标准

1. 桌面端打开 `/translate`，呈现三栏布局，sidebar 默认展开
2. 输入中文，800ms 停顿后自动出英文译文
3. swap 按钮切方向，不动现有文本
4. hover 英文单词 ≤ 200ms 出 IPA + 朗读按钮
5. click 英文单词出完整词卡，词卡内可收藏到生词本
6. 整句收藏 → sidebar 生词本即时刷新
7. sidebar 历史 tab 显示最近 50 条
8. 移动端 (375px 宽) 单列布局可用，sidebar 隐藏为 FAB
9. 生词本中至少能看到 `next_review_at` 倒计时（评分按钮取决于 V0.10 接口现状）
10. 删除 `MASTERED_KEY` 相关代码，无 localStorage 残留
