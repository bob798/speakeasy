# V0.4 发音练习模块 — 实施计划

> 版本：V0.4 Phase 1 | 日期：2026-04-16 | 状态：共识通过（Planner-Architect-Critic R2）

---

## RALPLAN-DR 摘要

### 原则（Principles）

1. **最小侵入** — 不修改现有 chat/memory/review 代码，新模块独立存在
2. **复用已有模式** — 沿用 GrammarCard 的 FSRS 模式、TTS 服务、sync Session(engine) 访问模式
3. **容错优先** — B站字幕提取不稳定，必须有 manual paste fallback，提取失败不阻塞用户
4. **Phase 1 自评** — 不引入外部评分 API，用户自行对比录音与 TTS 播放来判断发音质量
5. **单页完整体验** — practice.html 一个页面覆盖：输入内容 → 标记词句 → 练习 → 复习队列

### 决策驱动（Decision Drivers）

1. **开发速度** — V0.4 是中等版本，目标 6 个 Step 完成
2. **B站 API 可靠性** — 字幕不一定存在，反爬策略可能变化
3. **与现有 FSRS 体系的一致性** — 发音卡和语法卡共用调度器但独立存储

### 可行方案对比

#### 方案 A：独立 `PronunciationCard` 表（推荐）

| 维度 | 评估 |
|---|---|
| 优点 | 字段专为发音设计（text, context, source_url）；不污染 GrammarCard；可独立查询和展示 |
| 优点 | FSRS 逻辑通过共享 `fsrs_utils.py` 复用，只是存储在自己的表中 |
| 缺点 | 新增一张表，需要新的 CRUD |
| 风险 | 低 — 模式与 GrammarCard 完全对称，开发量可控 |

#### 方案 B：复用 `GrammarCard` 表，增加 `card_type` 字段

| 维度 | 评估 |
|---|---|
| 优点 | 不新增表，统一卡片管理；未来跨卡片查询只需单表 WHERE |
| 缺点 | GrammarCard 字段（example_wrong/right, explanation_zh）对发音卡无意义 |
| 缺点 | 需要修改现有查询全部加 `card_type` 过滤，影响 V0.3 已稳定代码 |
| 风险 | 中 — 违反"不修改已完成版本代码"原则 |
| 反论（Architect antithesis） | 若 V0.5 引入统一"每日复习"需要 UNION 查询两张表，而方案 B 只需单表 WHERE card_type IN (...)。但当前 V0.4 不涉及此需求。 |

**结论：选方案 A。** 方案 B 被否决因为：(1) 违反项目禁止修改已完成版本代码的规则；(2) 字段不匹配导致 null 值泛滥；(3) 查询逻辑回归测试成本高。

**⚠️ 第三种卡片类型决策门（Architect 建议）：** 如果未来出现第三种卡片类型（如 vocabulary_cards），**必须先提取 BaseCard mixin/抽象层**，不允许再新建第三张平行表。当前两张表是可接受的复杂度上限。

---

## ADR-007: 发音卡独立表设计

| 字段 | 内容 |
|---|---|
| **Decision** | 新增 `pronunciation_cards` 表，独立于 `grammar_cards`；提取共享 `fsrs_utils.py` 消除 FSRS 逻辑重复 |
| **Drivers** | 字段差异大；不修改已稳定代码；FSRS 调度逻辑可通过工具模块复用 |
| **Alternatives** | 复用 GrammarCard + card_type 区分（否决：违反不改旧代码原则，虽然未来跨卡片查询更简单但 V0.4 不需要） |
| **Why Chosen** | 最小侵入，字段贴合发音场景，开发模式与 V0.3 对称 |
| **Consequences** | 多一张表维护；未来统一复习视图需 UNION 查询；memory.html 未来可能需要第四个 Tab |
| **Follow-ups** | Phase 2 评估是否统一卡片抽象层；第三种卡片类型出现前必须先重构 |

---

## 数据库设计

### 新增表：`pronunciation_cards`

```python
class PronunciationCard(Base):
    __tablename__ = "pronunciation_cards"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    user_id         = Column(String, nullable=False, index=True)
    text            = Column(String, nullable=False)           # 标记的词或句子（存储时 strip + 单空格规范化）
    context         = Column(String, nullable=False, default="")  # 上下文句子（如果标记的是单词）
    source_url      = Column(String, nullable=True)            # B站链接（可选）
    source_title    = Column(String, nullable=True)            # 视频标题（可选）
    fsrs_card_data  = Column(String, nullable=False, default="")  # 与 grammar_cards 同名，利于未来迁移
    status          = Column(String, nullable=False, default="active")  # active | deleted（与 grammar_cards 同名）
    practice_count  = Column(Integer, nullable=False, default=0)
    created_at      = Column(DateTime, default=datetime.utcnow)  # 注：新代码用 datetime.now(timezone.utc)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "text"),)
```

**text 规范化策略：** 存储前执行 `text.strip().lower()` + 合并连续空格。UniqueConstraint 作用于规范化后的值。这意味着 "Hello World" 和 "hello world" 视为同一条卡片。

**与 GrammarCard 的关键差异：**
- 无 pending 状态 — 用户主动标记即进入 active + FSRS
- `text` 代替 `key` — 存储规范化后的原文
- `context` — 单词标记时保留所在句子
- `source_url` / `source_title` — 追溯来源
- `practice_count` — 记录练习次数
- FSRS 列名（`fsrs_card_data`, `status`, `created_at`, `updated_at`）与 GrammarCard 完全一致，利于未来抽取 BaseCard

### 新增表：`subtitle_sources`（必建，用于缓存字幕）

```python
class SubtitleSource(Base):
    __tablename__ = "subtitle_sources"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    user_id       = Column(String, nullable=False, index=True)
    bvid          = Column(String, nullable=True, index=True)    # B站 BV号
    title         = Column(String, nullable=True)
    subtitle_json = Column(String, nullable=False)               # 完整字幕 JSON（上限 500KB）
    created_at    = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "bvid"),)      # 防止重复导入同一视频
```

---

## B站字幕提取 — 技术实现详情

### API 调用链（4 步）

```
步骤 1: 从 URL 提取 BV 号
  输入: "https://www.bilibili.com/video/BV1xx411c7XW" 或 "BV1xx411c7XW"
  处理: 正则 r'(BV[a-zA-Z0-9]{10,12})' 提取
  输出: "BV1xx411c7XW"
  失败: 无法匹配 → 返回 error

步骤 2: 获取视频 cid
  请求: GET https://api.bilibili.com/x/web-interface/view?bvid={bvid}
  Header: User-Agent: "Mozilla/5.0 ..." (模拟浏览器)
  响应: {"code": 0, "data": {"cid": 12345, "title": "..."}}
  提取: data.cid, data.title
  失败: code != 0 或 httpx 超时 → 返回 error + "视频不存在或无法访问"

步骤 3: 获取字幕列表
  请求: GET https://api.bilibili.com/x/player/wbi/v2?bvid={bvid}&cid={cid}
  Header: User-Agent (同上)
  响应: {"code": 0, "data": {"subtitle": {"subtitles": [{"subtitle_url": "//...hdslb.com/...", "lan": "en"}]}}}
  提取: 选择 lan="en" 或第一个可用字幕的 subtitle_url
  失败: subtitles 为空 → 返回 error + "该视频无字幕，请手动粘贴"

步骤 4: 获取字幕内容
  请求: GET https:{subtitle_url}  (补全协议)
  域名白名单: 仅允许 *.bilibili.com 或 *.hdslb.com（SSRF 防护）
  响应: {"body": [{"from": 0.5, "to": 2.1, "content": "Hello everyone"}, ...]}
  提取: body 数组作为 segments
  失败: 下载失败 → 返回 error + "字幕下载失败，请手动粘贴"
```

### SSRF 防护措施（Architect 要求）

1. **BV号格式验证**: 正则 `^BV[a-zA-Z0-9]{10,12}$`，拒绝不匹配的输入
2. **硬编码 API 域名**: 只请求 `api.bilibili.com`，不让用户输入控制 hostname
3. **字幕 URL 域名白名单**: 步骤 4 的 URL 必须匹配 `*.bilibili.com` 或 `*.hdslb.com`
4. **超时限制**: 每个请求 10s 超时，总体 30s 超时
5. **响应大小限制**: subtitle_json 超过 500KB 则拒绝

### 错误返回格式

```python
# 成功
{"title": "BBC 6 Minute English", "segments": [{"from": 0.5, "to": 2.1, "content": "Hello"}], "bvid": "BV1xx..."}

# 失败
{"error": "该视频无英文字幕，请手动粘贴文本", "segments": []}
```

---

## FSRS 初始化策略

### 发音卡 vs 语法卡的差异（Critic 要求明确）

| 维度 | 语法卡 (GrammarCard) | 发音卡 (PronunciationCard) |
|---|---|---|
| 触发方式 | LLM 自动检测错误 | 用户主动标记 |
| 初始状态 | pending (freq<2 不调度) | active (立即调度) |
| 初始 Rating | `Rating.Hard` (第 2 次出现时激活) | **`Rating.Again`** (用户刚标记=完全不会) |
| 理由 | 语法卡确认出现 2 次才激活，已有一定暴露 | 用户主动标记意味着当前不会，应尽快复习 |

**`Rating.Again` 选择理由：** 用户标记一个词/句为"陌生"，等同于 FSRS 中"完全不记得"。`Rating.Again` 会生成最短的复习间隔（通常 1 分钟→10 分钟→1 天），确保新标记的内容尽快进入复习。这与语法卡使用 `Rating.Hard`（已有一定暴露后激活）的语义不同。

### 共享 FSRS 工具模块（Architect 建议）

**新建 `app/services/fsrs_utils.py`：**

```python
"""FSRS 共享工具 — grammar_cards 和 pronunciation_cards 共用"""
from fsrs import FSRS, Card, Rating
import json

_scheduler = FSRS()

def create_card(initial_rating: Rating = Rating.Again) -> str:
    """创建新 FSRS 卡片，返回 JSON 字符串"""
    card = Card()
    card, _ = _scheduler.review_card(card, initial_rating)
    return json.dumps(card.to_dict())

def review_card(card_json: str, rating: Rating) -> tuple[str, dict]:
    """评分更新卡片，返回 (新 JSON, card_dict)"""
    card = Card.from_dict(json.loads(card_json))
    card, _ = _scheduler.review_card(card, rating)
    new_json = json.dumps(card.to_dict())
    return new_json, card.to_dict()

def get_due_date(card_json: str) -> str | None:
    """从 card JSON 提取 due 日期"""
    if not card_json:
        return None
    return json.loads(card_json).get("due")

def is_due(card_json: str) -> bool:
    """判断卡片是否到期"""
    due = get_due_date(card_json)
    if not due:
        return False
    from datetime import datetime, timezone
    due_dt = datetime.fromisoformat(due)
    return due_dt <= datetime.now(timezone.utc)

RATING_MAP = {
    "again": Rating.Again,
    "hard": Rating.Hard,
    "good": Rating.Good,
    "easy": Rating.Easy,
}
```

**注意：此模块创建后，memory_service.py 中的 FSRS 逻辑保持不变（原则 1：最小侵入）。** 仅新代码（practice_service.py）引用 fsrs_utils。未来重构时再统一。

---

## 实施步骤

### Step 1: 数据模型 + FSRS 工具 + B站字幕提取服务

**文件：**
- `app/models/db.py` — 末尾添加 `PronunciationCard`, `SubtitleSource`（不改动现有代码）
- `app/services/fsrs_utils.py` — 新建，共享 FSRS 工具
- `app/services/subtitle_service.py` — 新建，B站字幕提取逻辑（含 SSRF 防护）
- `tests/test_v04_step1.py`

**实现内容：**
1. `app/models/db.py` 末尾添加两个 Model（严格不改动现有代码）
2. `fsrs_utils.py`：按上文规格实现 `create_card`, `review_card`, `get_due_date`, `is_due`, `RATING_MAP`
3. `subtitle_service.py`:
   - `def extract_bvid(url: str) -> str | None` — 正则提取，失败返回 None
   - `async def fetch_bilibili_subtitles(bvid: str) -> dict` — 4 步 API 链（见上文详情）
   - 使用 `httpx.AsyncClient(trust_env=False, timeout=10.0)`
   - 域名白名单验证 + BV号格式验证 + 500KB 大小限制
   - 提取失败返回 `{"error": "具体原因", "segments": []}`

**测试（`test_v04_step1.py`）— 使用 test_user_v04_1：**
```python
# 1. 表创建
assert PronunciationCard.__tablename__ == "pronunciation_cards"
assert SubtitleSource.__tablename__ == "subtitle_sources"
Base.metadata.create_all(engine)  # 无异常

# 2. PronunciationCard CRUD
# 创建卡片 → fsrs_card_data 非空，status=="active"
# 重复 (user_id, text) → IntegrityError

# 3. SubtitleSource 唯一约束
# 同 (user_id, bvid) → IntegrityError

# 4. BV号提取
assert extract_bvid("https://www.bilibili.com/video/BV1xx411c7XW") == "BV1xx411c7XW"
assert extract_bvid("BV1xx411c7XW") == "BV1xx411c7XW"
assert extract_bvid("invalid-url") is None
assert extract_bvid("http://evil.com/BV") is None  # 太短

# 5. SSRF 防护
# subtitle_url 不匹配白名单 → 拒绝请求

# 6. fsrs_utils
card_json = create_card(Rating.Again)
assert json.loads(card_json).get("due") is not None
new_json, _ = review_card(card_json, Rating.Good)
assert json.loads(new_json)["due"] != json.loads(card_json)["due"]

# 7. Mock httpx 测试
# 给定正确的 B站 API 响应 → 返回正确 segments
# 给定 code != 0 → 返回 error
# 给定空 subtitles 列表 → 返回 "该视频无字幕"
```

---

### Step 2: 发音练习后端 API

**文件：**
- `app/routers/practice.py` — 新建
- `app/services/practice_service.py` — 新建
- `tests/test_v04_step2.py`

**API 端点：**

| 端点 | 方法 | 说明 |
|---|---|---|
| `/practice/subtitles` | POST | 接收 B站 URL 或手动文本，返回字幕 segments |
| `/practice/cards` | POST | 批量创建发音卡（用户标记的词/句） |
| `/practice/cards` | GET | 获取用户发音卡列表（支持 status 过滤 + limit/offset 分页） |
| `/practice/cards/{id}/review` | POST | FSRS 评分更新（rating: again/hard/good/easy） |
| `/practice/cards/{id}` | DELETE | 软删除（status='deleted'） |
| `/practice/due` | GET | 获取到期复习卡（due <= now，按 stability 升序，limit 默认 10） |

**practice_service.py 核心逻辑：**
```python
from app.services.fsrs_utils import create_card, review_card, RATING_MAP, is_due
from fsrs import Rating

def create_pronunciation_cards(user_id: str, items: list[dict]) -> dict:
    """
    items: [{text, context, source_url, source_title}]
    text 存储前规范化：strip().lower() + 合并连续空格
    初始 FSRS: create_card(Rating.Again) — 用户标记=完全不会，最短复习间隔
    返回: {"created": N, "skipped": M}  (skipped = 已存在的重复项)
    """

def review_pronunciation_card(card_id: int, user_id: str, rating_str: str) -> dict:
    """
    rating_str → RATING_MAP → review_card()
    更新 practice_count += 1
    返回: {"id": card_id, "new_due": "...", "practice_count": N}
    """

def get_due_pronunciation_cards(user_id: str, limit: int = 10) -> list:
    """同 memory_service.get_injectable_cards 模式: status='active', due <= now, 按 stability 升序"""
```

**数据库访问：使用 sync `Session(engine)` 模式**（与 memory_service.py 一致）。

**测试（`test_v04_step2.py`）— 使用 test_user_v04_2：**
```python
# 1. POST /practice/subtitles {"url": "https://bilibili.com/video/BVxxx"}
#    → 200 + {"segments": [...]} (mock httpx)

# 2. POST /practice/subtitles {"text": "Hello world.\nHow are you?"}
#    → 200 + {"segments": [{"content": "Hello world."}, {"content": "How are you?"}]}

# 3. POST /practice/cards {"user_id": "x", "items": [{"text": "hello", "context": "Hello world."}]}
#    → 201 + {"created": 1, "skipped": 0}
#    再次提交相同 text → {"created": 0, "skipped": 1}

# 4. GET /practice/cards?user_id=x → 200 + cards 数组
#    验证: 每张卡有 id, text, context, fsrs_card_data, status, practice_count

# 5. GET /practice/cards?user_id=x&limit=1&offset=0 → 返回 1 张卡

# 6. POST /practice/cards/1/review {"user_id": "x", "rating": "good"}
#    → 200 + {"new_due": "2026-...", "practice_count": 1}
#    验证 fsrs_card_data 中 due 已更新

# 7. POST /practice/cards/1/review {"user_id": "x", "rating": "again"}
#    → 200, new_due 比 "good" 评分后更近

# 8. DELETE /practice/cards/1?user_id=x → 200
#    GET /practice/cards?user_id=x → 该卡不出现

# 9. GET /practice/due?user_id=x
#    创建卡片(Rating.Again) → 立即出现在 due 列表
#    评分 Rating.Easy → 从 due 列表消失
#    已删除的卡 → 不出现
```

---

### Step 3: 前端 — practice.html 页面骨架 + 字幕加载

**文件：**
- `static/practice.html` — 新建
- `main.py` — 添加 `from app.routers.practice import router as practice_router` + `app.include_router(practice_router)` + `@app.get("/practice")` 返回 `FileResponse("static/practice.html")`
- `static/index.html` — header 右侧添加 `<a href="/practice" title="发音练习">🎙️</a>`（在 🧠 之后）
- `tests/test_v04_step3.py` — 后端路由可达性测试

**页面结构：**
```
Header: Speakeasy 导航栏（首页 | 🧠记忆 | 🎙️练习）
─────────────────────────────
[输入区]
  - URL 输入框 + "提取字幕" 按钮
  - "或手动粘贴" 折叠区域 + textarea + "加载" 按钮
  - 加载状态指示器（spinner）
  - 错误提示区域

[字幕展示区]（提取/粘贴后显示）
  - 逐句展示，每句可点击标记（高亮切换）
  - 标记计数："已标记 N 项"
  - "开始练习" 按钮（标记 > 0 时启用）

[练习区]（点击开始练习后显示）
  - 见 Step 4

[复习入口]
  - 见 Step 5
```

**手动粘贴文本分割策略：** 按 `\n` 分割为行，每行为一个 segment。用户在粘贴前自行整理格式。不做智能句号分割（避免中英文标点混乱问题）。

**测试策略（Critic 要求明确）：**
- `test_v04_step3.py`（自动化，后端路由测试）：
  ```python
  # 1. GET /practice → 200, content-type text/html
  # 2. GET / → 200, 响应体包含 href="/practice"
  # 3. POST /practice/subtitles {"text": "line1\nline2"} → 200 + 2 segments
  ```
- **手动验证清单**（前端 UI）：
  - [ ] 页面加载正常，暖色调风格一致
  - [ ] URL 输入 + 提取按钮可交互
  - [ ] 手动粘贴区域展开/折叠正常
  - [ ] 字幕逐行显示，点击高亮切换
  - [ ] 标记计数实时更新
  - [ ] 无标记时"开始练习"按钮禁用

---

### Step 4: 前端 — 录音 + TTS + 自评交互

**文件：**
- `static/practice.html` — 续写 JS 逻辑

**交互流程：**
1. 用户看到当前练习项文本 + 上下文
2. 点击 🔊 TTS 播放 → 调用 `POST /tts {text}` → 播放音频（复用现有接口）
3. 点击 🎙️ 录音 → `navigator.mediaDevices.getUserMedia({audio: true})` → MediaRecorder 录制
4. 点击 ⏸️ 停止录音 → 生成 Blob → 创建 Object URL
5. 点击 ▶️ 回放 → 播放录音 Blob
6. 可反复听 TTS / 重新录音 / 回放对比，不限次数
7. 点击自评按钮（Again / Hard / Good / Easy）→ `POST /practice/cards/{id}/review`
8. 自动切换到下一个练习项
9. 全部完成 → 显示练习总结（本次数量 + 各评级分布）

**录音实现（不依赖 STT）：**
```javascript
// 与现有 stt-provider.js 的区别：
// - 不需要 POST 到 /stt（不做语音识别）
// - 只录制 + 本地回放
// - 不需要 VAD 自动停止（用户手动停止）
let mediaRecorder, chunks = [];
async function startRecording() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    chunks = [];
    mediaRecorder.ondataavailable = e => chunks.push(e.data);
    mediaRecorder.start();
}
function stopRecording() {
    return new Promise(resolve => {
        mediaRecorder.onstop = () => {
            const blob = new Blob(chunks, { type: 'audio/webm' });
            resolve(URL.createObjectURL(blob));
        };
        mediaRecorder.stop();
    });
}
```

**测试策略：**
- **无自动化测试文件**（前端录音/音频播放无法在 pytest 中测试）
- **手动验证清单：**
  - [ ] TTS 播放调用 /tts 成功，音频正常
  - [ ] 录音按钮状态切换：idle → recording（红色脉冲）→ recorded
  - [ ] 停止录音后可回放
  - [ ] 重新录音覆盖上一次
  - [ ] 自评按钮点击后，API 返回 200，切换到下一项
  - [ ] practice_count 自增 1（API 返回值验证）
  - [ ] 最后一项完成后显示练习总结

---

### Step 5: 复习队列 + 完整闭环

**文件：**
- `static/practice.html` — 添加复习入口 UI
- `tests/test_v04_step5.py` — 后端 FSRS 调度测试

**实现内容：**
1. practice.html 顶部添加"今日复习"入口：
   - 页面加载时调用 `GET /practice/due?user_id=x` 
   - 有到期卡时显示红色 badge + 数量
   - 点击进入复习模式（同练习区交互，数据来源从标记项切换为 due 卡）
2. 复习完成后回到主界面，badge 更新

**测试（`test_v04_step5.py`）— 使用 test_user_v04_5：**
```python
# 后端 FSRS 调度正确性（纯 API 测试，不涉及 UI）：

# 1. 创建卡片(Rating.Again) → GET /practice/due → 卡片在列表中
# 2. 评分 Rating.Easy → GET /practice/due → 卡片不在列表中（due 在未来）
# 3. 评分 Rating.Again → GET /practice/due → 卡片重新出现（due 极短）
# 4. 软删除卡片 → GET /practice/due → 不出现
# 5. 批量创建 5 张卡 → GET /practice/due?limit=3 → 返回 3 张，按 stability 升序
```

- **手动验证清单：**
  - [ ] 页面加载时 badge 正确显示到期数量
  - [ ] 点击进入复习模式，逐卡练习
  - [ ] 复习完成后 badge 归零
  - [ ] 端到端：粘贴文本 → 标记 → 练习 → 自评 Again → 刷新页面 → 复习 badge 出现

---

### Step 6: 集成测试 + 回归 + 文档更新

**文件：**
- `tests/test_v04_e2e.py` — 端到端 API 测试
- `.claude/CLAUDE.md` — 更新数据表清单、API 接口清单、版本状态

**测试（`test_v04_e2e.py`）— 使用 test_user_v04_e2e：**
```python
# 完整 API 级 E2E：
# 1. POST /practice/subtitles {"text": "..."} → segments
# 2. POST /practice/cards → 创建 3 张卡
# 3. GET /practice/cards → 3 张 active 卡
# 4. POST /practice/cards/{id}/review (rating=good) → due 更新
# 5. POST /practice/cards/{id}/review (rating=again) → due 更短
# 6. GET /practice/due → 正确的到期卡集合
# 7. DELETE /practice/cards/{id} → 软删除
# 8. 全量回归: pytest tests/ -v 全绿
```

**CLAUDE.md 更新内容：**
- 数据表清单 +2：`pronunciation_cards`, `subtitle_sources`
- API 接口清单 +6：`/practice/*` 系列
- 文件目录结构更新
- 版本状态：V0.4 ✅

---

## 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施（具体） |
|---|---|---|---|
| B站 API 反爬导致字幕提取失败 | 高 | 中 | manual paste fallback 始终可用；`fetch_bilibili_subtitles` 捕获所有异常返回 error dict；前端显示"请手动粘贴" |
| B站视频无 CC 字幕 | 高 | 低 | 步骤 3 检测空 subtitles 列表 → 返回具体错误信息 + 自动展开手动粘贴区 |
| SSRF 攻击（用户输入恶意 URL） | 低 | 高 | BV号正则验证 + 硬编码 API 域名 + 字幕 URL 白名单 + 超时/大小限制 |
| httpx 被 SOCKS 代理影响 | 中 | 中 | `trust_env=False`（项目已有先例，见 model_client.py） |
| Web Audio API 浏览器兼容性 | 低 | 低 | 现有 STT 录音已在用，无新增风险 |
| SQLite 并发写入冲突 | 低 | 低 | 发音练习是单用户操作，写入频率低 |

---

## 文件清单

| 操作 | 文件路径 | Step |
|---|---|---|
| **修改** | `app/models/db.py` — 末尾添加 2 个 Model | 1 |
| **修改** | `main.py` — 添加 practice router + `/practice` 路由 | 3 |
| **修改** | `static/index.html` — header 添加 🎙️ 导航链接 | 3 |
| **修改** | `.claude/CLAUDE.md` — 更新表/接口/版本 | 6 |
| **新建** | `app/services/fsrs_utils.py` | 1 |
| **新建** | `app/services/subtitle_service.py` | 1 |
| **新建** | `app/services/practice_service.py` | 2 |
| **新建** | `app/routers/practice.py` | 2 |
| **新建** | `static/practice.html` | 3-5 |
| **新建** | `tests/test_v04_step1.py` | 1 |
| **新建** | `tests/test_v04_step2.py` | 2 |
| **新建** | `tests/test_v04_step3.py` | 3 |
| **新建** | `tests/test_v04_step5.py` | 5 |
| **新建** | `tests/test_v04_e2e.py` | 6 |

**修改文件：4 个 | 新建文件：10 个**

---

## 成功标准

1. `pytest tests/test_v04_*.py -v` 全部 PASS
2. `pytest tests/ -v` 全量回归无失败
3. 用户可以从 index.html 导航到 practice.html
4. 粘贴文本 → 标记 → TTS 播放 → 录音 → 回放 → 自评，完整流程可用
5. B站 URL 提取成功时字幕正常显示；失败时显示错误提示 + 自动展开手动粘贴入口
6. FSRS 复习队列正确调度发音卡（到期 badge + 复习流程）
7. 不影响现有 chat / memory / review 功能

---

## Changelog (R2 修订)

**基于 Architect + Critic 反馈合并：**
1. ✅ 新增 B站 API 4 步调用链详细文档（Critic #1）
2. ✅ 明确 FSRS 初始 Rating 为 `Rating.Again` 并说明与 GrammarCard `Rating.Hard` 的差异原因（Critic #2）
3. ✅ 每个 Step 明确测试策略：自动化测试文件 + 手动验证清单（Critic #3）
4. ✅ SSRF 防护措施详细规格（Architect #1 + Critic #4）
5. ✅ `subtitle_sources` 改为必建 + UniqueConstraint("user_id", "bvid")（Architect #2）
6. ✅ 提取 `fsrs_utils.py` 共享 FSRS 工具（Architect #3）
7. ✅ 记录第三种卡片类型决策门（Architect #4）
8. ✅ text 规范化策略（strip + lower + 合并空格）（Architect 额外建议）
9. ✅ subtitle_json 500KB 大小限制（Architect 额外建议）
10. ✅ 明确使用 sync Session(engine) 模式（Critic 额外建议）
11. ✅ GET /practice/cards 添加 limit/offset 分页（Critic 额外建议）
12. ✅ 手动粘贴文本按 \n 分割，不做智能句号分割（Critic 歧义消除）
13. ✅ 添加 Step 6 CLAUDE.md 文档更新（Critic 额外建议）
14. ✅ ADR 编号更新为 ADR-007（避免与现有冲突）
