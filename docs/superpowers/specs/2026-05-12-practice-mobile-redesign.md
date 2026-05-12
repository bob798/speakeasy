# Practice 手机端重设计

> Date: 2026-05-12
> Owner: Claude Code (实现) · Human (验收)
> 范围: 仅手机端 (`<768px`) Practice 页布局与交互；桌面端保持现状
> 原型: `mockups/practice-mobile-v2.html`
> 关联 issue: #26（手机端评分流后续重做）

## 目标

让用户在手机上用「单手 + 大拇指」就能完成一次完整的发音练习单循环（听原音 → 看解释 → 录音 → 回放），常用动作不需要滚屏才能找到。

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
├──── dock (sticky 底部，2 行) ───────┤
│  💡 解释 [整句]    🔊 发音 [整句]   │ 副标题随选中状态变化
│  🎤 录音 [开始录]   ▶ 回放 [无录音] │ 录音中变红 + 脉冲
└─────────────────────────────────────┘
```

### 单一作用对象模型

- **作用对象**：当前句（默认）∪ 当前句里的某个选中词
- 💡 解释 / 🔊 发音 永远作用在「当前作用对象」上
- 按钮**副标题显式标注**当前作用对象：
  - 未选词：副标题 = `整句`
  - 选中词：副标题 = `<word>`（例如 `schedule`）
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

### Dock

- `position: sticky; bottom: 0`，`backdrop-filter: blur(20px) saturate(180%)`
- 两行四按钮，每按钮 minHeight 56px，flex: 1 等分宽
- **上行（accent 实色）**：
  - 💡 解释：副标题动态 = `整句` / 选中词
  - 🔊 发音：副标题动态 = `整句` / 选中词
- **下行（白底）**：
  - 🎤 录音：副标题 = `开始录` / 录音中 `录音中…` / 录过 `重录`；录音中按钮变红 + `rec-pulse` 动画
  - ▶ 回放：副标题 = `无录音` / `听自己`；无录音时 `opacity: 0.45`，点击 toast 提示「先录一段」
- 评分按钮 ❌ 暂不放（issue #26 跟进）
- `padding-bottom` 含 `env(safe-area-inset-bottom)` 适配 iOS

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

### 视觉规范

- 沿用全站 design tokens：`--accent: #3d6b4f`、`--bg-elevated`、`--radius` 等
- 不引入「pencil 草图风」—— Practice 是高频操作页，规整视觉的长时间使用舒适度优于风格化

## 组件拆分

```
Practice.vue                         <- 容器：路由 + store + ⚙ sheet 状态
├─ SubtitleImport.vue                <- 不动（hasSource = false 时）
├─ MobileSentenceList.vue (新)       <- 列表渲染 + 切句
│  └─ MobileCurrentSentence.vue (新) <- 当前句卡：词拆分 + 选词 + 选中条
├─ MobileDock.vue (新)               <- 4 按钮 + 副标题状态机
└─ MobileSettingsSheet.vue (新)      <- ⚙ sheet：语速/引擎/📖/🔄

桌面端 (`>= 768px`) 仍走老的 SentenceList + PracticePlayer 双栏。
通过 CSS `@media` + 容器组件根据宽度切换子组件即可，不复制业务逻辑。
```

### 共用 composables（已有，不动）

- `usePracticeStore` — currentSource / segments / currentIdx / cards / speed / provider
- `usePractice` — createCards / ttsBlob / rateCard
- `useRecorder` — MediaRecorder 包装
- `useAuthFetch` — 认证 + 错误处理

### 新增 store 字段

- `selectedWord: string | null` — 当前选中词；切句时自动清零

## 测试策略

手动用 Chrome DevTools mobile mode（iPhone 14 / 390×844、Pixel 5 / 393×851）验证：

1. **核心路径**：导入 BBC → 进入页面 → 当前句居中 → 点 💡 → ExplanationModal 打开（mock 数据时检查副标题为 `整句`）
2. **选词路径**：点当前句某词 → 下划线高亮 → 选中条出现 → 💡 副标题变为 `<word>` → 点 💡 → 调用带 word 参数
3. **切句**：点列表里其它句 → 该句变当前 → 选词清零 → 滚到中央
4. **录音闭环**：点 🎤 → 红色脉冲 → 点停止 → ▶ 回放从 disabled 变可点
5. **⚙ sheet**：点 ⚙ → 从底部滑出 → 改语速 → 关 sheet → 下次 🔊 用新语速
6. **safe-area**：在 iOS 模拟器看 dock 距底部 home indicator 有间距，顶栏距状态栏有间距
7. **回归**：宽屏（>=768px）切回桌面端布局，原有行为不变

不增加自动化测试（UI 重组、无新业务逻辑）；e2e 由人工走核心路径完成。

## Out of Scope

- **手机端评分**（issue #26）：暂不做，FSRS 状态读不写
- **桌面端布局调整**：本次不动
- **滑动手势切句**：未来增强，本次只支持 tap
- **长按词预览音标**：未来增强
- **进度条 / 已练 N/M 统计**：暂不显示在手机顶栏（可由 ⚙ sheet 中点 📖 跳过去看）
- **暗色模式**：tokens.css 已留钩子，本次不实装

## 验收标准

- [ ] iPhone 14 模拟器单手操作，所有常用动作（💡/🔊/🎤/▶/⚙）拇指可达
- [ ] 切换当前句时选词正确清零
- [ ] dock 副标题随选词状态变化
- [ ] ⚙ sheet 内的语速/引擎修改影响下次 🔊 发音
- [ ] 旧路径（导入字幕、ExplanationModal 联动）不破
- [ ] 桌面端布局不变
- [ ] frontend bundle 增量 < 30KB gzip（无新大依赖）
