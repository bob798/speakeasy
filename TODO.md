# TODO.md — Speakeasy 待办事项

---

## 待办列表

### TODO-001：下架 VAD 实时检测功能

- **优先级**：待定
- **背景**：VAD 检测效果不稳定，阈值调整后仍无法保证可靠性，用户体验差
- **方案**：
  - Hands Free 模式从 Voice Settings 中移除
  - activation 选项仅保留 Push to talk
  - 相关代码（`app/routers/vad.py`、`app/services/vad_service.py`、前端 Hands Free 逻辑）标记废弃或删除
- **影响范围**：V0.3.1 Step 4~6、`static/js/stt-provider.js` 中 VAD 相关逻辑
- **状态**：⬜ 待排期

---

### TODO-003：文章库 `/library` · 技术文档阅读器 · V0.8

- **优先级**：高（用户主动提需求 — 学技术文档时点词查 + 沉淀回顾）
- **状态**：✅ Spec + Plan 完成 + PR #45 待 review → ⬜ 待启动 PR1 实施
- **目标**：新增 `/library` 模块。用户粘 URL（任意网页，trafilatura 提正文）或粘 Markdown 正文导入英文技术文档 → 阅读时点词秒出 IPA / 选区一键翻译解读 → 所有解读自动入生词本（`source_type='library'`）→ 文章详情页右侧「本文沉淀」侧栏原地复习。与 BBC `/articles`（跟读训练）并行存在，不冲突。
- **MVP 不做**：高亮选区 / 评论 / 阅读进度 / 文章标签 — 留下一版补
- **后端**：trafilatura + 新表 `library_articles` + 新 router `/library/*` + 复用 `explain_service` / `vocab_service`
- **前端**：marked + DOMPurify + 新 view `Library.vue` + `LibraryArticle.vue` + 共享组件 `ExplanationCard`（BBC `/vocabulary` 页后续也会复用）
- **端优先级**：PC 优先（跟 `/translate` 一致），手机能用即可
- **锚点**：
  - Issue: [#46](https://github.com/bob798/speakeasy/issues/46)
  - Spec PR: [#45](https://github.com/bob798/speakeasy/pull/45)（`feat/library-spec` 分支）
  - Spec 文档：`docs/superpowers/specs/2026-05-19-library-tech-doc-reader-design.md`
  - Plan 文档：`docs/superpowers/plans/2026-05-19-library-tech-doc-reader.md`（16 Task / 3191 行）
  - 决策内存：`memory/project_v08_library.md`
- **PR 拆分**（4 PR，每个 ship 后页面可用、无半成品入口）：
  - [ ] **PR 1 · 后端基础（plan Task 1–4）**：trafilatura 依赖 + `LibraryArticle` ORM + `library_service`（import/list/get/delete/refetch）+ `/library/*` CRUD 路由 5 端点。ship 后后端可独立联调 import/list/detail。
  - [ ] **PR 2 · 后端 explain + 自动入库（plan Task 5–8）**：扩 `vocab.VALID_SOURCE_TYPES` 加 `library` + `_auto_save_library_vocab` 工具 + 三个 explain 端点（同步 / IPA / NDJSON 流式）+ 路由入口占位 + 完成回填 `update_explanation`。ship 后后端 explain 闭环可用。
  - [ ] **PR 3 · 前端阅读闭环（plan Task 9–13）**：marked + DOMPurify 依赖 + `useLibraryApi` composable + `Library.vue` 列表 + `AddArticleModal` + `LibraryArticle.vue` 阅读页 + `MarkdownReader` / `WordPopover` / `SelectionMenu` / `ExplanationCard` / `VocabSidebar`。ship 后 PC 端完整可用。
  - [ ] **PR 4 · 移动端 + 文档 + QA（plan Task 14–16）**：移动端降级（侧栏 → sheet + touchend 点词）+ CLAUDE.md / README / 架构图同步 + 全量回归 + 手动 E2E 验收。ship 后 V0.8 文章库 close issue #46。
- **关键约束**（启动前确认仍成立）：
  - 数据表叫 `library_articles`，**不叫 `articles`**（避开 BBC issue #42 计划的 `article_episodes` 通用命名）
  - `vocabulary` 表**无 schema 改动**，仅扩 `source_type='library'` 枚举值；`source_ref = str(article_id)`
  - `vocab_service.update_explanation` 已存在（见 `app/services/vocab_service.py:116`），直接复用
  - 任何入库 / 回填异常仅 `logger.warning` 吞，**不可影响解读返回**
  - 代码块 `<pre><code>` 内**不响应点词 / 选区**（明确划界）
  - Markdown 渲染必须经 `DOMPurify.sanitize`（XSS 防御）
  - 文章软删 → vocabulary 条目**不级联**（已沉淀的语言点跟文章生命周期解耦）
  - URL 抓取超时 8s；正文 >100k 截断 + meta.truncated=true
  - 同用户同 URL 唯一索引天然去重（命中已存返 200 + existing:true，不重抓）
- **预估工期**：5–7 天，4 PR 串行
- **启动指令**（回到本 TODO 时直接说一句即可）：
  > "启动 TODO-003 PR1"
  >
  > 我会：(1) 确认 spec PR #45 状态（merge 或继续）；(2) 从最新 main 拉 `feat/library-step-1`；(3) 按 plan Task 1–4 顺序 TDD 实现（先写失败测试 → 实现 → 跑通 → 单独 commit）；(4) 一并打成 PR1 `[V0.8 library / PR1] 后端基础 (Task 1–4)`，body `Refs #46`，并把 issue #46 对应 4 个 checkbox 在 merge 后勾掉

---

## V0.8 候选（已迁移到 GitHub Issues）

> 详细方案与讨论以 GitHub Issue 为准，本文件仅留索引。

- [#6](https://github.com/bob798/speakeasy/issues/6) — 连读解释通俗化 + 模式知识库
- [#7](https://github.com/bob798/speakeasy/issues/7) — 追问入口下沉到解读弹窗底部
- [#8](https://github.com/bob798/speakeasy/issues/8) — 历史缓存解读的刷新机制

---

### TODO 杂项（未排期）

1. 导出聊天内容，比如导出我的测试内容，让 ai 修正
2. 定义聊天标题

*TODO.md — 最后更新 2026-04-26*
