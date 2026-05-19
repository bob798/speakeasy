# 文章学习 · 生词本自动入库 · 标签化

> Date: 2026-05-19
> Owner: Claude Code (实现) · Human (验收)
> 范围: 后端路由重命名 + 解读自动入库 + 生词本前端独立页与标签化
> 关联 issue: [#42](https://github.com/bob798/speakeasy/issues/42)（后端 `source_type` 枚举与 `bbc_eaw_episodes` 表名重构 → 独立跟踪）
> 关联前序 spec: `2026-05-12-practice-mobile-redesign.md`

## 目标

**主目标**：用户在 `/articles`（原 `/practice`）做篇章学习时，**所有点过解读的词、短语、句子，自动落入"生词本"**，不需要任何手动收藏动作；事后用户可以在独立的 `/vocabulary` 页面按来源标签（BBC / 翻译收藏 / 未来 VOA 等）回看完整解读。

**核心心智**：生词本 = 学习过程中**碰过的语言点的沉淀池**，标签反映来源/主题。它服务于地铁场景下的"先点起来、回头慢慢看"的异步学习节奏。

**次目标（模块定位）**：把 `/practice` 从"发音练习"重命名为"文章学习"（`/articles`），为未来接入 VOA 等同类文章系列预留语义空间；本轮仅改路由与文案，不动后端 `source_type` 枚举。

## 现状问题

1. 用户在 `/practice` 点击 BBC 文章中的词/句触发解读后，**解读结果只在弹窗里看一眼即丢失**，没有沉淀路径
2. 现有 `vocabulary` 表的字段（`source_type='bbc_eaw'` / `source_ref` / `explanation_json` / `item_type`）已经为这件事预留好了，但没人写入
3. 用户大量在地铁等弱网/碎片场景使用，**解读慢 + 异步查看**是常态——前端弹窗生命周期不可依赖
4. `/practice` 模块名只反映"发音练习"这一种交互，但实际承载的是 BBC 篇章学习；未来加 VOA 等系列将语义错位

## 设计

### 整体范围

| 这一轮做 | 这一轮不做（独立 issue） |
|---|---|
| `/practice` → `/articles` 路由 + 前端文案 | `source_type` 枚举重构 (`bbc_eaw` → `article`) |
| `/practice/*` 临时 alias，1–2 个版本后移除 | `bbc_eaw_episodes` 表重命名为 `article_episodes` |
| 后端 `articles/explain*` 入口处自动写入 `vocabulary` | `vocabulary` 表 schema（已经够用） |
| 解读完成 / 缓存命中后回填 `explanation_json` | ExplanationCache 机制 |
| 生词本前端独立页 `/vocabulary` + 来源标签筛选 | Ask 抽象 (`/ask/threads`) |
| 生词本卡片原地展开 / pending 状态点开重新拉解读 | 用户自定义标签（本轮标签全由系统派生） |

### 1. 路由与模块重命名

| 项 | 旧 | 新 |
|---|---|---|
| 路由前缀 | `/practice` | `/articles` |
| 路由文件 | `app/routers/practice.py` | `app/routers/articles.py` |
| 前端页面 | `views/Practice.vue` | `views/Articles.vue` |
| Vue Router 路径 | `/practice` | `/articles` |
| 页面标题 | 发音练习 | 文章学习 |
| 导航文案 | 发音练习 | 文章学习 |
| 副标题 | （无） | BBC English at Work（系列标识，未来可切换） |

**保留**：
- 后端 `source_type='bbc_eaw'` 枚举（独立 issue 重构）
- `bbc_eaw_episodes` 表名
- `/practice/*` 临时 alias 路由（与新路由共用同一 handler，按 1–2 个版本节奏移除）
- `Practice.vue` 内部组件（发音对比、字幕跟读、FSRS 复习闭环）逻辑全部不动，仅文件改名

### 2. 自动入库时序

```
用户在 /articles 文章页点击词/句
        │
        ▼
ExplanationModal 打开，触发以下三种之一：
  · POST /articles/explain          （整体一次性解读）
  · POST /articles/explain/phonetic （单词 IPA 秒出）
  · POST /articles/explain/stream   （流式解读 NDJSON）
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│ 路由入口（同步、立即执行，先于任何 LLM/缓存查询）       │
│  vocab_service.save_item(                               │
│     user_id, source_text=text, direction='en2zh',       │
│     item_type=kind, source_type='bbc_eaw',              │
│     source_ref=slug, context=context,                   │
│     explanation_json=None  ← 先占位                     │
│  )                                                      │
│  · 唯一键 (user_id, source_text, source_ref) 命中 →     │
│    复活/保持现状，不重复入库                            │
│  · 写入异常仅 logger.warning，不影响后续解读返回        │
└─────────────────────────────────────────────────────────┘
        │
        ▼
原有 explain_service 流程
  · 命中 ExplanationCache → 秒出
  · 未命中 → 流式 LLM 生成 → 写 ExplanationCache
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│ 流式完成时 / 缓存命中时（同步路径中）                   │
│  vocab_service.update_explanation(                      │
│     user_id, source_text, source_ref,                   │
│     explanation_json=full_json                          │
│  )                                                      │
│  · 找不到记录 → logger.warning + skip                   │
│  · 软删状态也写入（不丢历史）                           │
└─────────────────────────────────────────────────────────┘
        │
        ▼
前端继续接收流；入库与前端生命周期解耦
```

#### 关键设计点

| 点 | 决策 | 理由 |
|---|---|---|
| 入库时机 | 路由入口处 | 地铁切走/断网照样有记录 |
| 入库依赖 | 不依赖前端 keep-alive | "解读慢 + 异步查看"场景必需 |
| 复活语义 | 沿用 `vocab_service` 现有 `(user_id, source_text, source_ref)` 复活逻辑 | 已存在的成熟行为，不引入新分支 |
| 回填语义 | 同样的复合键 `UPDATE explanation_json` | 软删条目也回填，保留历史 |
| 写入失败 | `logger.warning` + 吞异常 | 解读永不能因入库失败而 fail |
| 三个端点统一 | `/articles/explain`、`/articles/explain/phonetic`、`/articles/explain/stream` 都触发入库 | 用户场景下，只点 IPA 也是"我对这词感兴趣"的信号 |
| ExplanationCache | 不动；命中缓存也照常入库 | 缓存命中不意味着对当前用户来说"已经学过"，仍需要个人化记录 |
| 并发同一请求 | 唯一键挡住，第二次 `ON CONFLICT DO NOTHING` | save_item 现有行为 |

### 3. 标签机制

**所有标签由系统派生，不引入新表**：

| `vocabulary.source_type` | 派生标签 |
|---|---|
| `translate` | 翻译收藏 |
| `bbc_eaw` | BBC |
| `practice` / `chat` 等其它历史值 | 按需在前端 mapping 表里加 |
| （未来）VOA 接入后追加的新枚举 | VOA |

前端通过 `GET /vocab?source_type=<value>` 过滤，缺省返全部。tag chip 顺序：「全部 / BBC / 翻译收藏」（按当前数据量与重要度排序）。

### 4. 生词本独立页 `/vocabulary`

#### 4.1 入口调整

- **新增**：导航菜单"生词本"项 → `/vocabulary`
- **移除**：`/translate` 页面内嵌的 vocabulary 折叠面板（功能整体迁移到 `/vocabulary`）

#### 4.2 列表布局

```
┌──────────────────────────────────────────────────────────┐
│  我的生词本                                              │
├──────────────────────────────────────────────────────────┤
│  [ 全部 ] [ BBC ] [ 翻译收藏 ]      共 N 条              │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  💬 office banter                                BBC ▸   │
│  办公室闲聊                                              │
│  ⏱ 5 分钟前  ·  Episode 12 — Small Talk                  │
│  ─────────────────────────────────────────────────────  │
│                                                          │
│  💬 it's not rocket science                      BBC ▸   │
│  这又不是什么难事                                        │
│  ⏱ 1 小时前  ·  Episode 09 — Project Status              │
│  ⚠ 解读生成中                                            │
│  ─────────────────────────────────────────────────────  │
│                                                          │
│  💬 reschedule                                  翻译 ▸    │
│  改期 / 重新安排                                         │
│  ⏱ 3 天前                                                │
│  ─────────────────────────────────────────────────────  │
└──────────────────────────────────────────────────────────┘
```

- 顶部 chip 横排：「全部 / BBC / 翻译收藏」（点击切换 `source_type` query）
- 卡片元素：`source_text`（句子级 80 字截断） · `translated_text` · 相对时间 · 来源 tag · episode/系列副标题（仅 BBC 类有）
- pending 状态条目展示 `⚠ 解读生成中`
- 默认排序：`created_at DESC`
- 分页：与现有 `/vocab` 接口对齐（每页 20）

#### 4.3 条目交互

- **点条目 → 原地展开卡片**（不跳新页、不弹弹窗）
- 展开内容：完整 `explanation_json` 渲染（meaning / grammar / phrases / liaison / IPA / 朗读按钮 等）；与 `ExplanationModal` 共用渲染组件
- pending 条目点开：
  1. 自动调 `POST /articles/explain` 拉一份（非流式，一次返完整 JSON）
  2. 成功 → 回填生词本对应记录的 `explanation_json` + 原地渲染
  3. 失败（仍无网等）→ 展开区显示「生成中，请稍后重试」按钮
- 软删按钮：每条右上角，软删后从列表移除（实际是 `status='deleted'`）

#### 4.4 状态机

```
                  ┌──────────┐
   用户点解读     │ pending  │ ◀── 入库瞬间 explanation_json=null
       │         └─────┬────┘
       ▼               │
   流式解读完成        │
       │               │
       ▼               ▼
   ┌────────────────────────┐
   │ ready                  │ ◀── explanation_json 已回填
   └────────────┬───────────┘
                │
                │ 用户软删
                ▼
   ┌────────────────────────┐
   │ deleted                │ ◀── 软删；下次同源同词命中即复活
   └────────────────────────┘
```

> 注：状态字段已存在于 `vocabulary.status`，本轮无需新增字段。pending 的判定 = `status='active' AND explanation_json IS NULL`。

### 5. 错误处理与一致性

| 场景 | 行为 | 理由 |
|---|---|---|
| 入库 DB 异常 | `logger.warning` + 吞异常 | 解读永不能 fail |
| 回填记录不存在 | `logger.warning` + skip | 用户可能在解读完成前删除 |
| 回填遇到 deleted 记录 | 仍然写入 | 软删不丢历史 |
| 并发同请求 | 唯一键挡住 | save_item 已支持 |
| 解读流式中断 | pending 条目留存 | 异步回看场景的核心承载 |
| 用户点开 pending → 拉新解读再次失败 | UI 显示"生成中，请稍后重试"按钮 | 与 ExplanationModal 错误处理对齐 |

**结构化日志锚点**：

- `vocab_auto_save_attempt`：路由入口处发起入库
- `vocab_auto_save_skipped`：唯一键命中已存在记录
- `vocab_explanation_backfill`：解读完成回填
- `vocab_explanation_backfill_miss`：回填时找不到对应记录
- `vocab_pending_fetch`：前端从生词本拉新解读

### 6. 改动清单

#### 后端

| 文件 | 改动 |
|---|---|
| `app/routers/practice.py` → `app/routers/articles.py` | 路由前缀 `/practice` → `/articles`；逻辑不动；三个 explain 端点头部加 `vocab_service.save_item()` 占位写入 |
| `app/main.py` | router include 改 `articles_router`；额外注册 `/practice/*` alias 指向同一 handler |
| `app/services/vocab_service.py` | 新增 `update_explanation(user_id, source_text, source_ref, explanation_json)`；`save_item` 现有签名已支持 `explanation_json=None`，无需改 |
| `app/services/explain_service.py` | 流式生成完成 / 缓存命中处，回调 `vocab_service.update_explanation`（依赖注入 callback 或路由层在 await 完成后调用） |
| `app/routers/vocab.py` | `GET /vocab` 增加可选 query `source_type` |

#### 前端

| 文件 | 改动 |
|---|---|
| `frontend/src/router/index.ts` | `/practice` → `/articles` 主路由；`/practice` redirect 到 `/articles`；新增 `/vocabulary` 路由 |
| `frontend/src/views/Practice.vue` → `Articles.vue` | 标题"发音练习" → "文章学习"，加副标题"BBC English at Work"；其它不动 |
| 导航菜单组件 | 文案"发音练习" → "文章学习"；新增"生词本"入口 |
| `frontend/src/views/Vocabulary.vue` | 新建：tag chip 横排 + 列表 + 卡片原地展开 + pending 重拉逻辑 |
| `frontend/src/views/Translate.vue` | 移除原 vocabulary 折叠面板 |
| `frontend/src/api/vocab.ts` | `listVocab()` 增加 `sourceType?: string` 参数 |
| `ExplanationModal.vue` | **不改**（入库下沉到后端，弹窗对此无感） |
| 生词本卡片展开渲染组件 | 优先复用 `ExplanationModal` 内部的 explanation 渲染部分；如难拆，新建共享子组件 |

#### 文档

| 文件 | 同步更新 |
|---|---|
| `CLAUDE.md` | API 清单 `/practice/*` → `/articles/*`；数据表 vocabulary 说明补充（自动入库语义）；版本状态新增 V0.8 |
| `README.md` | 部署/路由说明；模块介绍 |
| `docs/architecture/c4-container.md` | 模块图重命名 + 自动入库流向 |
| `docs/architecture/flows/`（如有） | 新增 `article-explain-vocab-flow.md` 描述数据流 |

#### 这一轮不动

- `vocabulary` 表 schema
- `bbc_eaw_episodes` 表 / 路由 `/bbc-eaw/*`
- `source_type` 枚举值（仍是 `bbc_eaw`）
- ExplanationCache 机制
- Ask 抽象 (`/ask/threads`)
- ROADMAP.md（由 Human 验收后移入"已发布"）

### 7. 测试策略

| 层级 | 用例 |
|---|---|
| **vocab_service 单元测试** | `save_item(explanation_json=None)` 占位写入；`update_explanation()` 回填；唯一键复活；不存在时静默 skip；软删条目回填仍写入 |
| **explain_service 集成测试** | 流式解读完成 → `update_explanation` 被调；缓存命中也触发 update；写入失败时解读仍正常返回 |
| **articles router 路由测试** | `/articles/explain`、`/articles/explain/phonetic`、`/articles/explain/stream` 三个入口都调 `save_item`；写入 `source_type='bbc_eaw'`、`source_ref=slug`、`item_type` 与 kind 一致 |
| **alias 兼容测试** | `/practice/explain` 走同一 handler，vocabulary 入库一致 |
| **vocab list API 测试** | `GET /vocab?source_type=bbc_eaw` 仅返 BBC；`GET /vocab` 返全部；分页正确 |
| **失败容错测试** | mock `vocab_service.save_item` raise → explain 流式仍正常返回 |
| **前端 E2E（手测 + 截图）** | 文章页点词 → 弹窗解读 → 切到 `/vocabulary` → 看到刚才点的词；pending 条目点开能拉新解读；tag chip 切换过滤生效 |

**测试规范**：

- 测试 user_id 命名：`test_user_v08_articles_<step>`
- 每个测试 `autouse fixture` 保证前后清理
- 断言用具体值（如 `assert item.source_type == 'bbc_eaw'`），不用 `assert is not None`
- Mock 仅作用于 LLM API，不 Mock 内部服务

### 8. 关联 issue（独立跟踪，不阻塞本轮）

GitHub Issue：[#42 chore(vocab): source_type 与表名重构为 article-* 通用语义](https://github.com/bob798/speakeasy/issues/42)

**背景**：本轮 `/practice` → `/articles` 仅文案层完成，后端 `source_type='bbc_eaw'`、`bbc_eaw_episodes` 表名仍是 BBC 专属命名。未来加 VOA 等系列后会需要更通用的 `article-*` 语义。

**预期工作**（详见 issue #42）：
- 数据迁移：`vocabulary.source_type` `bbc_eaw` → `article` + `series='bbc_eaw'` 的拆分（或类似方案）
- 表名 `bbc_eaw_episodes` → `article_episodes`，新增 `series` 字段
- 旧 alias `/practice/*` 一并移除
- 标签 chip 由 `series` 字段派生

## 验收标准

1. 在 `/articles` 页面点击 BBC 文章中的任意词、短语、句子（包括只点 IPA），切到 `/vocabulary` 都能看到对应条目
2. 网络中断 / 关闭弹窗 / 切走页面，条目仍存在；`explanation_json` 状态正确（pending 或 ready）
3. `/vocabulary` 标签切换正确过滤 BBC / 翻译收藏 / 全部
4. pending 条目点开能自动拉新解读并回填
5. 旧路由 `/practice/*` 在过渡期仍可访问，行为与 `/articles/*` 一致
6. `pytest tests/ -v` 全绿
7. CLAUDE.md / README.md / 架构图同步更新
