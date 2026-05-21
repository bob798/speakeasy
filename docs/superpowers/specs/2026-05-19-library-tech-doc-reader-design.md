# 文章库 · 技术文档阅读器 `/library`

> Date: 2026-05-19
> Owner: Claude Code (实现) · Human (验收)
> 范围: 新增 `/library` 模块 — 用户自带英文技术文档的精读 + 翻译沉淀闭环
> 关联前序 spec: `2026-05-19-articles-vocab-tag-design.md`（BBC `/articles` 改名 + 独立 `/vocabulary`，与本 spec 在 V0.8 并行 ship）
> 版本归属: V0.8

## 目标

**一句话**：`/library` = 我自己粘进来的英文技术文档库；进文章 → 点词 / 选区直翻 → 翻译自动入生词本 → 后续在生词本回看。

**与现有 BBC 路径的边界**：
- BBC English at Work（`/articles`，由 `2026-05-19-articles-vocab-tag-design.md` 主理）= **跟读 + 发音 + FSRS**，强训练路径
- `/library`（本 spec）= **精读 + 翻译沉淀**，纯阅读路径，没有发音卡，没有 FSRS
- 两条路径并行存在，共用 `vocabulary` 表与 `explain_service`

**心智**：用户在地铁 / 工位读 GitHub README、技术博客、Anthropic docs 时，**碰过的语言点的沉淀池**——查过的不丢，回头慢慢看。

## 现状问题

1. Speakeasy 现有的"读 + 查"能力只服务 BBC 67 集预制语料，用户带来的任意英文技术文档没有入口
2. `/translate` 适合"独立查个词 / 句"，但**没有"我正在读这篇文章"的上下文承载**——查过的词跟"我读到哪了"完全脱节
3. 技术文档场景下，用户希望"点词秒查 + 不打断阅读流 + 查过的回头能看见"，这是 `/translate` 双栏布局无法提供的

## 设计

### 1. 范围卡（MVP vs 下一版）

| MVP 这一轮做 | 留给下一版 |
|---|---|
| 导入：任意 URL（trafilatura）+ 粘贴 Markdown 双入口 | 标注重点（高亮选区） |
| `/library` 列表页（PC 优先） | 高亮叠加评论 |
| `/library/:id` 阅读详情页：Markdown 渲染 + 点词 / 选区翻译 | 阅读进度与续读 |
| 翻译自动入 `vocabulary`（`source_type='library'`） | 文章 tag / 标签筛选 |
| 文章软删 / URL 去重 / 抓取失败兜底 | 浏览器扩展、批量导入 |
| 生词本入口：文章详情页底部「本文沉淀」侧栏 | 独立 `/vocabulary` 全局页（BBC spec 已规划，本 spec 不重复实现） |

### 2. 选型与依赖

| 模块 | 选型 | 理由 |
|---|---|---|
| 后端正文提取 | `trafilatura` (Python) | 直接输出 Markdown（保留标题 / 列表），内部已含 readability-lxml + jusText 三层 fallback，技术文档场景平均得分 0.883 |
| Markdown 渲染 | `marked` + `DOMPurify`（前端） | 轻量、安全 sanitize；与现有 Vue 栈兼容 |
| 高亮渲染（下一版） | `mark.js` | 不在 MVP 范围；本 spec 预留 slot |
| 解读服务 | 复用 `app/services/explain_service.py` | 已验证通用（不绑 BBC），无需改造 |
| 生词本服务 | 复用 `app/services/vocab_service.py` + BBC spec 计划新增的 `update_explanation` | 与 BBC spec **共同依赖**，两边一起 ship |
| 解读 prompt / cache | 复用 `EXPLAIN_SENTENCE_PROMPT` / `EXPLAIN_WORD_PROMPT` / `ExplanationCache` | 不动 |

**评估过但不采用**：
- Omnivore — 2024-11 服务关停，社区 fork 在 `omnivore.work`；栈是 Node + TS + Postgres + Redis + 浏览器扩展 + 移动 App，与 Speakeasy FastAPI+Vue 栈完全不匹配，移植成本 ≥ 重写
- Wallabag — PHP/Symfony 栈，同上不匹配
- Read Frog（开源沉浸式翻译扩展）— 是浏览器扩展形态，沉淀在它自己侧，无法接入 Speakeasy 既有生词本 / FSRS / Ask 闭环
- 浏览器扩展路线 — 工作量是 web 路线的 2–3 倍（Chrome ext 维护 / 跨域身份 / 商店上架）

### 3. 数据模型

#### 3.1 新表 `library_articles`

```sql
CREATE TABLE library_articles (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id      TEXT NOT NULL,
  source_url   TEXT,                                  -- 粘贴正文模式为 NULL
  title        TEXT NOT NULL,
  markdown     TEXT NOT NULL,                          -- trafilatura / 粘贴的正文 markdown 快照
  word_count   INTEGER NOT NULL DEFAULT 0,             -- 估算阅读时长用
  source_meta  TEXT,                                   -- JSON: author / site_name / published_at / extracted_at
  status       TEXT NOT NULL DEFAULT 'active',         -- active / deleted
  created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX ux_library_articles_user_url
  ON library_articles(user_id, source_url)
  WHERE source_url IS NOT NULL;

CREATE INDEX ix_library_articles_user_status
  ON library_articles(user_id, status, created_at DESC);
```

**表名为何叫 `library_articles` 而非 `articles`**：避开 BBC spec issue #42 计划的 `article_episodes` / 通用 `articles` 命名空间冲突。`library_` 前缀清晰表明"用户文章库"语义。

#### 3.2 `vocabulary` 表无 schema 改动

仅启用新枚举值：
- `vocabulary.source_type` 取值集合扩展为 `{translate, bbc_eaw, library}`
- `vocabulary.source_ref` 当 `source_type='library'` 时存 `library_articles.id` 的字符串化形式
- `vocabulary.item_type`、`explanation_json`、`status` 等字段语义与 BBC 一致

### 4. 后端接口

| 接口 | 方法 | 说明 |
|---|---|---|
| `/library/articles` | POST | 导入文章：body `{url?, markdown?, title?}`，二选一；URL 命中已存条目 → 200 + `{existing: true, id, ...}`；新条目 → 201 + 完整记录 |
| `/library/articles` | GET | 文章列表，分页（`page`/`page_size`，默认 20，`created_at DESC`），仅 `status='active'` |
| `/library/articles/{id}` | GET | 文章详情，返 markdown 全文 + meta + 本文沉淀 vocab 数量 |
| `/library/articles/{id}` | DELETE | 软删（`status='deleted'`），vocabulary 条目不级联 |
| `/library/articles/{id}/refetch` | POST | 强制重抓（仅 URL 类，粘贴正文返 400） |
| `/library/articles/{id}/explain` | POST | 单词 / 句子整解读，body `{text, kind, context?}`；路由入口写 vocabulary 占位 → 调 `explain_service.explain_text` → 完成回填 |
| `/library/articles/{id}/explain/phonetic` | POST | IPA 秒出（`item_type=word`），同步写 vocabulary |
| `/library/articles/{id}/explain/stream` | POST | NDJSON 流式句解读，入口写占位 → 流完成回调回填 |

#### 4.1 抓取行为

- trafilatura 配置：`extract(url, output_format='markdown', include_links=True, include_tables=True, with_metadata=True)`
- 超时：HTTP fetch 8s（trafilatura 内部走 `requests`，自定义 timeout）
- 失败返：`400 {"error": "fetch_failed", "hint": "抓取失败，请改用粘贴正文模式"}`，前端识别此 error 切到粘贴 tab
- 超长保护：`len(markdown) > 100_000` 截断到 100k + `source_meta.truncated=true`，warning 日志
- 标题来源优先级：trafilatura meta.title > body 第一个 `# ` 标题 > `Untitled`
- 同 `(user_id, source_url)` 唯一索引天然去重

#### 4.2 入库行为（沿用 BBC spec 已确认的模式）

三个 explain 端点的路由入口处：

```python
# 路由入口（同步、立即执行，先于任何 LLM/缓存查询）
try:
    vocab_service.save_item(
        user_id=user_id,
        source_text=text,
        translated_text="",                       # 解读类不直接走 translate
        direction="en2zh",
        item_type=kind,                            # word / sentence
        source_type="library",
        source_ref=str(article_id),
        context=context,
        explanation_json=None,                     # 先占位
    )
except Exception as e:
    logger.warning("vocab_auto_save_failed", extra={"err": str(e)})
```

LLM 完成 / 缓存命中后：

```python
try:
    vocab_service.update_explanation(
        user_id=user_id,
        source_text=text,
        source_ref=str(article_id),
        explanation_json=full_json,
    )
except Exception as e:
    logger.warning("vocab_backfill_failed", extra={"err": str(e)})
```

**入库的关键约束**：
- 任何入库异常仅 `logger.warning` + 吞，**不能影响解读返回**
- 唯一键 `(user_id, source_text, source_ref)` 复活语义沿用 `save_item` 现有行为
- 软删条目也回填（不丢历史），与 BBC spec 一致

#### 4.3 路由文件

新增 `app/routers/library.py`，注册到 `app/main.py`。不复用 `practice.py`（语义、内容源、生命周期都不同）。

### 5. 前端页面

#### 5.1 路由

```
/library              → Library.vue        我的文章库列表
/library/:id          → LibraryArticle.vue 阅读详情
```

PC 优先（与 `/translate` 一致）；手机能用即可，不做独立设计。

#### 5.2 列表页 `Library.vue`

```
┌──────────────────────────────────────────────────────────────┐
│  我的文章库                                  [+ 添加文章]    │
├──────────────────────────────────────────────────────────────┤
│  Spec-Driven Development with Spec Kit                       │
│  github.com/github/spec-kit · 3,200 词 · ~13 分钟读           │
│  ⏱ 1 小时前  ·  💬 已沉淀 7 个词                              │
│  ──────────────────────────────────────────────────────────  │
│  Anthropic Cookbook — Claude API Memory                      │
│  anthropic.com/docs · 1,800 词 · ~7 分钟读                    │
│  ⏱ 昨天  ·  💬 已沉淀 3 个词                                  │
└──────────────────────────────────────────────────────────────┘
```

- 卡片元素：标题 · 来源 host · 词数 · 估算阅读时长（200 wpm）· 相对时间 · 已沉淀词数（由 `GET /library/articles` 列表响应每条记录直接附带 `vocab_count` 字段返回，避免 N+1 查询）
- 点卡片进入详情页
- 右上角 `+ 添加文章` 弹模态框

#### 5.3 添加文章模态框

```
┌── 添加文章 ──────────────────────────────────────┐
│  ( ◉ 粘贴 URL )  ( ○ 粘贴正文 )                  │
│                                                  │
│  URL: https://...                                │
│                                                  │
│  [ 抓取 ]                                        │
└──────────────────────────────────────────────────┘
```

- Tab 切换：`粘贴 URL` / `粘贴正文`
- URL 模式：title 自动从 trafilatura meta 拉，可编辑（无 meta 时 fallback 到 body 第一个 `# ` 标题或 `Untitled`）
- 粘贴正文模式：textarea + **title 输入框（必填，前端表单校验）**
- 抓取失败时，自动建议切到粘贴正文 tab

#### 5.4 阅读详情页 `LibraryArticle.vue`

```
┌─────────────────────────────────────────────────────────────────────┐
│  ← 返回                                                  [⋯ 删除]   │
├─────────────────────────────┬───────────────────────────────────────┤
│                             │  本文沉淀 (7)                          │
│   Article Title             │  ─────────────────────────────────    │
│   ────────────              │  💬 spec-driven                       │
│                             │     规约驱动                          │
│   Markdown body...          │  ─────────────────────────────────    │
│   选词 → 浮气泡             │  💬 it's not rocket science           │
│   点词 → IPA 秒出           │     这又不是什么难事                  │
│                             │  ─────────────────────────────────    │
│   ```code blocks            │  💬 ...                               │
│   不响应点词 / 选区```      │                                       │
│                             │                                       │
└─────────────────────────────┴───────────────────────────────────────┘
```

**布局**：
- PC：主区最大宽 720px 居中（阅读舒适）；右侧固定侧栏「本文沉淀」（≥1280px 默认展开，<1280px 折叠为抽屉图标）
- 手机：右侧侧栏变底部 sheet（点底部按钮"本文沉淀 (7)"展开）

**点词 / 选区交互**：

| 触发 | 行为 |
|---|---|
| 单击单词（`mouseup` + `caretRangeFromPoint`） | 浮气泡显示 IPA 秒出（`/library/articles/{id}/explain/phonetic`）+ 「展开解读」按钮 |
| 选中 ≥2 个词 | 浮气泡菜单，MVP 只有「翻译」按钮，点击触发 `/library/articles/{id}/explain/stream`（句）或 `/explain`（短语） |
| 「展开解读」 | 浮层卡片（与 `ExplanationModal` 共享渲染组件）流式渲染 explanation_json 字段 |
| 代码块 `<pre><code>` 内 | **不响应点词 / 选区**；CSS `user-select: text` 但不触发 listener |

**「本文沉淀」侧栏**：
- 列表项：`source_text` 截断 + 译文 / 解读 meaning 第一行 + 状态徽章（pending / ready）
- 点列表项 → 原地展开 explanation_json 全量渲染
- pending 条目点开：自动调 `/library/articles/{id}/explain` 拉新解读 → 成功回填 → 失败显示「生成中，请稍后重试」按钮
- 数据源：`GET /vocab?source_type=library&source_ref=<article_id>`

#### 5.5 导航入口

- 主导航菜单新增「文章库」项 → `/library`
- 现有 `/translate` 内的 vocabulary 折叠面板（如有）不动；独立 `/vocabulary` 页由 BBC spec 实现

### 6. 与 BBC spec 的共依赖

| 共依赖项 | 由谁先做 | 备注 |
|---|---|---|
| `vocab_service.update_explanation(user_id, source_text, source_ref, explanation_json)` | 谁先到谁实现，另一方复用 | 函数签名两份 spec 一致 |
| `vocabulary.source_type` 枚举扩展 | 两份 spec 同时启用各自值 | 不需要 schema 改动，运行时校验放宽 |
| `ExplanationModal` 内 explanation 渲染部分组件化 | 谁先到谁做 | 两份 spec 都需要"原地展开 explanation" |
| 独立 `/vocabulary` 全局页 | **BBC spec 主理**，本 spec MVP 不依赖 | 本 spec 用文章详情页「本文沉淀」侧栏兜底 |

**Ship 顺序建议**：本 spec 与 BBC spec 在 V0.8 内并行，每个 Step 各自 PR；先合并的负责实现共依赖项，后合并的复用。

### 7. 错误处理与一致性

| 场景 | 行为 | 理由 |
|---|---|---|
| URL 抓取失败（超时 / 403 / 解析空） | 返 400 `fetch_failed` + hint，前端切到粘贴正文 | 技术文档站 anti-bot 常态 |
| URL 命中已存条目 | 200 + `existing: true`，前端提示「文章已在文章库」并直接跳入详情 | 避免重复抓取浪费 |
| 抓取后 markdown 过长 | 截断到 100k + `source_meta.truncated=true`，UI 顶部条提示 | 保护数据库与渲染 |
| Markdown 含可执行 HTML | DOMPurify 强制 sanitize | XSS 防御 |
| vocab 入库 DB 异常 | `logger.warning` + 吞 | 解读永不能 fail |
| 回填记录不存在 | `logger.warning` + skip | 用户可能在解读完成前删除 |
| 回填遇到 deleted 记录 | 仍然写入 | 软删不丢历史 |
| 解读流式中断 | pending 条目留存 | 异步回看场景核心 |
| 软删文章 | vocabulary 条目**不级联**，保留 | 已沉淀的语言点跟文章生命周期解耦 |

**结构化日志锚点**：

- `library_article_imported`：导入成功（mode=url/markdown，char_count）
- `library_article_fetch_failed`：抓取失败（url, reason）
- `library_article_dedup_hit`：URL 命中已存
- `library_article_truncated`：超长截断
- `library_vocab_auto_save`：入口处占位写入
- `library_vocab_backfill`：完成回填
- `library_vocab_backfill_miss`：回填找不到记录

### 8. 改动清单

#### 后端

| 文件 | 改动 |
|---|---|
| `app/routers/library.py` | 新增；7 个端点 |
| `app/main.py` | 注册 `library_router` |
| `app/models/db.py` | 新增 `LibraryArticle` model + 唯一索引 |
| `app/services/library_service.py` | 新增；trafilatura 抓取 + 入库 + 列表 / 详情 / 软删 |
| `app/services/vocab_service.py` | 新增 `update_explanation()`（与 BBC spec 共依赖，谁先做谁实现） |
| `app/services/explain_service.py` | 不动（直接复用） |
| `requirements.txt` | 添加 `trafilatura>=2.0` |

#### 前端

| 文件 | 改动 |
|---|---|
| `frontend/src/router/index.ts` | 新增 `/library`、`/library/:id` 路由 |
| `frontend/src/views/Library.vue` | 新建：列表 + 添加文章模态框 |
| `frontend/src/views/LibraryArticle.vue` | 新建：阅读详情 + 选词 / 选区交互 + 本文沉淀侧栏 |
| `frontend/src/api/library.ts` | 新建：7 个端点的 client 封装 |
| `frontend/src/components/ExplanationCard.vue` | 抽取自 `ExplanationModal` 的渲染部分（共依赖，谁先做谁抽） |
| 导航菜单组件 | 加「文章库」入口 |
| `package.json` | 添加 `marked`、`dompurify`（前端依赖） |

#### 文档

| 文件 | 同步更新 |
|---|---|
| `.claude/CLAUDE.md` | API 清单新增 `/library/*`；数据表新增 `library_articles`；版本状态升 V0.8（与 BBC spec 并行） |
| `README.md` | 模块介绍 / 接口文档 |
| `docs/architecture/c4-container.md` | 加 `/library` 模块块与数据流 |
| `ROADMAP.md` | Human 维护，验收后移入"已发布" |

#### 这一轮不动

- BBC `/practice` 路由（由 BBC spec 改名 `/articles`）
- `vocabulary` 表 schema
- `ExplanationCache` 机制
- Ask 抽象（`/ask/threads`）
- 翻译页 DeepL 风重设计（独立 V0.11 spec）

### 9. 测试策略

| 层 | 用例 |
|---|---|
| `library_service` 单元 | URL 命中去重；粘贴 markdown 入库；软删；trafilatura mock 失败返 fetch_failed；超长截断 |
| `library` router 端点 | POST /library/articles 两种 mode；GET 列表分页；GET 详情含 vocab count；DELETE 软删 |
| `library` explain 端点 | 三个 explain 端点入口都触发 `save_item(source_type='library', source_ref=<id>)`；写入 item_type 与 kind 一致 |
| 失败容错 | mock `save_item` raise → explain 流式仍正常返；mock trafilatura raise → 400 fetch_failed |
| `vocab` 集成 | `GET /vocab?source_type=library&source_ref=<id>` 仅返本文沉淀；分页正确；deleted 文章的 vocab 仍可查 |
| 前端 E2E（手测 + 截图） | 粘 `https://github.com/github/spec-kit/blob/main/spec-driven.md` → 抓回正文 → 点词出气泡 → 选句出菜单 → 切到列表看到这篇 → 删除文章 / 已沉淀生词不丢 |

**测试规范**：

- 测试 user_id 命名：`test_user_v08_library_<step>`
- 每个测试 `autouse fixture` 保证前后清理 `library_articles` 与 `vocabulary`
- 断言用具体值（如 `assert article.source_type == 'library'`），不用 `assert is not None`
- Mock 仅作用于外部依赖（trafilatura / LLM API），不 Mock 内部 service

## 验收标准

1. 在 `/library` 粘贴 `https://github.com/github/spec-kit/blob/main/spec-driven.md` → 抓回正文 → 进文章可读
2. 点击文中任意词 → 浮气泡显示 IPA；点「展开解读」→ 流式渲染完整 explanation
3. 选中任意短语 / 句子 → 浮气泡菜单出现「翻译」→ 点击触发解读
4. 切到文章详情页右侧「本文沉淀」侧栏，能看到刚才点过的词 / 句条目
5. 关闭页面 / 切走 / 网络中断后，「本文沉淀」条目仍存在（状态 pending 或 ready 都计入）
6. 切回列表能看到这篇文章，软删后从列表消失，已沉淀生词不丢
7. 粘贴正文模式（不带 URL）流程同上
8. 抓取失败时 UI 自动建议切到粘贴正文模式
9. `pytest tests/ -v` 全绿
10. `.claude/CLAUDE.md` / `README.md` / 架构图 同步更新

## 版本归属

V0.8（与 `2026-05-19-articles-vocab-tag-design.md` 并行 ship）

| Spec | 内容 |
|---|---|
| 本 spec（`library-tech-doc-reader`） | 用户自带技术文档库 + 精读 + 翻译沉淀 |
| BBC spec（`articles-vocab-tag`） | `/practice` → `/articles` 改名 + BBC 自动入库 + 独立 `/vocabulary` |

两份 spec 共依赖 `vocab_service.update_explanation` 与 `ExplanationCard` 共享组件，谁先到谁实现。

## 关联 issue 与 PR

- spec 本身：单独 PR（doc-only）合入后，开 tracking issue「V0.8 文章库 · 技术文档阅读器」
- 实现：每个 Step 一个 PR，`Refs #<issue>`
- 实现计划详见同目录 `2026-05-19-library-tech-doc-reader-plan.md`
