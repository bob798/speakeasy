# BBC Learning English — English at Work（语料数据集）

> 状态：已抓取 + 已入库 · 2026-04-27 首次落地
> 数据：67 集 · 2,836 条对白 · 273 条核心 phrases
> 用途：V0.8 场景模式素材底座（职场场景对白 / 目标句型 / 听力小测）

---

## 1. 数据来源

- **官方主站**：`https://www.bbc.co.uk/learningenglish/english/features/english-at-work/<slug>`
- **覆盖范围**：1 集 intro + 66 集正篇（episode_id 160701 → 171004，对应 2016-07-01 至 2017-10-04 BBC 播出周期）
- **每集页面包含**：标题、片名、Episode ID、播出日期、主题（Language for X）、剧情简介、3–8 条核心 phrases、听力 Listening Challenge（Q + A）、完整角色对白
- **主线人物**：Anna（主角）/ Paul（老板）/ Denise / Tom / 偶尔 Mr Socrates、Mr Lime、Rachel、Narrator（旁白教学）

> 本数据集仅在本地存储与解析，用于 Speakeasy 学习功能。版权归 BBC 所有。

---

## 2. 文件落地

```
data/bbc_eaw/
├── raw/             29 MB · 67 个原始 HTML（全保留，作为后续扩展原料）
├── parsed/         576 KB · 67 个结构化 JSON
└── index.json       24 KB · 全集目录（slug / title / episode_id / topic / 统计）

scripts/
├── bbc_eaw_fetch.py · 抓取（curl + 0.6 s 限速 · idempotent · --force / --only 可选）
├── bbc_eaw_parse.py · HTML → JSON 解析
└── bbc_eaw_seed.py  · JSON → SQLite 入库（upsert by slug）
```

**Pipeline**

```
BBC web → curl (rate-limited)
       → data/bbc_eaw/raw/<slug>.html        ← 原始 HTML 永久保留
       → bbc_eaw_parse.py
       → data/bbc_eaw/parsed/<slug>.json     ← 结构化中间产物
       → bbc_eaw_seed.py
       → bbc_eaw_episodes 表                  ← 业务表（应用层使用）
```

3 段式可独立重跑，每段 idempotent。后续要扩字段（如 IPA、词频、相关 video pid），改 parser/seed 重跑即可，**不必再访问 BBC**。

---

## 3. JSON Schema（每集）

```json
{
  "slug": "01-the-interview",
  "url":  "https://www.bbc.co.uk/learningenglish/english/features/english-at-work/01-the-interview",
  "page_title": "BBC Learning English - English at Work / The Interview",
  "title": "The Interview",
  "episode_id": "160706",
  "air_date":  "06 Jul 2016",
  "topic":  "Language for interviews",
  "description": "Tip Top Trading is the fastest-growing company in the plastic fruit sector...",
  "phrases": [
    "A good example that comes to mind…",
    "I'm particularly proud of…",
    "Timekeeping is important to me."
  ],
  "listening_challenge": {
    "question": "What was Anna's role in the university debating society?",
    "answer":   "She was treasurer."
  },
  "transcript": [
    { "speaker": "Narrator", "text": "Hold tight please! This is Anna..." },
    { "speaker": "Anna",     "text": "Oh, a little nervous but I really want this job." }
  ],
  "transcript_turns": 36
}
```

---

## 4. 数据库表 `bbc_eaw_episodes`

定义在 `app/models/db.py`。**不绑 user_id**（共享公共素材）。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | autoincrement |
| slug | STRING UNIQUE | `01-the-interview` |
| url | STRING | 原始 BBC URL |
| title | STRING | `The Interview` |
| episode_id | STRING idx | `160706`（BBC 内部编号 = YYMMDD） |
| air_date | STRING | `06 Jul 2016` |
| topic | STRING idx | `Language for interviews` |
| description | STRING | 剧情简介（可能多段，`\n` 分隔） |
| phrases_json | STRING | JSON 数组：`["A good example that comes to mind…", ...]` |
| listening_question | STRING | 听力题题目 |
| listening_answer | STRING | 听力题答案 |
| transcript_json | STRING | JSON 数组：`[{speaker, text}, ...]` |
| transcript_turns | INTEGER | 对白条数（聚合统计 / 排序便利） |
| source_html_path | STRING | 原始 HTML 相对路径（追溯用） |
| created_at / updated_at | DATETIME | 标准时间戳 |

**索引**：`slug` UNIQUE / `episode_id` / `topic`

---

## 5. 当前规模

| 指标 | 值 |
|---|---|
| episodes | 67（intro + 1–66） |
| 播出周期 | 2016-07-01 → 2017-10-04 |
| 对白 turns 总 | 2,836 |
| turns / 集 | min 17 · max 62 · avg 42.3 |
| phrases 总 | 273 |
| phrases / 集 | min 2 · max 8 · avg 4.1 |
| raw HTML | 29 MB |
| parsed JSON | 576 KB |
| DB 行 | 67（已入库） |

---

## 6. 使用方式

```python
from sqlalchemy.orm import Session
from app.models.db import engine, BbcEawEpisode
import json

with Session(engine) as s:
    ep = s.query(BbcEawEpisode).filter_by(slug="01-the-interview").one()
    phrases   = json.loads(ep.phrases_json)        # list[str]
    transcript = json.loads(ep.transcript_json)    # list[{speaker,text}]

    # 按主题搜索（模糊）
    interview_eps = (
        s.query(BbcEawEpisode)
         .filter(BbcEawEpisode.topic.ilike("%interview%"))
         .all()
    )
```

---

## 7. 实现细节 / 已知边角

- **抓取走 `curl`**：最初用 Python `urllib` 在 macOS 上 `CERTIFICATE_VERIFY_FAILED`（系统根证书路径问题）；改 subprocess 调 curl 一次跑通。
- **BBC 自家拼写错误**：`08-gving-praise`（缺 i）、`44-language-to-in-dealing-with-it-support`（缺 use），按原 slug 抓，已在 `bbc_eaw_fetch.py` 内联注释。
- **DOM 锚点**：`<h3>English at Work</h3>` 之后依次是 `<h3>{title}</h3>` / `<h3>Episode {id} / {date}</h3>` / `<h3>{topic}</h3>` / `<h3>Transcript</h3>`。intro 集没有 topic h3。
- **Transcript 分行策略**：原本用 `<strong>{Speaker}</strong>` 直接抓 speaker name，遇到几集变体（`&nbsp;` 填充、`<span data-mce-mark>` 包裹、`</strong><strong>` 拆段）失配。改成"按 `<p>` 内第一个 `<br />` 切分"后所有 67 集稳定。
- **Phrases 列表**：大部分集有 "Phrases from the programme:" 标记，少数（如 ep55）裸 `<ul>`。fallback 为 description block 内第一个 `<ul>`。
- **Listening answer 去重**：BBC 在答案区会重复一遍问题，parser 中检测并 strip 掉前缀。
- **Intro 集**：listening_question 与 answer 在原 HTML 同一 `<p>` 内，未单独分离（数据可用，但格式略糙）。

---

## 8. 重跑 Pipeline

```bash
# 抓取（已下集自动跳过）
python3 scripts/bbc_eaw_fetch.py
python3 scripts/bbc_eaw_fetch.py --force                    # 强刷全部
python3 scripts/bbc_eaw_fetch.py --only 01-the-interview    # 单集调试

# 解析
python3 scripts/bbc_eaw_parse.py

# 入库（按 slug upsert，重跑安全）
python3 scripts/bbc_eaw_seed.py --dry-run
python3 scripts/bbc_eaw_seed.py
```

---

## 9. 下一步集成方向（V0.8 候选）

1. **场景模式骨架**：`topic` 直接当场景标签（interview / pitch / appraisal / negotiation / cold-calling / networking / wedding…）；前端"职场场景"页按 topic 分组列出可用集
2. **目标句型卡**：phrases 转成"今日重点表达"，可流入现有 `pronunciation_cards` 做发音练习，或新建 `phrase_cards` 走 FSRS 复习
3. **角色扮演对白**：transcript 给 Alex 当 system prompt 里的"参考剧本"，让他在练习场景时能模拟 Paul / Denise / Tom 的语气与典型回应
4. **听力小测**：listening_challenge 直接做练习页"听后小测"

均可在不再访问 BBC 的前提下，靠现有 raw + parsed + DB 三层数据扩展。
