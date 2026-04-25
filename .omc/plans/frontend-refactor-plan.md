> **修订历史**
> - Pass 2（2026-04-23）：基于 Architect 3 MF + Critic 9 REV 重做 Pass 1；Human 决策丙延期 35d
> - **Pass 3（2026-04-24）**：Human 决策 α 移除 TypeScript（遵守 spec Non-Goal）；吸收 Critic Pass 2 的 5 条 blockers (B1-B5)

# Speakeasy 前端重构 · Pass 2 修订稿（35 工作日）

> 共识计划 · ralplan consensus Pass 2
> 本稿依据 Architect 3 条 Must-Fix + Critic 9 条 REV 重做 Pass 1 的 22.5 天方案
> Human 决策：Scope 全量 β · Timeline 35d（7 周）· 硬指标 A/B/C/G/H 全部保留

---

## 0. Workload Recalibration

### 0.1 基线 LOC（实测）

```
static/index.html        1577   (Chat 主战场)
static/practice.html     1529   (Practice 主战场，V0.4 已重写)
static/memory.html        575   (次战场)
static/translate.html     494   (次战场)
static/review.html        429   (次战场)
static/login.html         169   (次战场)
static/js/app.js          458   (Chat 业务逻辑)
static/js/stt-provider.js 240   (STT + 倒计时 + VAD 混合)
static/js/ask-panel.js    266   (划词解读抽屉)
static/js/tts-provider.js  95
static/js/auth.js          55
static/js/utils.js         38
static/js/config.js        10
─────────────────────────────
合计                     5935 行
```

### 0.2 生产力假设

| 参数 | 取值 | 依据 |
|---|---|---|
| 单人日净产出（新写+测试） | 150 行/人日 | 业界 Vue3+Pinia+Vitest 新项目中位 |
| 迁移折扣（已有逻辑移植） | 0.7× | 业务逻辑已验证，减耗 30% |
| 审查/返工 buffer | +15% | 共识模式双 reviewer 循环 |
| Must-Fix 复杂度加成 | +2d | PWA scope 悖论 + useSTT 三拆分 |

### 0.3 35d 推导

```
净开发：5935 行 × 0.7 折扣 / 150 行·日 = 27.7 人日
硬指标验收（A/B/C/G/H 各 0.5d）     = 2.5 人日
P0 前置（pytest 扫描 + 脚手架选型）  = 1.5 人日
Phase 0.5 Login 冒烟                  = 0.5 人日
buffer 15%                            = 4.8 人日
Must-Fix 加成                          = 2 人日
─────────────────────────────────────────
理论总量                               ≈ 39 人日
压缩到 Human 丙决策                   = 35 人日（-4d 通过并行 Phase 4 次战场壳化吸收）
```

-4d 吸收机制：Phase 4 次战场壳化可与 Phase 3-T5 生词本（R5 兜底项）并行穿插于 D21-D26；
Phase 4 P4-T1/T2/T3 采用"壳化"（仅路由 + auth guard + vanilla 脚本移植，不重写业务逻辑），
单页预算由 2d 压至 1–1.5d。若 Phase 3 超期，压缩失败即回到 39d 预算并通告 Human。

**落点：35 工作日 ± 2d，95% 置信区间 [33, 38]。**

---

## 1. RALPLAN-DR（修订）

### 1.1 Principles（5 条）

1. **先搭骨架再切肉** —— Phase 0 脚手架可跑通 Login 冒烟后再切主战场
2. **可回滚优于激进** —— `/legacy/*` 路由与新版共存两周，灰度按用户 UID 尾号切流
3. **composable 粒度单一职责** —— STT/TTS/Countdown/VAD 一一对应，禁止混合 provider
4. **测试耦合零债务** —— pytest HTML grep 为 P0，任何新 Vue 组件不得让老测试通过旧路径躲过
5. **Bundle size 即契约** —— CI 预算 300KB gzip，超支即 revert

### 1.2 Decision Drivers（top 3）

| # | Driver | 权重 |
|---|---|---|
| D1 | 迭代速度（Chat/Practice 后续能 3 天加一个大功能） | 40% |
| D2 | 回滚安全性（单路径挂载 + UID 灰度） | 35% |
| D3 | 硬指标可验收（A/B/C/G/H reproducibility） | 25% |

### 1.3 Options（3 个，含 1 已弃选）

#### Option A（选中）· 单挂载 + UID 灰度 + 三周 composable 先行

- 挂载：Vite build → `/static/dist/`，FastAPI `/` → `dist/index.html`，老版保留 `/legacy/`
- composable 三拆：useSTT / useCountdown / useAudioVAD 独立
- Chat 分两段：2a 基础 3d + 2b 高复杂度 4d，Phase 2.5 Login 调剂 0.5d
- 35d 执行，Phase 5 灰度 5% → 50% → 100%

**Pros**：回滚 1 条 route 切换；composable 解耦利于后续 TDD；Phase 2.5 给 Chat 高复杂度留喘息
**Cons**：`/legacy/` 需保留两周构建产物双份占磁盘（~5MB，可接受）

#### Option B（备选）· 子路径挂载 `/v2/*`

- `/v2/` 新版，`/` 保持老版，切流通过改 `/` 的 FileResponse
**Pros**：SW scope 完全隔离
**Cons**：用户已有书签 `/practice` 需额外跳转层；SEO/分享链接双地址语义混乱；**淘汰**

#### Option C（备选）· 全量 cutover 单次替换

**Pros**：简单
**Cons**：违反 D2 回滚安全性；Architect Must-Fix #1 明确否决；**淘汰**

> 仅 Option A 进入最终方案。B/C 的失效原因已入 ADR-005 Alternatives 节。

---

## 2. Phase 切分（35 工作日）

### 总览表

| Phase | 工期 | 起止日 | 核心产物 |
|---|---|---|---|
| **P0 前置** | 1.5d | D1–D1.5 | 脚手架选型冻结 + pytest HTML 扫描清单 + CI bundle 预算 |
| **Phase 0** 骨架 | 2.5d | D2–D4.5 | Vite + Vue3 + Pinia + Router 跑通 + FastAPI `/legacy/` 路由 |
| **Phase 0.5** Login 冒烟 | 0.5d | D5 | 登录跑通新壳，作为 milestone gate |
| **Phase 1** composables | 4d | D6–D9 | useSTT/useCountdown/useAudioVAD/useTTS/useSSE/useAuthFetch |
| **Phase 2a** Chat 基础 | 3d | D10–D12 | 消息渲染 + 发送 + SSE 流式 + 历史加载 |
| **Phase 2.5** Login polish | 0.5d | D12.5 | authFetch 401 接入 authStore + 记忆化重定向 |
| **Phase 2b** Chat 高复杂度 | 4d | D13–D16 | STT+VAD+倒计时 + TTS 队列 + 划词解读抽屉 + ask-panel |
| **Phase 3** Practice 重写 | 6d | D17–D22 | B站字幕 + 批量建卡 + FSRS 复习 + 录音对比 |
| **Phase 4** 次战场壳化 | 4d | D23–D26 | Memory(双脚本) / Translate / Review 三页迁入壳 |
| **Phase 5** PWA + 硬指标验收 | 4.5d | D27–D31.5 | SW 注册 + A/B/C/G/H 全绿 + bundle < 300KB |
| **Phase 6** 灰度 | 3.5d | D32–D35 | UID 尾号 5%→50%→100% + 回滚 runbook + `/legacy/` 清理计划 |

---

### P0 前置（D1–D1.5 · 1.5d）

#### P0-T1 · pytest HTML 耦合扫描 · 0.5d

- **命令**（写入 `scripts/scan_html_coupled_tests.sh`）：
  ```bash
  grep -rln 'static/.*\.html\|static/js/' tests/ | tee .omc/plans/html-coupled-tests.txt
  ```
- **产物**：`.omc/plans/html-coupled-tests.txt` 应含 9 个 `test_v07_*.py` 文件：
  `test_v07_followup.py / test_v07_followup2.py / test_v07_step4.py / test_v07_step5.py / test_v07_step6.py / test_v07_step7.py / test_v07_step8.py / test_v07_step9.py / test_v07_step10.py`
- **完成判据**：清单输出且每个文件标注「保留 / 改写 / 废弃」决策；`grep -rln 'static/.*\.html\|static/js/' tests/ | wc -l == 9`
- **文件清单**：`scripts/scan_html_coupled_tests.sh`、`.omc/plans/html-coupled-tests.txt`

#### P0-T2 · 脚手架选型冻结 · 0.5d

- 固化版本：Vue 3.4 / Vite 5 / Pinia 2 / Vue Router 4 / Vitest 1.2
- 遵守 spec Non-Goal，本次重构不引入 TypeScript；composable/store 用 JSDoc 注解类型
- **完成判据**：`frontend/package.json` 提交，npm ci 一次通过
- **文件清单**：`frontend/package.json`、`frontend/vite.config.js`

#### P0-T3 · CI bundle 预算钩子 · 0.5d

- GitHub Actions 新增 `bundle-size.yml`，阈值 `gzip<300KB` 硬门槛
- 使用 `vite-bundle-visualizer` + `size-limit`
- **完成判据**：PR 超 300KB 时 CI 红
- **文件清单**：`.github/workflows/bundle-size.yml`、`frontend/.size-limit.json`

---

### Phase 0 · 骨架（D2–D4.5 · 2.5d）

#### P0a-T1 · Vite + Vue3 脚手架 · 1d

- `frontend/` 目录初始化，Vue Router + Pinia wired
- `src/main.js` / `src/App.vue` / `src/router/index.js` / `src/stores/auth.js`
- **完成判据**：`npm run build` 产出 `frontend/dist/`；本地 `vite preview` 打开空壳路由
- **文件清单**：`frontend/src/main.js`、`frontend/src/App.vue`、`frontend/src/router/index.js`、`frontend/src/stores/auth.js`

#### P0a-T2 · FastAPI `/legacy/*` 路由 + dist 挂载 · 1d

- **main.py diff**（见第 4 节伪代码）
- 老版 6 条 FileResponse 从 `/` 全量平移到 `/legacy/`
- 新增 `/` → `frontend/dist/index.html`（SPA catch-all）
- `/static` 保留兼容 assets；新增 `/assets` → `frontend/dist/assets/`
- **完成判据**：
  - `curl /legacy/practice` 返回旧 practice.html
  - `curl /` 返回新 Vue 壳
  - 9 个 HTML-coupled pytest 全部改指 `/legacy/` 后全绿（由 P0-T1 清单驱动）
- **文件清单**：`main.py`、`tests/test_legacy_routes.py`、9 个被修订的 `test_v07_*` 文件

#### P0a-T3 · Vitest + ESLint + Prettier · 0.5d

- **完成判据**：`npm run test` / `npm run lint` / `npm run format:check` 三条命令均可跑
- **ESLint 规则**：`'vue/no-restricted-syntax': ['error', "VAttribute[key.rawName^='on']"]`
  禁止 Vue template 中使用原生 inline 事件属性（onclick / onmouseover / onmouseout / onmouseenter）
- **背景**：实测全站 76 处 inline handlers（index 29 / practice 30 / memory 12 / login 3 / translate 2 / review 0），工作量已埋入 Phase 2a/2b/3/4 预算，此规则确保零遗漏
- **文件清单**：`frontend/vitest.config.js`、`frontend/.eslintrc.cjs`、`frontend/.prettierrc`

---

### Phase 0.5 · Login 冒烟里程碑（D5 · 0.5d）

#### P05-T1 · Login.vue 最小可用 · 0.5d

- `src/pages/Login.vue`（纯表单）+ `authStore.login()` 打 `/auth/login`
- 登录成功路由到 `/` 占位 Home.vue
- **完成判据（milestone gate）**：
  - 用户在浏览器从 `/login` 登录成功到达 `/`
  - `localStorage.token` 写入
  - 刷新 `/` 仍保持登录态
  - 失败路径弹 error message
- **文件清单**：`frontend/src/pages/Login.vue`、`frontend/src/pages/Home.vue`、`frontend/src/stores/auth.js`（补全）

---

### Phase 1 · composables（D6–D9 · 4d）

> Must-Fix #3：useSTT 拆三；所有 composable 不直接依赖 router

#### P1-T1 · useAuthFetch · 0.5d

- 401 自动调 `authStore.logout()`（由 store 触发路由跳转，composable 不引 router）
- 所有后续 composable 依赖此 wrapper
- **完成判据**：单测覆盖 200/401/500/timeout 4 分支，100% 覆盖率
- **文件清单**：`frontend/src/composables/useAuthFetch.js`、`frontend/src/composables/__tests__/useAuthFetch.spec.js`

#### P1-T2 · useSSE · 0.5d

- 基于 `AbortController`，卸载组件自动 abort
- **完成判据**：单测验证 abort 后不再派发 message 事件
- **文件清单**：`frontend/src/composables/useSSE.js` + spec

#### P1-T3 · useAudioVAD · 1d（从 stt-provider.js 抽出）

- 纯能量阈值 VAD，返回 `{ speaking: Ref<boolean>, start, stop }`
- **完成判据**：mock mediaStream 注入正弦波，能正确切换 speaking
- **文件清单**：`frontend/src/composables/useAudioVAD.js` + spec

#### P1-T4 · useCountdown · 0.5d

- 倒计时仅暴露 `{ remaining, start, pause, reset }`
- **完成判据**：单测覆盖 start→pause→resume→reset 全路径；**不得有全局方法**（Must-Fix #3 明确禁 startCountdown 后门）
- **文件清单**：`frontend/src/composables/useCountdown.js` + spec

#### P1-T5 · useSTT · 1d（只留录音+上传）

- 接口签名见第 6 节
- 依赖注入 useAudioVAD + useCountdown，但两者可独立使用
- **完成判据**：mock faster-whisper 返回，验证上传后 transcript ref 更新
- **文件清单**：`frontend/src/composables/useSTT.js` + spec

#### P1-T6 · useTTS · 0.5d

- edge-tts 队列 + `cancel()` 方法；切换消息时取消旧队列
- **完成判据**：播放中调 cancel 立即 pause + 清空队列
- **文件清单**：`frontend/src/composables/useTTS.js` + spec

---

### Phase 2a · Chat 基础（D10–D12 · 3d）

#### P2a-T1 · Chat.vue 脚手架 + MessageList · 1d

- 路由 `/` → `Chat.vue`，消息虚拟滚动（`@tanstack/vue-virtual`）
- **完成判据**：渲染 100 条 mock 消息 FPS > 55
- **文件清单**：`frontend/src/pages/Chat.vue`、`frontend/src/components/chat/MessageList.vue`、`frontend/src/components/chat/MessageBubble.vue`

#### P2a-T2 · 发送 + SSE 流式渲染 · 1d

- 接 `/chat`，增量 token 拼接
- **完成判据**：硬指标 G（SSE 流式延迟 ≤ 现状 +50ms）基准通过
- **文件清单**：`frontend/src/composables/useChat.js` + spec、`frontend/src/stores/chat.js`

#### P2a-T3 · 历史加载 + 会话切换 · 1d

- 打 `/history` 拉会话树
- **完成判据**：切换会话后首屏 < 300ms（P50）
- **文件清单**：`frontend/src/components/chat/SessionSidebar.vue`、`frontend/src/stores/history.js`
- **完成判据（inline handler 清零）**：`grep -E 'onclick=|onmouseover=|onmouseout=|onmouseenter=' frontend/src/ | wc -l == 0`

---

### Phase 2.5 · Login polish（D12.5 · 0.5d）

#### P25-T1 · authFetch 401 全链路 + 记忆重定向 · 0.5d

- 登录前路径记在 `sessionStorage.__redirect_after_login`
- 登录后回跳
- **完成判据**：
  - 未登录访问 `/practice` → 跳 `/login` → 登录成功回 `/practice`
  - 任意 API 401 → authStore.logout() → `/login`
- **文件清单**：`frontend/src/stores/auth.js`（补全 redirect 逻辑）、`frontend/src/router/guards.js`

---

### Phase 2b · Chat 高复杂度（D13–D16 · 4d）

#### P2b-T1 · STT + VAD + 倒计时三合一 UI · 1.5d

- 录音按钮 + 波形 + 倒计时气泡；三 composable 各管各事，UI 聚合
- **完成判据**：
  - 硬指标 A（STT→SSE 端到端 ≤ 现状 +100ms）通过
  - VAD 触发静音 600ms 自动停录
- **文件清单**：`frontend/src/components/chat/VoiceRecorder.vue`

#### P2b-T2 · TTS 自动播放 + 队列取消 · 1d

- 消息到齐后自动 tts；切会话/新消息 cancel 旧队列
- **完成判据**：连发 3 条消息，仅最后一条被播
- **文件清单**：`frontend/src/components/chat/TtsPlayer.vue`

#### P2b-T3 · 划词解读抽屉（ask-panel） · 1.5d

- 长按/划选文本 → 右侧抽屉 → 打 `/ask`（V0.7）
- 抽屉支持生词本收藏 + FSRS 入库
- **完成判据**：
  - 硬指标 B（划词响应 < 150ms 打开抽屉）通过
  - 抽屉收藏后 `/memory/facts` 新增一条
- **文件清单**：`frontend/src/components/chat/AskDrawer.vue`、`frontend/src/composables/useAsk.js`
- **完成判据（inline handler 清零）**：`grep -E 'onclick=|onmouseover=|onmouseout=|onmouseenter=' frontend/src/ | wc -l == 0`

---

### Phase 3 · Practice 重写（D17–D22 · 6d）

#### P3-T1 · Practice.vue 脚手架 + 路由 · 0.5d

- `/practice` → `Practice.vue`，三 tab：新建 / 复习 / 列表
- **文件清单**：`frontend/src/pages/Practice.vue`、`frontend/src/router/index.js`

#### P3-T2 · B站字幕提取 + 手动文本 · 1.5d

- 调 `/practice/subtitles`，loading/error/empty 三态
- **完成判据**：输入 B站链接 → 展示字幕预览 ≤ 2s
- **文件清单**：`frontend/src/components/practice/SubtitleFetcher.vue`、`frontend/src/composables/useSubtitle.js`

#### P3-T3 · 批量建卡 flow · 1d

- 选中字幕行批量勾选 → POST `/practice/cards`
- **完成判据**：50 行字幕一次创建 < 1.5s，UI 不卡顿
- **文件清单**：`frontend/src/components/practice/CardBatchBuilder.vue`

#### P3-T4 · FSRS 复习闭环 · 2d

- 录音 → `/practice/cards/{id}/review` → 下一张
- 展示 due 列表 / review_count / next_review
- **完成判据**：
  - 硬指标 C（Practice 首屏 < 500ms） 通过
  - 硬指标 H（录音→评分 UI 反馈 < 2s）通过
- **文件清单**：`frontend/src/components/practice/ReviewCard.vue`、`frontend/src/components/practice/Recorder.vue`、`frontend/src/composables/usePractice.js`
- **完成判据（inline handler 清零）**：`grep -E 'onclick=|onmouseover=|onmouseout=|onmouseenter=' frontend/src/ | wc -l == 0`

#### P3-T5 · 生词本 + 删除 · 1d

- 列表页 + 软删除交互
- **文件清单**：`frontend/src/components/practice/CardList.vue`

---

### Phase 4 · 次战场壳化（D23–D26 · 4d）

#### P4-T1 · Memory.vue 双脚本模式 · 1.5d

> Critic REV #10：Memory 用 `<script>` 原生 + `<script setup>` 空壳

- `<script setup>` 仅做路由 guard + auth 注入
- `<script>`（非 setup）原样移植 `memory.html` 的 vanilla JS，用 `onMounted` 钩挂 DOM
- **完成判据**：memory 三层视图（profile/cards/facts）与老版功能对等
- **文件清单**：`frontend/src/pages/Memory.vue`

#### P4-T2 · Translate.vue · 1d

- 直接用 composable 重写（较薄，<500 行）
- **完成判据**：双向翻译 + 收藏 + 列表三功能过 e2e
- **文件清单**：`frontend/src/pages/Translate.vue`、`frontend/src/composables/useTranslate.js`
- **完成判据（inline handler 清零）**：`grep -E 'onclick=|onmouseover=|onmouseout=|onmouseenter=' frontend/src/ | wc -l == 0`

#### P4-T3 · Review.vue · 1d

- `/review/{session_id}` 复盘页
- **文件清单**：`frontend/src/pages/Review.vue`

#### P4-T4 · 顶部导航 + 侧栏整合 · 0.5d

- 统一 AppShell 含 nav + auth badge
- **文件清单**：`frontend/src/layouts/AppShell.vue`

---

### Phase 5 · PWA + 硬指标验收（D27–D31.5 · 4.5d）

#### P5-T1 · Service Worker 单挂载 scope · 1d

> Must-Fix #1：scope 为 `/`，`/legacy/*` 从 SW 白名单排除

- `vite-plugin-pwa` 注入 `navigateFallbackDenylist: [/^\/legacy\//]`
- **完成判据**：
  - DevTools → Application → SW scope = `/`
  - 访问 `/legacy/practice` 不走 SW
- **文件清单**：`frontend/vite.config.js`（PWA 配置块）、`frontend/public/manifest.webmanifest`

#### P5-T2 · 离线页 + 预缓存策略 · 1d

- runtime cache: GET `/chat`（stale-while-revalidate），POST 全部 networkOnly
- **完成判据**：飞行模式打开 `/` 展示离线页
- **文件清单**：`frontend/src/pages/Offline.vue`

#### P5-T3 · 硬指标 A/B/C/G/H 验收 · 2d

- 按第 5 节的 reproducible 步骤逐条跑
- 任一项未达 → 回到对应 Phase 修复
- **完成判据**：5 项全绿，结果写入 `.omc/plans/hard-metrics-report.md`
- **文件清单**：`.omc/plans/hard-metrics-report.md`、`frontend/perf/*.js`

#### P5-T4 · Bundle 预算终检 · 0.5d

- `npm run build` → gzip < 300KB；超支则 split-chunk
- **完成判据**：CI 绿
- **文件清单**：`frontend/.size-limit.json`（阈值最终锁定）

---

### Phase 6 · 灰度（D32–D35 · 3.5d）

#### P6-T1 · UID 尾号灰度中间件 · 1d

- FastAPI 中间件：cookie `__uid` 末位落 0–9，0 入新版，1–9 入 `/legacy/`
- 环境变量 `GRAY_PERCENT` 控制（初始 10）
- **完成判据**：`GRAY_PERCENT=10` 时 10% 用户命中新版（日志采样验证）
- **文件清单**：`middleware/gray_release.py`、`tests/test_gray_release.py`

#### P6-T2 · 灰度 5% → 50% → 100% · 1.5d

- 每档观察 4 小时，错误率 / 首屏 / SSE 延迟三指标无退化即推进
- **完成判据**：三档全通过，100% 稳定 6 小时
- **文件清单**：`.omc/plans/gray-release-log.md`

#### P6-T3 · 回滚 runbook + `/legacy/` 清理计划 · 1d

- runbook：一条 `GRAY_PERCENT=0` env 回滚
- `/legacy/` 保留期：100% 后再保留 14 天方可删除
- **完成判据**：runbook 文档 + `/legacy/` 删除 PR 草稿
- **文件清单**：`docs/runbook-frontend-rollback.md`、`.omc/plans/legacy-retire-plan.md`

---

## 3. 逐条 REV/MF 回应

| # | 来源 | 内容 | 回应 Phase 子任务 |
|---|---|---|---|
| MF1 | Architect | PWA SW scope 悖论 → 单挂载 | P0a-T2 路由改造 + P5-T1 SW 单 scope |
| MF2 | Architect | Chat 切 2a+2.5+2b | Phase 2a / 2.5 / 2b 拆三段 |
| MF3 | Architect | useSTT 拆三 composable | P1-T3 / P1-T4 / P1-T5 |
| REV4 | Critic | 工期重算 | 第 0 节 Workload Recalibration |
| REV5 | Critic | FastAPI 6 route 迁移 | P0a-T2 + 第 4 节 diff |
| REV6 | Critic | 硬指标 reproducible | 第 5 节完整步骤 |
| REV7 | Critic | pytest HTML 扫描前置 | P0-T1 |
| REV8 | Critic | Login 冒烟里程碑 | Phase 0.5 |
| SF9 | Critic | keep-alive 决策 | 第 7 节明文 |
| SF10 | Critic | Memory 双脚本 | P4-T1 |
| SF11 | Critic | authFetch 401 走 store | P1-T1 接口约束 |
| SF12 | Critic | Bundle 预算 + AbortController + TTS 取消 | P0-T3 / P1-T2 / P1-T6 |

---

## 4. FastAPI 路由迁移 diff 伪代码

### Before（main.py 当前状态 · line 59–86）

```python
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.get("/review")
async def review_page():
    return FileResponse("static/review.html")

@app.get("/memory")
async def memory_page():
    return FileResponse("static/memory.html")

@app.get("/practice")
async def practice_page():
    return FileResponse("static/practice.html")

@app.get("/translate")
async def translate_page():
    return FileResponse("static/translate.html")

@app.get("/login")
async def login_page():
    return FileResponse("static/login.html")
```

### After（Phase 0a-T2 目标）

```python
# ── legacy 前缀：老版原封不动保留两周（灰度 + 回滚用） ─────────────
app.mount("/legacy/static", StaticFiles(directory="static"), name="legacy-static")

@app.get("/legacy/")
async def legacy_root():
    return FileResponse("static/index.html")

@app.get("/legacy/review")
async def legacy_review():
    return FileResponse("static/review.html")

@app.get("/legacy/memory")
async def legacy_memory():
    return FileResponse("static/memory.html")

@app.get("/legacy/practice")
async def legacy_practice():
    return FileResponse("static/practice.html")

@app.get("/legacy/translate")
async def legacy_translate():
    return FileResponse("static/translate.html")

@app.get("/legacy/login")
async def legacy_login():
    return FileResponse("static/login.html")

# ── 新版 Vue 壳 SPA catch-all ─────────────────────────────────
app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="spa-assets")

# Phase 6 灰度中间件会在 `/` 前判定
@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    # 排除 API 前缀
    if full_path.startswith(("api/", "chat", "stt", "tts", "history",
                              "review/", "memory/", "practice/",
                              "translate/", "auth/", "ask/", "health",
                              "debug/", "settings/", "legacy/",
                              ".well-known/")):
        raise HTTPException(404)
    return FileResponse("frontend/dist/index.html")
```

### pytest 改写示例

```python
# tests/test_v07_step5.py  BEFORE
src = Path("static/practice.html").read_text(...)
assert '/static/js/ask-panel.js' in src
```

```python
# tests/test_v07_step5.py  AFTER（Phase 0a-T2 产出）
# 继续断言 legacy 路径（直到 Phase 6 100% 灰度 + 14 天再删）
src = Path("static/practice.html").read_text(...)
assert '/legacy/static/js/ask-panel.js' in src  # 路径前缀升级
```

---

## 5. 硬指标 A/B/C/G/H 可再现验收

> 全部在 Phase 5-T3（D29–D30.5）执行，任何一项未达 → 记入 BUG_LOG 并回 Phase 修复

### 5.0. Baseline 采集时机

baseline 数据由 **P0 首日（D1）** 在老版 `/` 上按同设备清单采集一次，
存入 `.omc/plans/hard-metrics-baseline.json`。
Phase 5-T3 的 `baseline_stt_end_to_end.json` 即指此文件。

**采集脚本**：`scripts/collect_baseline_metrics.sh`（D1 晚 commit 产物）
**验收**：D1 晚 commit 中包含 `.omc/plans/hard-metrics-baseline.json`

### 设备清单（固定环境）

- 设备：MacBook Pro M3 16GB / Chrome 122 / 网络限速 Fast 3G（1.6Mbps DL）
- 后端：本地 uvicorn，关闭 reload
- 用户：`test_e2e_user_v08_perf` 预置 20 条历史消息 + 10 张 pronunciation_card

### A · STT 端到端延迟

**步骤**：
1. 打开 Chat 页，点录音按钮
2. 朗读 "Hello how are you today"（5 词 ~2.5s）
3. 松开按钮启动 Playwright 计时器
4. 计时终点：SSE first token 到达
**通过判据**：P50 ≤ 现状 `baseline_stt_end_to_end.json` +100ms
**失败判据**：> +100ms 或 P95 > baseline +300ms

### B · 划词解读响应

**步骤**：
1. Chat 页长按一条 AI 消息 300ms 触发 selection
2. 抽屉 DOM `display: block` 作为终点
**通过判据**：抽屉打开 P95 < 150ms（不含网络请求，仅 UI 响应）
**失败判据**：任一次 > 200ms

### C · Practice 首屏

**步骤**：
1. Lighthouse CI run 3 次取中位
2. URL `/practice`
**通过判据**：FCP < 500ms，LCP < 1200ms
**失败判据**：FCP ≥ 500ms

### G · SSE 流式延迟

**步骤**：
1. Chat 发送一条消息
2. 测量 `/chat` 请求发出 → 第一个 token 到达的时间
3. 连续 10 次取 P50
**通过判据**：P50 ≤ baseline +50ms
**失败判据**：> +100ms

### H · 录音→评分 UI 反馈

**步骤**：
1. Practice 复习页，录音一句
2. 点提交 → UI 展示评分卡片
**通过判据**：P50 < 2s，P95 < 3s
**失败判据**：P50 ≥ 2s

### 报告产物

`.omc/plans/hard-metrics-report.md` 含：运行环境、baseline 数据、三次 run 数据、P50/P95、Pass/Fail、失败项的 Phase 回溯 issue 链接。

---

## 6. useSTT 三 composable 接口签名

### 6.1 useAudioVAD

```javascript
// frontend/src/composables/useAudioVAD.js

/**
 * @typedef {Object} UseAudioVADOptions
 * @property {number} [threshold=0.02]       - 能量阈值（RMS）
 * @property {number} [silenceTimeoutMs=600] - 静音超时 ms
 */

/**
 * @typedef {Object} UseAudioVADReturn
 * @property {import('vue').Ref<boolean>} speaking
 * @property {(stream: MediaStream) => void} start
 * @property {() => void} stop
 * @property {(cb: () => void) => void} onSilence - 静音超时回调
 */

/**
 * @param {UseAudioVADOptions} [opts]
 * @returns {UseAudioVADReturn}
 */
export function useAudioVAD(opts) { /* ... */ }
```

### 6.2 useCountdown

```javascript
// frontend/src/composables/useCountdown.js

/**
 * @typedef {Object} UseCountdownOptions
 * @property {number} durationMs - 必填，例 30000
 * @property {number} [tickMs=100]
 */

/**
 * @typedef {Object} UseCountdownReturn
 * @property {import('vue').Ref<number>} remaining - 剩余 ms
 * @property {import('vue').Ref<boolean>} running
 * @property {() => void} start
 * @property {() => void} pause
 * @property {() => void} reset
 * @property {(cb: () => void) => void} onTimeout
 */

/**
 * @param {UseCountdownOptions} opts
 * @returns {UseCountdownReturn}
 */
export function useCountdown(opts) { /* ... */ }
// 强约束：不挂 window；不提供 startCountdown 全局后门（Must-Fix #3）
```

### 6.3 useSTT

```javascript
// frontend/src/composables/useSTT.js

/**
 * @typedef {Object} UseSTTOptions
 * @property {import('./useAudioVAD').UseAudioVADReturn} [vad]       - 依赖注入，可选
 * @property {import('./useCountdown').UseCountdownReturn} [countdown] - 依赖注入，可选
 * @property {string} [uploadUrl='/stt/upload']
 * @property {number} [maxDurationMs=30000]
 */

/**
 * @typedef {Object} UseSTTReturn
 * @property {import('vue').Ref<boolean>} recording
 * @property {import('vue').Ref<string>} transcript  - STT 识别结果
 * @property {import('vue').Ref<Error|null>} error
 * @property {() => Promise<void>} start
 * @property {() => Promise<void>} stop              - 停录 + 上传 + 等 transcript
 * @property {() => void} cancel
 */

/**
 * @param {UseSTTOptions} [opts]
 * @returns {UseSTTReturn}
 */
export function useSTT(opts) { /* ... */ }
// 关键：useSTT 只负责录音 + 上传；VAD 和 Countdown 由调用方自行组合
```

### 组合示例（Chat.vue 内）

```javascript
const vad = useAudioVAD({ threshold: 0.02, silenceTimeoutMs: 600 })
const countdown = useCountdown({ durationMs: 30000 })
const stt = useSTT({ vad, countdown })

vad.onSilence(() => stt.stop())
countdown.onTimeout(() => stt.stop())
```

---

## 7. keep-alive 决策

**决策**：Chat.vue 和 Practice.vue 启用 `<keep-alive>`；次战场（Memory/Translate/Review/Login）不启用。

**实现**（`App.vue`）：

```vue
<router-view v-slot="{ Component, route }">
  <keep-alive :include="['Chat', 'Practice']">
    <component :is="Component" :key="route.fullPath" />
  </keep-alive>
</router-view>
```

**理由**：
- Chat/Practice 含 SSE 连接、录音状态、滚动位置、FSRS 游标，缓存避免重建
- 次战场每次进入重拉数据即可，keep-alive 反而增加内存

**清理约束**：Chat/Practice 组件必须实现 `onDeactivated` 钩：
- 取消 SSE AbortController
- 停掉 TTS 队列（调 `useTTS.cancel()`）
- 停掉 STT 录音（调 `useSTT.cancel()`）
- 缓存滚动位置写入 store

---

### 7bis. 新老版 Storage 命名空间约束

- **新版 key 必须以 `v2:` 前缀**（如 `v2:auth.token`、`v2:chat.session`）
- **老版 key 保持原名不动**（`token` / `__redirect_after_login` 等）
- **回滚策略**：`/legacy/*` 切回时清 `v2:*` 不清原名
- **验收**：`grep -rE "localStorage\.(setItem|getItem|removeItem)\(['\"]" frontend/src/` 所有结果必须带 `v2:` 前缀

---

## 8. Top 7 风险（更新）

| # | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| R1 | SW scope 与 `/legacy/` 冲突导致回滚失效 | M | 高 | MF1 单挂载 + `navigateFallbackDenylist` + Phase 5-T1 DevTools 验证 |
| R2 | Chat.vue 复杂度爆炸拖慢 Phase 2b | M | 高 | 2a/2.5/2b 三段切 + Phase 1 composables 先行 + Phase 2.5 的 0.5d 调剂 |
| R3 | Bundle 超 300KB 触发 CI 红 | M | 中 | P0-T3 预算钩子 + split-chunk 预案（vendor/pages/composables 三 chunk） |
| R4 | pytest HTML 耦合漏改 | L | 中 | P0-T1 grep 扫描清单 + CI lint 拒 `static/*.html` 新引用 |
| R5 | Phase 3 Practice 6d 吃光 buffer | M | 中 | P3-T4 FSRS 闭环若超期，P3-T5 生词本延至 Phase 4 并行 |
| R6 | 灰度期用户反馈功能丢失 | L | 高 | 同一用户 cookie sticky + `/legacy/` 可手动切换 + runbook |
| R7 | TTS 队列切会话未取消导致错播 | M | 低 | P1-T6 cancel API + Phase 2b-T2 连发测试 + onDeactivated 钩 |

---

## 9. ADR-005 草稿 · Frontend Refactor 工期与路由策略

```markdown
# ADR-005 · 前端重构工期定为 35 工作日 · 单挂载 + `/legacy/` 回滚

## Status
Draft · 待 Human 确认

## Context
Pass 1 共识给出 22.5d 方案，Architect 提出 3 条 Must-Fix，Critic 9 条 REV。
核心争议：22.5d 无法吸收 Chat.vue 高复杂度 + PWA SW scope 改造 + useSTT 三拆分。

## Decision
1. **工期 35 工作日（7 周）**，基于 5935 行基线 + 150 行/人日 + 0.7 迁移折扣 + 15% buffer 推导。
2. **单挂载 + `/legacy/` 路由**：`/` 指向 Vue SPA，`/legacy/*` 保留 6 条老 FileResponse 两周，灰度切流靠 cookie UID 尾号中间件。

## Decision Drivers
- 迭代速度（后续 3 天加一个大功能）
- 回滚安全性（一条 env var 切回）
- 硬指标 A/B/C/G/H reproducibility

## Alternatives considered
- **Option B · `/v2/*` 子路径**：用户书签 & 分享链接双地址语义混乱，淘汰
- **Option C · 全量 cutover**：无回滚路径，违反 Decision Driver #2，淘汰
- **Pass 1 · 22.5d**：未吸收 Must-Fix #2/#3 复杂度，淘汰

## Why chosen
Option A 在三 Driver 上均得分最高；35d 相对 22.5d 增 55%，但 Must-Fix 覆盖 + Phase 2.5 冒烟 + 灰度期三项质量收益抵消。

## Consequences
### 正
- Chat.vue 分两段 + Phase 2.5 Login 调剂，降低 burnout 风险
- composable 粒度单一，后续 TDD 成本低
- `/legacy/` 14 天保留期给问题兜底

### 负
- `/legacy/` dist 双份占磁盘 ~5MB（Phase 6 后 14 天删除）
- pytest 9 文件需改路径前缀（P0-T1 批改）
- SW scope 白名单需维护

## Follow-ups
- Phase 6 100% 灰度 +14d 后删除 `/legacy/*` 路由和测试（新建单独 PR）
- 运行 30 天后复盘实际工期与 35d 偏差，补 ADR-005-followup
- Bundle 预算突破 300KB 时触发 ADR-006（chunk 分拆策略）
```

保存位置：`docs/adr/ADR-005-frontend-refactor-35d.md`（Phase 0 首日提交草稿）

---

## 10. Final Checklist

- [x] Workload Recalibration 给出 5935 行基线 + 35d 推导公式
- [x] RALPLAN-DR 含 5 Principles / 3 Drivers / 3 Options（2 已弃选并注明理由）
- [x] Phase 切分 11 阶段（P0 / 0 / 0.5 / 1 / 2a / 2.5 / 2b / 3 / 4 / 5 / 6）共 35d
- [x] 每个子任务粒度 0.5–2d，均含 testable 完成判据 + 文件清单
- [x] 12 条 MF/REV/SF 逐条回应并引用 Phase 子任务编号
- [x] FastAPI 路由迁移 diff 含 before/after + pytest 改写示例
- [x] 硬指标 A/B/C/G/H 给出设备清单 + reproducible 步骤 + 失败判据
- [x] useSTT/useAudioVAD/useCountdown 三接口签名确定，禁全局后门
- [x] keep-alive 决策明文：Chat/Practice 启用 + onDeactivated 清理
- [x] Top 7 风险已更新，SW scope / Bundle / pytest 耦合均覆盖
- [x] ADR-005 草稿含 Decision / Drivers / Alternatives / Why / Consequences / Follow-ups
- [x] Bundle CI 预算 < 300KB gzip + SSE AbortController + TTS cancel 全部落入 Phase
- [x] Phase 0.5 Login 冒烟作为 milestone gate
- [x] `/legacy/` 回滚路径 + UID 尾号灰度中间件 + 14d 保留期 runbook
- [ ] 待 Human 确认 ADR-005 最终版

---

*Pass 2 产出 · 35 工作日 · Scope β 全量 · 硬指标 A/B/C/G/H 硬保留*
