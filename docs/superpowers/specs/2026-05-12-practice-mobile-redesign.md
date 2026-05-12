# Practice 手机端重设计

> Date: 2026-05-12
> Owner: Claude Code (实现) · Human (验收)
> 范围: 仅手机端 (`<768px`) Practice 页布局与交互；桌面端保持现状
> 原型: `mockups/practice-mobile-v2.html`
> 关联 issue: #26（手机端评分流后续重做）

## 目标

**主目标**：让用户在手机上用「单手 + 大拇指」就能完成一次完整的发音练习单循环（听原音 → 看解释 → 录音 → 回放），常用动作不需要滚屏才能找到。

**次目标（私教感）**：让用户明确知道**自己正在练哪一句、刚完成了什么、下一步该做什么**。Practice 是 Speakeasy「AI 陪伴式私教」的一个肢体，不是孤立的工具页 —— 它必须有引导感、反馈感、进度感。

## 现状问题

当前手机端 `Practice.vue` 沿用桌面端 PracticePlayer 的单栏堆叠：句子 → 解释按钮 → 词条/输入 → 语速/引擎下拉 → 播音/录音/回放 → 评分。所有控件挂在一条可滚动的列里，常用按钮（解释 / 发音 / 录音）随屏幕大小不同被推到看不见的位置。`📜` 抽屉是补丁，没解决主页面臃肿。

## 设计

### 布局骨架

```
┌─────────────────────────────────────┐
│ ← 返回   发音练习            ⚙ 设置 │ 顶栏 56px (sticky)
├─────────────────────────────────────┤
│ 1  Welcome to BBC English at Work.. │
│                                     │
│ 2 ▶ Could you give me the           │ 当前句卡（高亮）
│    ─schedule─ for tomorrow.         │ 单词可点；选中 = 下划线 + 底色
│    ⭕ 已选: schedule          ✕    │ 选中条仅在选词时出现
│                                     │
│ 3  Sure, you have a meeting at...   │
│ 4  ...                              │ 整页可垂直滚动
│ ...                                 │ tap 任意句 = 切为当前句
│                                     │
├──── coach bar ─────────────────────┤
│ 🎯 第 3/12 句 · 先听我读一次          │ 状态条（引导 + 进度）
├──── dock (sticky 底部，2 行) ───────┤
│  💡 解释整句         🔊 发音整句     │ 主标签随选中状态变化
│  🎤 录音 [开始录]   ▶ 回放 [无录音] │ 录音中变红 + 脉冲
└─────────────────────────────────────┘
```

### 单一作用对象模型

- **作用对象**：当前句（默认）∪ 当前句里的某个选中词
- 💡 解释 / 🔊 发音 永远作用在「当前作用对象」上
- **主标签** + 副标签**双层显式**标注当前作用对象，避免模式只藏在副标题里：

  | 状态 | 💡 主标签 | 💡 副标签 | 🔊 主标签 | 🔊 副标签 |
  |---|---|---|---|---|
  | 未选词 | `解释整句` | — | `发音整句` | — |
  | 选中 `schedule` | `解释单词` | `schedule` | `发音单词` | `schedule` |

  主标签层级（句/词）变化让用户一眼分清当前模式，副标签补充具体词面，**两条信息互不冗余**。

- 切换当前句 / 再点同词 / 点选中条的 ✕ → 取消选词

### 顶栏

- 左：`← 返回`
- 中：标题「发音练习」
- 右：单一胶囊按钮 `⚙ 设置`（背景 `--accent-soft`，强调可点）
- **删除**：原 `📜 句子列表`（列表直接在身体区）
- **删除**：原 `🔄 重新导入` 顶栏入口（收进 ⚙ sheet）
- **删除**：原 `📖 BBC 复习` 顶栏入口（收进 ⚙ sheet，仅 BBC 源时显示）

### 句子列表

- 整页一栏，垂直滚动，进页面/切句时 `scrollIntoView({block:'center'})`
- 每条卡：`<序号> <文本>`，tap 整行 = 切为当前句
- **当前句视觉差异**：
  - 左侧 3px `--accent` 色条
  - 背景 `--bg-elevated` + 轻阴影
  - 文本字号 18px / 加粗，相比非当前 15px / `--text-2`
  - 单词可点（拆词 + 标点保留）
  - 选中词条仅当前句显示
- 不显示 FSRS 状态点（issue #26 评分流重做后再考虑加回）

### 单词选择

- 仅当前句的单词渲染为 `<button class="word">`
- 拆词正则 `[A-Za-z][A-Za-z'-]*`，标点 / 空白作为文本节点保留
- 选中样式：`text-decoration: underline 2px var(--accent); background: var(--accent-soft); color: var(--accent)`
- 选中条样式：`background: var(--accent-soft)`，左侧⭕图标 + 已选词加粗，右侧 ✕ 按钮
- 切换当前句时自动清除选词

### Dock (`MobileActionDock.vue`)

- `position: sticky; bottom: 0`，`backdrop-filter: blur(20px) saturate(180%)`
- 两行四按钮，每按钮 minHeight 56px，flex: 1 等分宽
- **上行（accent 实色）**：
  - 💡 主标签：`解释整句` / `解释单词`；副标签：选词时显示词面
  - 🔊 主标签：`发音整句` / `发音单词`；副标签：选词时显示词面
- **下行（白底）**：
  - 🎤 录音：副标题 = `开始录` / 录音中 `录音中…` / 录过 `重录`；录音中按钮变红 + `rec-pulse` 动画
  - ▶ 回放：副标题 = `无录音` / `听自己`；无录音时视觉灰化但**仍可点**，通过 `aria-disabled="true"` 表达语义，点击 toast 提示「先录一段」
- 评分按钮 ❌ 暂不放（issue #26 跟进）
- `padding-bottom` 含 `env(safe-area-inset-bottom)` 适配 iOS
- **该 dock 是可复用容器模式**：仅承载 `2×2 主动作栅格 + coach bar 槽 + safe-area`，将来 Translate / Polish 出现高频底部动作时可沿用同一壳层（届时把组件名提升至 `frontend/src/components/common/`）

### 教练状态条 Coach Bar（dock 顶部，第一行）

一行轻量文本，**同时承担引导 / 反馈 / 进度感**。位置在 dock 内部最顶（在两行按钮之上），不再占用主操作区空间。

**v1 静态规则（不接 LLM，由前端状态推导）**：

| 状态 | 文案 |
|---|---|
| 进入页面 / 切句 / 无录音 / 无选词 | `🎯 第 N/M 句 · 先听我读一次` |
| 选中词时 | `🎯 第 N/M 句 · 解读 "<word>"` |
| TTS 播放中 | `🔊 听着…` |
| 录音中 | `🎤 录音中 · 念完点停止` |
| 录完未回放 | `✅ 收到了 · 回放听听自己` |
| 录完已回放 | `👍 比一比，节奏对齐了吗` |
| 第 1 句完成（无评分仍切到下一句） | `不错，已经顺下来 1 句了` |
| 第 5/10/N 句节点 | `👏 连续 N 句` |

**样式**：`padding: 8px var(--space-4); font-size: 12px; color: var(--text-2); background: var(--bg-elevated); border-top: 1px solid var(--border); display: flex; align-items: center; gap: 8px`。

**v2（未来）**：把 「TTS 播完」「录完节奏对齐评估」等接 LLM 微文案（短句、≤ 20 字），保持 1 行不变。本次 spec 不实施。

### FSRS 闭环缺口披露（非常驻）

由于本次手机端无评分入口，FSRS 卡的 due / stability 不会被更新。**披露策略**（**不**占主操作区）：

1. **首次进入提示**：用户首次进入 Practice 页时弹一次 toast（持续 4s）：「手机端暂不记录复习评分，仍可正常练习」。dismiss 后写 `localStorage['v2:practice.fsrs_notice_seen'] = 1`，不再弹。
2. **⚙ sheet 内常态说明**：sheet 底部加一条 disabled-looking 行 `ℹ︎ 关于复习评分`，描述当前为「只读 FSRS」状态，并 link to issue #26。
3. **issue #26 退出条件**：mobile 恢复至少 Again/Good 两档评分入口前，上述两处披露**不得删**。

### ⚙ 设置 sheet

从底部上滑，最大高度内容自适应：

```
┌── 设置 ─────────────────┐
│ 语速  [慢][偏慢][正常][偏快] │
│ 引擎  [Edge][豆包][Azure]  │
├──────────────────────┤
│ 📖 BBC 复习            > │ ← 仅 BBC EAW 源显示
│    基于 SRS 的文章复习    │
│ 🔄 重新导入字幕         > │
│    换一集、换一篇         │
└──────────────────────┘
```

- 语速 / 引擎 用分段控制器（segment picker）而非 select 下拉
- 操作行带图标 + 描述 + chevron，tap 后关 sheet 并执行
- 选中分段实色 accent 背景

### 行为细节

| 触发 | 行为 |
|---|---|
| 进页面 | 自动滚到 `currentIdx` 句，居中 |
| tap 非当前句 | 切当前句 → 清除选词 → 滚到中央 |
| tap 当前句的词 | 选中（再点同词 = 取消） |
| tap ✕ 选中条 / 切句 | 清除选词 |
| tap 💡 解释 | 调用 `/practice/explain/stream`，内容 = 整句 or 选中词 |
| tap 🔊 发音 整句 | 调用 `POST /practice/tts`（已有，沿用 `ttsBlob`） |
| tap 🔊 发音 选中词 | 调用 `POST /practice/explain/phonetic` 拿 IPA + 朗读单词（短 TTS 复用同一 `POST /practice/tts`） |
| tap 🎤 录音 | 启动 MediaRecorder；再 tap = 停止 |
| tap ▶ 回放 | 播放本地录音 blob |
| tap ⚙ | 打开 sheet |
| sheet 内选语速/引擎 | 更新 store，下次 TTS 生效 |
| sheet 内点 📖 | router push `bbc-review/<slug>` |
| sheet 内点 🔄 | 重置 store，回到 SubtitleImport 视图 |

### 状态机约束（真机必要）

1. **切句前的清理**：tap 非当前句 → 依序执行 `stopTTS()` → `clearSelectedWord()` → 切 `currentIdx` → 滚到中央。**录音中切句**不静默切，弹 native `confirm` 或自定义 sheet：「正在录音，停止并切句？/ 留在当前句」。
2. **录音绑定句子**：录音启动时记录 `recordingSegIdx = currentIdx`；停止前 `currentIdx` 必须 == `recordingSegIdx`，否则视为异常并丢弃 blob。
3. **异步响应去重**：每次 💡/🔊 请求生成 `requestKey = currentIdx + ':' + (selectedWord || '__sentence__') + ':' + Date.now()`；响应回来比对最新 key，不匹配则 silently drop 不渲染、不播音。
4. **TTS 并发**：新 TTS 请求触发时，先 `_releaseTTS()` 释放上一段 audio + objectURL，再起新 audio。
5. **选词清理**：切句 / 同词再点 / ✕ / `isMobile` watch 翻转（窗口缩放跨 768px 断点） → 全部清 `selectedWord`。

### 视觉规范

- 沿用全站 design tokens：`--accent: #3d6b4f`、`--bg-elevated`、`--radius` 等
- 不引入「pencil 草图风」—— Practice 是高频操作页，规整视觉的长时间使用舒适度优于风格化

### 可访问性（a11y）规范

1. **真实按钮语义**：句中的可点词渲染为 `<button class="word">`，**不允许**用 `<span>` + `onclick`。键盘 Enter/Space 可触发；选中态用 `aria-pressed="true"`。
2. **焦点环不剥离**：禁用全局 `button:focus { outline: none }`。改用 `:focus-visible` 定义自有 2px accent outline，键盘导航可见、触控点击不可见。
3. **真 disabled vs aria-disabled**：dock 的「▶ 回放」无录音时**不要**用 `disabled` 属性（会丢失 tabindex、读屏跳过）。改用 `aria-disabled="true"` + 视觉灰化，仍可点出 toast 提示。
4. **dock 按钮 aria-label**：动态描述当前作用对象，例如 `aria-label="解释，当前作用对象：schedule"` / `aria-label="发音整句"`。`<button>` 内部图标用 `aria-hidden="true"`。
5. **sheet focus 管理**：⚙ sheet 打开时初始焦点落到首个交互项；用 `inert` 属性把背景区屏蔽出无障碍树；关闭时焦点还给「⚙ 设置」按钮。
6. **录音状态可读**：录音中给按钮加 `aria-pressed="true"`；副标题文本 `录音中…` 包裹 `aria-live="polite"` 让读屏读出。
7. **触控目标**：dock 按钮 ≥ 56×56pt；句中词 button 高度 ≥ 28pt（行内紧凑容许，但通过 `padding` 保证可点）。

### Mobile edge cases（必处理）

| 场景 | 处理 |
|---|---|
| **长句 / 超长 token** | 句子文本加 `overflow-wrap: anywhere; word-break: break-word; hyphens: auto`；卡片不撑炸 |
| **横屏（max-height: 500px）** | dock 压成单行 4 按钮；句子卡高度自适应；隐藏 FSRS 提示文案 |
| **软键盘弹起 / Safari 动态 viewport** | 容器高度用 `100dvh`（非 `100vh`）；dock 用 `sticky` + 父容器滚动而非 `fixed`，键盘弹起时不会遮挡；本次 mobile 无输入框，键盘路径仅可能从外部 paste/语音输入触发，仍要 `dvh` 兜底 |
| **快速连续点词** | 副标题 / 选中条 / explain target 由同一 ref 派生，render 一致；prevent 双击放大 `touch-action: manipulation` |
| **录音中切句 / 切词** | 状态机约束 #1 + #2 强制 confirm + 丢弃异常 blob |
| **窗口缩放跨 768px 断点** | `watch(isMobile)` 触发清理：清选词、关 sheet、停 TTS、停录音 |

## 组件拆分

```
Practice.vue                          <- 容器：路由 + store + 本地 selectedWord/sheetOpen + ⚙ sheet + 首次 FSRS toast
├─ SubtitleImport.vue                 <- 不动（hasSource = false 时）
├─ MobileSentenceList.vue (新)        <- 列表 + 当前句卡（含词拆分 + 选词 + 选中条），通过 props 接 selectedWord
└─ MobileActionDock.vue (新)          <- coach bar + 4 按钮 + 主/副标签状态机
                                         · 命名中性，未来 Translate/Polish 可复用同一壳层
                                         · 若复用真发生，移到 components/common/

桌面端 (`>= 768px`) 仍走老的 SentenceList + PracticePlayer 双栏。
通过 CSS `@media` + 容器组件根据宽度切换子组件即可，不复制业务逻辑。
⚙ sheet 直接写在 Practice.vue 内（modal 性质，没必要早拆）；底部 sheet 公共组件等多页面共用时再抽。
```

### 共用 composables（已有，不动）

- `usePracticeStore` — currentSource / segments / currentIdx / cards / speed / provider
- `usePractice` — createCards / ttsBlob / rateCard
- `useRecorder` — MediaRecorder 包装
- `useAuthFetch` — 认证 + 错误处理

### 本地状态（不入 Pinia）

`selectedWord` 是纯瞬时 UI 状态，仅服务 mobile 视图，**不放进 `practiceStore`**（store 跨视图持久化会污染桌面端 / 跨断点切换）。改放在 `Practice.vue` 的 `ref`，通过 props/emit 传给 `MobileSentenceList` 和 `MobileDock`。同样地，`sheetOpen` / `recordingSegIdx` 也保持本地。

## 测试策略

手动用 Chrome DevTools mobile mode（iPhone 14 / 390×844、Pixel 5 / 393×851）验证：

1. **核心路径**：导入 BBC → 进入页面 → 当前句居中 → 点 💡 → ExplanationModal 打开（mock 数据时检查副标题为 `整句`）
2. **选词路径**：点当前句某词 → 下划线高亮 → 选中条出现 → 💡 副标题变为 `<word>` → 点 💡 → 调用带 word 参数
3. **切句**：点列表里其它句 → 该句变当前 → 选词清零 → 滚到中央
4. **录音闭环**：点 🎤 → 红色脉冲 → 点停止 → ▶ 回放从灰化变可点
5. **⚙ sheet**：点 ⚙ → 从底部滑出 → 改语速 → 关 sheet → 下次 🔊 用新语速
6. **safe-area**：在 iOS 模拟器看 dock 距底部 home indicator 有间距，顶栏距状态栏有间距
7. **回归**：宽屏（>=768px）切回桌面端布局，原有行为不变
8. **录音中切句**：录音中点其它句 → 必须弹 confirm，「停止并切句」起作用、「留在当前句」起作用
9. **横屏**：844×390 / 851×393 → dock 压成单行 4 按钮 / 句子卡正常，无内容被遮挡
10. **可访问性 · 键盘**：Tab/Shift+Tab 焦点顺序合理；句中词 Enter/Space 可选中；sheet 打开后 Tab 在 sheet 内循环
11. **可访问性 · 读屏**：VoiceOver/TalkBack 朗读 dock 按钮时报出当前作用对象（如「解释，当前作用对象：schedule」）；录音中读出「录音中」状态
12. **并发场景**：同一句内快速连点 5 个不同词，最终副标题 / 选中条 / explain target 一致；录音中 phonetic API 慢响应回来不会播旧词

不增加自动化测试（UI 重组、无新业务逻辑）；e2e 由人工走核心路径完成。

## Out of Scope

- **手机端评分**（issue #26）：暂不做，FSRS 状态读不写
  - 硬约束：在 #26 完成、至少 Again/Good 两档评分入口恢复前，**首次进入 FSRS toast** + **⚙ sheet 内 ℹ︎ 关于复习评分**两处披露**不得移除**
- **桌面端布局调整**：本次不动
- **滑动手势切句**：未来增强，本次只支持 tap
- **长按词预览音标**：未来增强
- **LLM 微文案 coach bar**（v2）：本次 v1 用静态规则推导，不接 LLM
- **进度条 / 已练 N/M 单独行**：进度信息**已**融进 coach bar，不再单独占行
- **暗色模式**：tokens.css 已留钩子，本次不实装

## 验收标准

- [ ] iPhone 14 模拟器单手操作，所有常用动作（💡/🔊/🎤/▶/⚙）拇指可达
- [ ] 切换当前句时选词正确清零
- [ ] dock 主标签随选词状态切换（句↔词），副标签显示具体词面
- [ ] coach bar 文案随状态推导（空闲/听/录/回放/切句）正确变化
- [ ] coach bar 始终展示「第 N/M 句」进度
- [ ] 首次进入 Practice 弹一次 FSRS toast，再次进入不弹
- [ ] ⚙ sheet 底部存在「ℹ︎ 关于复习评分」常态说明行
- [ ] ⚙ sheet 内的语速/引擎修改影响下次 🔊 发音
- [ ] 录音中切句弹 confirm，不静默切
- [ ] 异步 stale 响应被丢弃（手动模拟慢网测试）
- [ ] 横屏 dock 布局正常（coach bar 可隐藏以省高度）
- [ ] 句中词为真 `<button>`，键盘 Enter/Space 可选中
- [ ] `:focus-visible` 焦点环可见
- [ ] 旧路径（导入字幕、ExplanationModal 联动）不破
- [ ] 桌面端布局不变
- [ ] frontend bundle 增量 < 30KB gzip（无新大依赖）
