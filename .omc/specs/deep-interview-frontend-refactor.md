# Deep Interview Spec: Speakeasy 前端现代化重构（H5 + PWA）

## Metadata
- Interview ID: v07-frontend-refactor
- Rounds: 5
- Final Ambiguity Score: 5%
- Type: brownfield
- Generated: 2026-04-23
- Threshold: 20%
- Status: PASSED
- Challenge Modes Used: Contrarian (Round 4), Simplifier (Round 5)

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|---|---|---|---|
| Goal Clarity | 0.98 | 0.35 | 0.343 |
| Constraint Clarity | 0.95 | 0.25 | 0.238 |
| Success Criteria | 0.95 | 0.25 | 0.238 |
| Context Clarity | 0.85 | 0.15 | 0.128 |
| **Total Clarity** | | | **0.9455** |
| **Ambiguity** | | | **0.0545** |

## Goal

把 Speakeasy 前端从"原生 HTML/JS/CSS + 7 个独立 MPA 页面 + 内联代码"升级为"Vue 3 + Vite + PWA 的现代化 Web 应用"，**不做微信小程序**（推迟到出现明确驱动事件再议）。改造聚焦主战场两个页面（聊天、发音练习），其余五个页面做轻量响应式 + PWA 壳，交付一个在移动浏览器上体感接近原生 App 的渐进式 Web 应用。

## Constraints

- **单平台**：只做 H5（桌面浏览器 + 移动浏览器 + 微信内置浏览器），不做微信小程序，不做原生 App
- **单人 + Claude Code 协作**：无前端专职人员参与
- **工期目标**：3–4 周（需 Human confirm 后启动）
- **后端零改动**：FastAPI API 契约保持不变，V0.1–V0.7 所有接口复用
- **测试回归**：V0.1–V0.7 现有 pytest 套件必须 100% 通过
- **鉴权延续**：JWT + localStorage 方案保留，`authFetch()` 语义迁移到新封装
- **保留浏览器能力**：SSE、MediaRecorder、AudioVAD、AudioContext 全部保留——不因"跨端担忧"而削弱

## Non-Goals

- ❌ 不做微信小程序（Round 4 Contrarian 明确推迟）
- ❌ 不做原生 App（Round 2 明确移除）
- ❌ 不引入 React / Flutter / Taro / uni-app / Capacitor 等跨端框架
- ❌ 不重写登录、记忆、翻译、复盘、首页这五个页面（只做响应式 + PWA 壳）
- ❌ 不改动 FastAPI 后端 API 形态
- ❌ 不引入 TypeScript（单人 + 工期紧，延后评估）
- ❌ 不做离线缓存对话历史（D 指标未被选中）
- ❌ 不追 Lighthouse 性能分数（F 指标未被选中）

## Acceptance Criteria

### 硬指标（必须全部通过才算交付）

- [ ] **A. iPhone Safari 全功能可用**：聊天（含 SSE 流）、录音（MediaRecorder）、TTS 播放、翻译、V0.7 解读弹窗、AskPanel 追问、发音练习录音对比
- [ ] **B. PWA Standalone 模式**：从 iPhone Safari / Android Chrome 添加到主屏后，打开时脱离浏览器 UI，独立窗口运行；带 icon、带 splash screen
- [ ] **C. 跨浏览器兼容**：安卓 Chrome + 微信内置浏览器 + iOS Safari 三端核心功能可用
- [ ] **G. 回归测试全绿**：V0.1–V0.7 全部 pytest 套件通过（前端改造不应破坏任何后端行为）
- [ ] **H. 无 `:hover` / 无鼠标专属交互**：触屏设备上所有按钮/侧边栏/删除入口均可通过点击/长按完成；CSS 检查无裸 `:hover`（或用 `@media (hover: hover)` 包裹）

### 软指标（加分项，不阻塞交付）

- 主战场两个页面（聊天、发音练习）的 HTML/JS 从内联迁出到 `.vue` 单文件组件
- 构建产物单个 bundle < 300KB（gzip）
- 首屏 JS 延迟执行（code-split 次战场页面）

## Assumptions Exposed & Resolved

| 假设 | 挑战方式 | 结论 |
|---|---|---|
| "未来要做小程序 + App" | Contrarian：你有具体触发事件吗？ | **否**。"小程序"是习惯性假设，无渠道压力/增长假设/投放计划。决定推迟 |
| "跨端框架是必选项" | Contrarian：阉割版小程序还值得做吗？ | **否**。②=2 的功能降级已削弱了做小程序的 ROI，选 X 反方案 |
| "VAD 已被删除" | 代码核查：`stt-provider.js:7` `AudioVAD` 仍在 | **错**。VAD 仍是现役功能（BUG-004 改为用户主动触发后启动），重构必须保留 |
| "全家桶重写" vs 保守重构 | Simplifier：哪些页面真正需要重写？ | **只主战场**。聊天+发音练习两页共 3000 行，ROI 最高；其余 5 页 300–600 行改响应式即可 |
| "技术选型困难" | 用户授权决定 | **Vue 3 + Vite + vite-plugin-pwa**。理由：单人项目心智负担最小；Vue 3 Composition API 配合 Claude Code 产出效率高；无 React 历史经验不引入新范式 |

## Technical Context

### 当前代码事实（explore 报告）

**前端栈**：零框架 + 零构建 + 纯浏览器加载
- 7 个 HTML（2 个根 `index.html` 重复，5 个 `static/*.html`）
- 主战场：`static/index.html` 1577 行（聊天）、`static/practice.html` 1426 行（发音练习）
- 次战场：`translate.html` 494、`memory.html` 575、`review.html` 429、`login.html` 169
- JS 外置：`static/js/` 下 7 个文件（app.js / auth.js / config.js / stt-provider.js / tts-provider.js / ask-panel.js / utils.js）
- CSS：全部内联在 `<style>`，但 `:root` CSS 变量体系统一（accent 色、spacing token）

**关键封装已就位**
- `authFetch()` 统一 JWT 头 + 401 自动踢出（`auth.js:40-50`）
- `sttProvider` 统一语音识别（`stt-provider.js` 3 层降级：Whisper / VAD+倒计时 / SpeechRecognition）
- `ttsProvider` TTS 队列
- `AskPanel` 组件（V0.7 新抽象，已是跨页面复用雏形）

**迁移友好度评估**
- ✅ CSS 变量体系 → 可直接搬到 Vue 的 `<style>` 全局入口
- ✅ authFetch / sttProvider / ttsProvider → 可直接封装成 Vue 3 composables (`useAuth`, `useSTT`, `useTTS`)
- ✅ AskPanel → 可直接重写为 Vue SFC，V0.7 已是组件雏形
- ⚠️ 内联 `<script>` 里的业务逻辑（尤其 `index.html` 605-824 + 1115-1529） → 需要重构到 Vue 组件
- ⚠️ `document.getElementById` 17 处 → 换成 Vue 模板 `ref`
- ⚠️ 全局变量（userId / sessionId / chatHistory 等） → 迁到 Pinia store

### 目标技术栈

| 层 | 选型 | 依据 |
|---|---|---|
| 框架 | **Vue 3 Composition API** | 单人心智负担最小，Claude Code 产出熟练 |
| 构建 | **Vite** | 冷启动快，原生 ESM，HMR 体验 |
| 路由 | **Vue Router 4**（history 模式） | 替代当前 `<a href>` + `window.location.href` 硬跳 |
| 状态 | **Pinia** | 替代现有全局变量，TypeScript 友好（未来可迁） |
| PWA | **vite-plugin-pwa** | manifest + service worker 一键集成 |
| HTTP | 保留 `fetch` + authFetch 迁入 composable | 不引入 axios，减少体积 |
| UI 库 | **不引入 UI 库** | 现有 CSS 已成体系，重新设计反而破坏一致性 |
| 图标 | **@iconify/vue** 按需加载 | 替代现有内联 SVG |

### 架构草图

```
speakeasy-web/   (新前端项目根)
├── index.html                      # Vite 入口
├── vite.config.js
├── package.json
├── public/
│   ├── manifest.webmanifest        # PWA
│   ├── icons/                      # 各尺寸 icon
│   └── sw.js                       # vite-plugin-pwa 生成
├── src/
│   ├── main.js                     # createApp + pinia + router
│   ├── router/
│   │   └── index.js                # 7 页路由
│   ├── stores/
│   │   ├── auth.js                 # JWT + user state
│   │   ├── chat.js                 # session + messages
│   │   └── practice.js             # pronunciation cards
│   ├── composables/
│   │   ├── useAuthFetch.js         # 搬 authFetch
│   │   ├── useSTT.js               # 封装 sttProvider
│   │   ├── useTTS.js               # 封装 ttsProvider
│   │   └── useAskThread.js         # V0.7 ask-panel 逻辑
│   ├── components/
│   │   ├── AskPanel.vue            # V0.7 通用追问
│   │   ├── ChatBubble.vue
│   │   ├── ExplanationModal.vue    # V0.7 解读弹窗
│   │   └── ...
│   ├── views/
│   │   ├── Chat.vue                # 主战场 1：聊天（重写自 index.html）
│   │   ├── Practice.vue            # 主战场 2：发音练习（重写自 practice.html）
│   │   ├── Translate.vue           # 次战场：响应式迁移
│   │   ├── Memory.vue              # 次战场
│   │   ├── Review.vue              # 次战场
│   │   ├── Login.vue               # 次战场
│   │   └── Home.vue                # 首页
│   └── styles/
│       ├── tokens.css              # 搬 :root 变量
│       ├── reset.css
│       └── global.css
└── dist/                           # Vite build 输出，FastAPI 挂载这里替代当前 static/
```

### FastAPI 挂载调整

- 现状：`app.main` 挂 `static/` 目录返回 HTML
- 目标：改挂 `speakeasy-web/dist/`，由 Vite 构建产物取代
- `index.html` 走 Vue Router history 模式，FastAPI 404 fallback 到 `dist/index.html`

## Ontology (Key Entities)

| Entity | Type | Fields | Relationships |
|---|---|---|---|
| 前端 | 核心域 | 7 个 HTML、static/js/*、内联 CSS | 服务于 Speakeasy 用户界面层 |
| H5 / 移动浏览器 | 核心域 | iPhone Safari / Android Chrome / 微信 WebView | 重构后的主要运行环境 |
| 重构 | 核心域 | scope, timeline, acceptance criteria | 覆盖主战场 2 页 + 次战场 5 页壳化 |
| SPA | 核心域 | Vue 3 + Vue Router + Pinia | 替代当前 MPA 结构 |
| PWA | 核心域 | manifest, service worker, icons | 提供"像 App"的安装体验 |
| Vue 3 | 工具层 | Composition API, SFC | 新前端框架选型 |
| Vite | 工具层 | dev server, build, HMR | 新构建工具 |
| vite-plugin-pwa | 工具层 | manifest 生成, SW 注入 | PWA 能力实现 |

## Ontology Convergence

| Round | Entity Count | New | Changed | Stable | Removed | Stability Ratio |
|---|---|---|---|---|---|---|
| 1 | 5 | 5 | - | - | - | N/A |
| 2 | 6 | 1 (跨端框架) | 0 | 5 | 0 | 83% |
| 3 | 5 | 0 | 1 (小程序→微信小程序) | 4 | 1 (App) | 100% |
| 4 | 5 | 2 (SPA, PWA) | 0 | 3 | 2 (微信小程序, 跨端框架) | 60% |
| 5 | 8 | 3 (Vue3, Vite, vite-plugin-pwa) | 0 | 5 | 0 | 63% |

**说明**：Round 4 的稳定度下降是 Contrarian 模式的有效产出——问题框架从"跨平台重写"切换到"单平台现代化"，移除的实体是主动 scope 收窄。Round 5 新增的 3 个实体是"工具层"（框架、构建、插件），不是核心域实体变动。

## Interview Transcript

<details>
<summary>Full Q&A (5 rounds)</summary>

### Round 1 — Goal Clarity（方向分叉）
**Q:** 你真正承诺的终态是什么？（A 轻量派 / B 中间派跨端 / C 分裂派 / D 先 H5 后决定 / E 其它）
**A:** 用跨端
**Ambiguity:** 76% → 63% (Goal 0.15→0.50)

### Round 2 — Constraint Clarity（平台 + 功能底线）
**Q:** 哪个小程序？哪种 App？Speakeasy 音频/SSE/VAD 在小程序端能降级到什么程度？
**A:** 只做小程序 和 H5；VAD 我记着已经删除了（← 经验证此认知不准确，VAD 仍在 `stt-provider.js:7`）
**Ambiguity:** 63% → 52% (Goal 0.50→0.65, Constraint 0.20→0.40)

### Round 3 — Constraint Clarity（细化）
**Q:** 哪家小程序 + 功能底线三选一 + 工期人力？
**A:** a. 只做微信小程序；②=2 核心对齐+降级；技术不限
**Ambiguity:** 52% → 34%

### Round 4 — Contrarian（挑战前提）
**Q:** 为什么一定要做微信小程序？有具体触发事件吗？（甲渠道 / 乙增长 / 丙习惯 / 丁冗余 / 或 X 反方案）
**A:** 选择 X（先极致 H5 + PWA，小程序推迟）
**Ambiguity:** 34% → 20%

### Round 5 — Simplifier（压复杂度+定验收）
**Q:** 交付范围（α/β/γ/δ） + 5 条硬指标 + 工期
**A:** 选 β 主战场优先；硬指标 A+B+C+G+H；单人 + Claude Code，confirm 后启动
**Ambiguity:** 20% → 5% ✅

</details>

## Implementation Plan Sketch（供后续 Planner 参考）

### Phase 0：项目骨架（2 天）
- 新建 `speakeasy-web/`，Vite + Vue 3 + Router + Pinia + vite-plugin-pwa
- 搬 CSS tokens，建立 `styles/` 体系
- FastAPI 挂载切换：`static/` → `speakeasy-web/dist/`（保留 `static/audio_cache/` `static/tts_cache/`）
- 路由骨架：7 个空 `.vue` view + 404

### Phase 1：基础设施 composables（3 天）
- `useAuthFetch` — 搬 authFetch + 401 路由跳转
- `useSTT` — 封装 sttProvider（保留 AudioVAD 类）
- `useTTS` — 封装 ttsProvider
- `useAskThread` — V0.7 ask-panel 逻辑
- `stores/auth` + `stores/chat` + `stores/practice`

### Phase 2：主战场 1 — Chat.vue（5–7 天）
- 迁移 `index.html` 605–1529 行的业务逻辑
- 组件拆分：`ChatBubble` / `ChatInput` / `HistorySidebar` / `TopicCard` / `ExplanationModal`
- SSE 流式：继续用 `fetch().body.getReader()`（不引入 eventsource 库）
- hands-free 录音 + VAD 行为保留
- AskPanel 组件嵌入

### Phase 3：主战场 2 — Practice.vue（4–6 天）
- 迁移 `practice.html` 1426 行
- 组件拆分：`SubtitleImport` / `SentenceCard` / `RecordCompare` / `FSRSRater`
- B站/YouTube 字幕导入 UI + 音频对比

### Phase 4：次战场壳化（3–4 天）
- Translate / Memory / Review / Login / Home 五页
- 不重写业务逻辑，按 View 包一层 Vue 外壳
- 补响应式断点（目前仅 768/900）
- 删除所有 `:hover`（或包 `@media (hover: hover)`）

### Phase 5：PWA + 验收（2–3 天）
- vite-plugin-pwa 配置 manifest + icons + splash
- 真机 iOS Safari + Android Chrome 添加主屏测试
- 微信内置浏览器验证
- 跑全量 pytest 确认后端零回归
- 对照硬指标 A+B+C+G+H 逐条打勾

### 总工期估算：3–4 周（单人 + Claude Code 全天投入）
