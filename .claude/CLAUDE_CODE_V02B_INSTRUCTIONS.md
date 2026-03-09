# Speakeasy V0.2b — Claude Code 执行指令

> 如任何步骤上下文不清晰，参考项目根目录 SPEC_V02B.md
> Human 只验收最终结果，过程中遇到文档未覆盖的情况：停下来问，不自行决策

---

## 工作规则

1. 按 Step 顺序执行，不跳步
2. 每个 Step = 实现代码 + 自测脚本，测试全部 PASS 才进入下一步
3. 测试未通过则自行修复，直到全绿
4. 所有 pip install 在激活的 venv 中执行
5. 测试数据使用独立 user_id（如 `test_user_v02b`），每个测试后清理
6. 不修改 V0.2a 已有测试
7. mock 策略：只 mock 外部 LLM 调用，不 mock 内部服务
8. 每个 Step 完成后终端打印 `✅ Step N 完成`

---

## Step 1：环境 + 数据表

### 实现

```bash
# 1. 安装依赖
pip install fsrs
# 在 requirements.txt 末尾追加：fsrs
```

在 `app/models/db.py` 追加两张表（保留 V0.2a 所有内容不变）：

```python
from sqlalchemy import UniqueConstraint

class GrammarCard(Base):
    __tablename__ = "grammar_cards"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    user_id        = Column(String, nullable=False, index=True)
    key            = Column(String, nullable=False)
    content        = Column(String, nullable=False, default="")
    example_wrong  = Column(String, nullable=False, default="")
    example_right  = Column(String, nullable=False, default="")
    explanation_zh = Column(String, nullable=False, default="")
    frequency      = Column(Integer, nullable=False, default=1)
    fsrs_card_data = Column(String, nullable=False, default="")   # pending 时为空字符串
    status         = Column(String, nullable=False, default="pending")  # pending | active | deleted
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "key"),)


class SessionReview(Base):
    __tablename__ = "session_reviews"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    session_id    = Column(String, nullable=False, unique=True)
    user_id       = Column(String, nullable=False)
    errors        = Column(String, nullable=False, default="[]")    # JSON
    highlights    = Column(String, nullable=False, default="[]")    # JSON
    stats         = Column(String, nullable=False, default="{}")    # JSON
    is_user_rated = Column(Boolean, nullable=False, default=False)
    created_at    = Column(DateTime, default=datetime.utcnow)
```

重新执行 `create_all` 创建新表。

### 自测脚本：tests/test_step1.py

```python
import pytest
from fsrs import FSRS, Card, Rating
from sqlalchemy import inspect
from app.models.db import engine, GrammarCard, SessionReview, Base
from sqlalchemy.orm import Session

def test_fsrs_importable():
    scheduler = FSRS()
    card = Card()
    card, log = scheduler.review_card(card, Rating.Good)
    assert card is not None

def test_tables_exist():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "grammar_cards" in tables
    assert "session_reviews" in tables

def test_grammar_cards_schema():
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("grammar_cards")}
    required = {"id", "user_id", "key", "status", "frequency", "fsrs_card_data"}
    assert required.issubset(columns)

def test_session_reviews_schema():
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("session_reviews")}
    required = {"id", "session_id", "user_id", "errors", "highlights", "is_user_rated"}
    assert required.issubset(columns)

def test_grammar_card_crud():
    with Session(engine) as session:
        card = GrammarCard(
            user_id="test_user_v02b",
            key="test_key_step1",
            status="pending",
            frequency=1,
        )
        session.add(card)
        session.commit()
        found = session.query(GrammarCard).filter_by(key="test_key_step1").first()
        assert found is not None
        assert found.status == "pending"
        session.delete(found)
        session.commit()
```

运行：`pytest tests/test_step1.py -v`
全部 PASS 后打印 `✅ Step 1 完成`

---

## Step 2：FSRS 记忆服务

> 参考 SPEC_V02B.md 第五节

### 实现：app/services/memory_service.py

实现以下四个函数：

**`update_grammar_cards(user_id: str, errors: list[dict])`**
- 遍历 errors
- 查询该 user_id + key 是否已存在
- 不存在：创建 status='pending'，frequency=1，fsrs_card_data=''
- 存在且 status='pending'：frequency+1，若 frequency 达到 2，则 status → 'active'，创建 FSRS Card（`Card()`），序列化写入 fsrs_card_data
- 存在且 status='active'：frequency+1，用 Rating.Hard 更新 FSRS Card，更新 example_wrong/example_right/explanation_zh

**`mark_errors_not_appeared(user_id: str, appeared_keys: list[str])`**
- 获取该用户所有 status='active' 的 cards
- 对不在 appeared_keys 里的 card，用 Rating.Good 更新 FSRS Card

**`get_injectable_cards(user_id: str, limit: int = 3) -> list`**
- 获取所有 status='active' 的 cards
- 过滤：card.due <= datetime.now(timezone.utc)
- 按 stability 升序排序
- 返回前 limit 条

**`build_system_prompt(user_id: str) -> str`**
- 调用 get_injectable_cards
- 无结果：返回原始 SYSTEM_PROMPT
- 有结果：拼接记忆上下文追加到 SYSTEM_PROMPT 末尾（见 SPEC_V02B.md 5.4）

### 自测脚本：tests/test_step2.py

```python
import pytest
import asyncio
import json
from datetime import datetime, timezone, timedelta
from fsrs import Card, Rating, FSRS
from sqlalchemy.orm import Session
from app.models.db import engine, GrammarCard
from app.services.memory_service import (
    update_grammar_cards,
    get_injectable_cards,
    build_system_prompt
)

TEST_USER = "test_user_v02b_step2"

def cleanup():
    with Session(engine) as s:
        s.query(GrammarCard).filter_by(user_id=TEST_USER).delete()
        s.commit()

@pytest.fixture(autouse=True)
def clean():
    cleanup()
    yield
    cleanup()

def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

ERROR_GO_WENT = {
    "key": "go_went",
    "content": "常用 go 代替 went",
    "original": "I go to the client yesterday",
    "corrected": "I went to the client yesterday",
    "explanation_zh": "yesterday 表过去，go → went",
    "count": 1,
    "confidence": 0.9
}

def test_first_occurrence_is_pending():
    run(update_grammar_cards(TEST_USER, [ERROR_GO_WENT]))
    with Session(engine) as s:
        card = s.query(GrammarCard).filter_by(user_id=TEST_USER, key="go_went").first()
    assert card.status == "pending"
    assert card.frequency == 1
    assert card.fsrs_card_data == ""

def test_second_occurrence_becomes_active():
    run(update_grammar_cards(TEST_USER, [ERROR_GO_WENT]))
    run(update_grammar_cards(TEST_USER, [ERROR_GO_WENT]))
    with Session(engine) as s:
        card = s.query(GrammarCard).filter_by(user_id=TEST_USER, key="go_went").first()
    assert card.status == "active"
    assert card.frequency == 2
    assert card.fsrs_card_data != ""
    fsrs_data = json.loads(card.fsrs_card_data)
    assert "due" in fsrs_data

def test_third_occurrence_increments_frequency():
    run(update_grammar_cards(TEST_USER, [ERROR_GO_WENT]))
    run(update_grammar_cards(TEST_USER, [ERROR_GO_WENT]))
    run(update_grammar_cards(TEST_USER, [ERROR_GO_WENT]))
    with Session(engine) as s:
        card = s.query(GrammarCard).filter_by(user_id=TEST_USER, key="go_went").first()
    assert card.frequency == 3

def test_get_injectable_cards_due():
    # 手动插入一张 due=过去 的 active card
    scheduler = FSRS()
    fsrs_card = Card()
    fsrs_card, _ = scheduler.review_card(fsrs_card, Rating.Again)
    # 强制 due 为过去时间
    card_dict = fsrs_card.to_dict()
    card_dict["due"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    with Session(engine) as s:
        row = GrammarCard(
            user_id=TEST_USER, key="due_card",
            status="active", frequency=2,
            fsrs_card_data=json.dumps(card_dict),
        )
        s.add(row)
        s.commit()

    result = run(get_injectable_cards(TEST_USER))
    assert any(c.key == "due_card" for c in result)

def test_get_injectable_cards_not_due():
    scheduler = FSRS()
    fsrs_card = Card()
    card_dict = fsrs_card.to_dict()
    card_dict["due"] = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()

    with Session(engine) as s:
        row = GrammarCard(
            user_id=TEST_USER, key="future_card",
            status="active", frequency=2,
            fsrs_card_data=json.dumps(card_dict),
        )
        s.add(row)
        s.commit()

    result = run(get_injectable_cards(TEST_USER))
    assert not any(c.key == "future_card" for c in result)

def test_build_system_prompt_with_cards():
    scheduler = FSRS()
    fsrs_card = Card()
    card_dict = fsrs_card.to_dict()
    card_dict["due"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    with Session(engine) as s:
        row = GrammarCard(
            user_id=TEST_USER, key="inject_card",
            content="常用 go 代替 went",
            status="active", frequency=2,
            fsrs_card_data=json.dumps(card_dict),
        )
        s.add(row)
        s.commit()

    prompt = run(build_system_prompt(TEST_USER))
    assert "常用 go 代替 went" in prompt

def test_build_system_prompt_without_cards():
    from app.services.chat_service import SYSTEM_PROMPT  # 或实际路径
    prompt = run(build_system_prompt(TEST_USER))
    assert prompt == SYSTEM_PROMPT
```

运行：`pytest tests/test_step2.py -v`
全部 PASS 后打印 `✅ Step 2 完成`

---

## Step 3：对话分析服务

> 参考 SPEC_V02B.md 第四节

### 实现

**app/prompts/review.py**
复制 SPEC_V02B.md 中的 REVIEW_PROMPT 常量。

**app/services/review_service.py**

```python
async def analyze_conversation(session_id: str, user_id: str, history: list[dict]) -> dict | None:
    """
    返回 None 表示分析失败，调用方降级到今日一句
    """
    try:
        user_messages = [m for m in history if m['role'] == 'user']
        if len(user_messages) < 2:
            return None

        conversation_text = "\n".join(f"user: {m['content']}" for m in user_messages)

        llm = get_client()   # 使用现有 LLM 工厂函数
        raw = await llm.complete(
            REVIEW_PROMPT.format(conversation=conversation_text),
            max_tokens=1000
        )

        result = json.loads(raw)
        result['errors'] = [e for e in result['errors'] if e.get('confidence', 0) >= 0.7]

        stats = {
            "turns": len([m for m in history]),
            "duration_seconds": 0   # 前端传入或估算
        }
        result['stats'] = stats

        await save_session_review(session_id, user_id, result)
        return result

    except Exception as e:
        logger.error("复盘分析失败 session_id=%s error=%s", session_id, e)
        return None


async def save_session_review(session_id: str, user_id: str, data: dict):
    """写入 session_reviews 表"""
    # 实现略，标准 ORM 写入
```

### 自测脚本：tests/test_step3.py

```python
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, patch
from app.services.review_service import analyze_conversation

TEST_USER = "test_user_v02b_step3"
TEST_SESSION = "test_session_step3"

def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

HISTORY_WITH_ERROR = [
    {"role": "user", "content": "Yesterday I go to the client office and present the report."},
    {"role": "assistant", "content": "That sounds like a productive day!"},
    {"role": "user", "content": "Yes, I go there every week actually."},
]

HISTORY_CORRECT = [
    {"role": "user", "content": "I went to the gym this morning."},
    {"role": "assistant", "content": "Nice! How was the workout?"},
    {"role": "user", "content": "It was great, I feel much better now."},
]

HISTORY_IDIOMATIC = [
    {"role": "user", "content": "The meeting totally threw me off."},
    {"role": "assistant", "content": "I understand that feeling."},
    {"role": "user", "content": "Yeah, I wasn't prepared for the sudden change."},
]

def test_returns_errors_for_wrong_history():
    result = run(analyze_conversation(TEST_SESSION, TEST_USER, HISTORY_WITH_ERROR))
    assert result is not None
    assert "errors" in result
    assert len(result["errors"]) > 0
    err = result["errors"][0]
    assert "key" in err
    assert "original" in err
    assert "corrected" in err
    assert "explanation_zh" in err
    assert "confidence" in err

def test_returns_empty_errors_for_correct_history():
    result = run(analyze_conversation(TEST_SESSION + "_correct", TEST_USER, HISTORY_CORRECT))
    if result is not None:  # LLM 可能返回 None 也属正常
        assert result["errors"] == []

def test_returns_highlights_for_idiomatic():
    result = run(analyze_conversation(TEST_SESSION + "_idiomatic", TEST_USER, HISTORY_IDIOMATIC))
    if result is not None:
        assert "highlights" in result

def test_returns_none_on_llm_failure():
    with patch("app.services.review_service.get_client") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.complete.side_effect = Exception("LLM timeout")
        mock_client.return_value = mock_instance
        result = run(analyze_conversation(TEST_SESSION + "_fail", TEST_USER, HISTORY_WITH_ERROR))
    assert result is None

def test_returns_none_for_short_history():
    short = [{"role": "user", "content": "Hello"}]
    result = run(analyze_conversation(TEST_SESSION + "_short", TEST_USER, short))
    assert result is None
```

运行：`pytest tests/test_step3.py -v`
全部 PASS 后打印 `✅ Step 3 完成`

---

## Step 4：升级 /chat/summary 接口

> 替换原有今日一句逻辑，今日一句作为降级保留

### 实现

在处理 `POST /chat/summary` 的路由中：

```python
@router.post("/chat/summary")
async def chat_summary(request: SummaryRequest):
    result = await analyze_conversation(
        session_id=request.session_id,
        user_id=request.user_id,
        history=request.history
    )

    if result is not None:
        appeared_keys = [e["key"] for e in result.get("errors", [])]
        await update_grammar_cards(request.user_id, result.get("errors", []))
        await mark_errors_not_appeared(request.user_id, appeared_keys)
        return {"type": "review", **result}
    else:
        # 降级：返回今日一句（复用 V0.1 原有逻辑）
        tip = await get_daily_tip()
        return {"type": "tip", "tip": tip}
```

### 自测脚本：tests/test_step4.py

```python
import pytest
import json
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient
from app.main import app  # 或实际 FastAPI app 入口

TEST_USER = "test_user_v02b_step4"

@pytest.mark.asyncio
async def test_summary_returns_review():
    history = [
        {"role": "user", "content": "Yesterday I go to the client office."},
        {"role": "assistant", "content": "Sounds great!"},
        {"role": "user", "content": "I go there every week."},
    ]
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post("/chat/summary", json={
            "user_id": TEST_USER,
            "session_id": "test_session_step4_a",
            "history": history
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "review"
    assert "errors" in data
    assert "highlights" in data
    assert "stats" in data

@pytest.mark.asyncio
async def test_summary_fallback_on_llm_failure():
    with patch("app.services.review_service.get_client") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.complete.side_effect = Exception("LLM down")
        mock_client.return_value = mock_instance
        async with AsyncClient(app=app, base_url="http://test") as client:
            resp = await client.post("/chat/summary", json={
                "user_id": TEST_USER,
                "session_id": "test_session_step4_b",
                "history": [
                    {"role": "user", "content": "I go yesterday."},
                    {"role": "assistant", "content": "Ok."},
                    {"role": "user", "content": "I go again."},
                ]
            })
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "tip"
    assert "tip" in data
    assert len(data["tip"]) > 0

@pytest.mark.asyncio
async def test_summary_fallback_on_short_history():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post("/chat/summary", json={
            "user_id": TEST_USER,
            "session_id": "test_session_step4_c",
            "history": [{"role": "user", "content": "Hi"}]
        })
    data = resp.json()
    assert data["type"] == "tip"

@pytest.mark.asyncio
async def test_summary_creates_grammar_cards():
    from sqlalchemy.orm import Session
    from app.models.db import engine, GrammarCard

    history = [
        {"role": "user", "content": "Yesterday I go to the office."},
        {"role": "assistant", "content": "Got it."},
        {"role": "user", "content": "I go there every day last week."},
    ]
    async with AsyncClient(app=app, base_url="http://test") as client:
        await client.post("/chat/summary", json={
            "user_id": TEST_USER,
            "session_id": "test_session_step4_d",
            "history": history
        })

    with Session(engine) as s:
        cards = s.query(GrammarCard).filter_by(user_id=TEST_USER).all()
    assert len(cards) > 0

    # 清理
    with Session(engine) as s:
        s.query(GrammarCard).filter_by(user_id=TEST_USER).delete()
        s.commit()
```

运行：`pytest tests/test_step4.py -v`
全部 PASS 后打印 `✅ Step 4 完成`

---

## Step 5：升级 /chat 接口注入记忆

### 实现

在 `POST /chat` 路由中，将原来的：
```python
system_prompt = SYSTEM_PROMPT
```
替换为：
```python
system_prompt = await build_system_prompt(request.user_id)
```

### 自测脚本：tests/test_step5.py

```python
import pytest
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient
from sqlalchemy.orm import Session
from app.models.db import engine, GrammarCard
from app.main import app

TEST_USER = "test_user_v02b_step5"

def insert_due_card():
    from fsrs import Card, Rating, FSRS
    scheduler = FSRS()
    fsrs_card = Card()
    card_dict = fsrs_card.to_dict()
    card_dict["due"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    with Session(engine) as s:
        row = GrammarCard(
            user_id=TEST_USER, key="step5_card",
            content="常用 go 代替 went",
            status="active", frequency=2,
            fsrs_card_data=json.dumps(card_dict),
        )
        s.add(row)
        s.commit()

def cleanup():
    with Session(engine) as s:
        s.query(GrammarCard).filter_by(user_id=TEST_USER).delete()
        s.commit()

@pytest.fixture(autouse=True)
def clean():
    cleanup()
    yield
    cleanup()

@pytest.mark.asyncio
async def test_chat_injects_memory_in_system_prompt():
    insert_due_card()
    captured = {}

    original_get_client = None
    try:
        import app.services.chat_service as cs
        original_get_client = cs.get_client
    except Exception:
        pass

    with patch("app.services.chat_service.get_client") as mock_client:
        mock_instance = AsyncMock()
        async def fake_complete(messages, **kwargs):
            captured["system"] = next(
                (m["content"] for m in messages if m.get("role") == "system"), ""
            )
            return "That sounds great!"
        mock_instance.complete = fake_complete
        mock_client.return_value = mock_instance

        async with AsyncClient(app=app, base_url="http://test") as client:
            await client.post("/chat", json={
                "user_id": TEST_USER,
                "message": "Hello Alex",
                "history": []
            })

    assert "常用 go 代替 went" in captured.get("system", "")

@pytest.mark.asyncio
async def test_chat_no_injection_without_due_cards():
    from app.services.chat_service import SYSTEM_PROMPT
    captured = {}

    with patch("app.services.chat_service.get_client") as mock_client:
        mock_instance = AsyncMock()
        async def fake_complete(messages, **kwargs):
            captured["system"] = next(
                (m["content"] for m in messages if m.get("role") == "system"), ""
            )
            return "Hello!"
        mock_instance.complete = fake_complete
        mock_client.return_value = mock_instance

        async with AsyncClient(app=app, base_url="http://test") as client:
            await client.post("/chat", json={
                "user_id": TEST_USER,
                "message": "Hi",
                "history": []
            })

    assert captured.get("system", "") == SYSTEM_PROMPT
```

运行：`pytest tests/test_step5.py -v`
全部 PASS 后打印 `✅ Step 5 完成`

---

## Step 6：复盘查询 + 评分接口

### 实现

**GET /review/{session_id}**
```python
@router.get("/review/{session_id}")
async def get_review(session_id: str):
    review = await get_session_review(session_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return {
        "session_id": review.session_id,
        "errors": json.loads(review.errors),
        "highlights": json.loads(review.highlights),
        "stats": json.loads(review.stats),
    }
```

**POST /review/{session_id}/rate**
```python
@router.post("/review/{session_id}/rate")
async def rate_review(session_id: str, request: RateRequest):
    # request.card_key, request.rating ("good" | "again")
    rating = Rating.Good if request.rating == "good" else Rating.Again

    card_row = await get_card_by_key(request.user_id, request.card_key)
    if not card_row:
        raise HTTPException(status_code=404)

    scheduler = FSRS()
    card = Card.from_dict(json.loads(card_row.fsrs_card_data))
    card, _ = scheduler.review_card(card, rating)

    await update_card_fsrs(card_row.id, json.dumps(card.to_dict()))
    await mark_session_user_rated(session_id)

    return {"next_review": card.due.isoformat()}
```

### 自测脚本：tests/test_step6.py

```python
import pytest
import json
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.orm import Session
from app.models.db import engine, GrammarCard, SessionReview
from app.main import app

TEST_USER = "test_user_v02b_step6"
TEST_SESSION = "test_session_step6"

def seed():
    # 写入 session_review
    with Session(engine) as s:
        review = SessionReview(
            session_id=TEST_SESSION,
            user_id=TEST_USER,
            errors=json.dumps([{
                "key": "go_went",
                "original": "I go yesterday",
                "corrected": "I went yesterday",
                "explanation_zh": "go → went",
                "count": 2,
                "confidence": 0.9
            }]),
            highlights=json.dumps([]),
            stats=json.dumps({"turns": 4, "duration_seconds": 120}),
        )
        s.add(review)
        s.commit()

    # 写入对应 grammar_card
    from fsrs import Card
    import json as _json
    card_dict = Card().to_dict()
    with Session(engine) as s:
        row = GrammarCard(
            user_id=TEST_USER, key="go_went",
            content="常用 go 代替 went",
            status="active", frequency=2,
            fsrs_card_data=_json.dumps(card_dict),
        )
        s.add(row)
        s.commit()

def cleanup():
    with Session(engine) as s:
        s.query(SessionReview).filter_by(user_id=TEST_USER).delete()
        s.query(GrammarCard).filter_by(user_id=TEST_USER).delete()
        s.commit()

@pytest.fixture(autouse=True)
def setup():
    cleanup()
    seed()
    yield
    cleanup()

@pytest.mark.asyncio
async def test_get_review_success():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get(f"/review/{TEST_SESSION}")
    assert resp.status_code == 200
    data = resp.json()
    assert "errors" in data
    assert len(data["errors"]) == 1
    assert data["errors"][0]["key"] == "go_went"

@pytest.mark.asyncio
async def test_get_review_not_found():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/review/nonexistent_session")
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_rate_good_updates_fsrs():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post(f"/review/{TEST_SESSION}/rate", json={
            "user_id": TEST_USER,
            "card_key": "go_went",
            "rating": "good"
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "next_review" in data

    # 验证 next_review 是未来时间
    from datetime import datetime
    next_review = datetime.fromisoformat(data["next_review"].replace("Z", "+00:00"))
    assert next_review > datetime.now(timezone.utc)

@pytest.mark.asyncio
async def test_rate_again_sooner_than_good():
    # good 的 next_review
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp_good = await client.post(f"/review/{TEST_SESSION}/rate", json={
            "user_id": TEST_USER, "card_key": "go_went", "rating": "good"
        })
    next_good = datetime.fromisoformat(resp_good.json()["next_review"].replace("Z", "+00:00"))

    # 重置 card，再测 again
    from fsrs import Card
    with Session(engine) as s:
        card_row = s.query(GrammarCard).filter_by(user_id=TEST_USER, key="go_went").first()
        card_row.fsrs_card_data = json.dumps(Card().to_dict())
        s.commit()

    async with AsyncClient(app=app, base_url="http://test") as client:
        resp_again = await client.post(f"/review/{TEST_SESSION}/rate", json={
            "user_id": TEST_USER, "card_key": "go_went", "rating": "again"
        })
    next_again = datetime.fromisoformat(resp_again.json()["next_review"].replace("Z", "+00:00"))

    assert next_again < next_good

@pytest.mark.asyncio
async def test_is_user_rated_set_after_rating():
    async with AsyncClient(app=app, base_url="http://test") as client:
        await client.post(f"/review/{TEST_SESSION}/rate", json={
            "user_id": TEST_USER, "card_key": "go_went", "rating": "good"
        })
    with Session(engine) as s:
        review = s.query(SessionReview).filter_by(session_id=TEST_SESSION).first()
    assert review.is_user_rated is True
```

运行：`pytest tests/test_step6.py -v`
全部 PASS 后打印 `✅ Step 6 完成`

---

## Step 7：复盘前端 UI

> 参考 SPEC_V02B.md 第三节

### 实现要求

1. 在前端「结束对话」按钮点击时，调用 `POST /chat/summary`
2. 显示加载状态 ⏳
3. 收到 `type="review"` 数据后，展示三层复盘卡片
4. 收到 `type="tip"` 时展示降级卡片
5. 点击「查看详情」展开错误详情
6. 👍 / 🔁 按钮调用 `POST /review/{session_id}/rate`
7. 亮点板块与错误板块严格分开展示

### 自测：Playwright e2e（tests/test_step7_e2e.py）

```python
import pytest
from playwright.sync_api import sync_playwright
import requests
import json

BASE_URL = "http://localhost:8000"
TEST_USER = "test_user_v02b_step7"
TEST_SESSION = "test_session_step7"

def seed_review():
    """直接往数据库插入一条含错误的 session_review，跳过真实 LLM"""
    from sqlalchemy.orm import Session
    from app.models.db import engine, SessionReview, GrammarCard
    from fsrs import Card

    with Session(engine) as s:
        s.query(SessionReview).filter_by(session_id=TEST_SESSION).delete()
        s.query(GrammarCard).filter_by(user_id=TEST_USER).delete()
        review = SessionReview(
            session_id=TEST_SESSION,
            user_id=TEST_USER,
            errors=json.dumps([{
                "key": "go_went",
                "original": "I go yesterday",
                "corrected": "I went yesterday",
                "explanation_zh": "go → went（不规则动词）",
                "count": 2, "confidence": 0.9
            }]),
            highlights=json.dumps([{
                "original": "The meeting totally threw me off",
                "praise_zh": "throw sb off 是很地道的口语！"
            }]),
            stats=json.dumps({"turns": 14, "duration_seconds": 480}),
        )
        s.add(review)
        gc = GrammarCard(
            user_id=TEST_USER, key="go_went",
            content="常用 go 代替 went",
            status="active", frequency=2,
            fsrs_card_data=json.dumps(Card().to_dict()),
        )
        s.add(gc)
        s.commit()

def cleanup():
    from sqlalchemy.orm import Session
    from app.models.db import engine, SessionReview, GrammarCard
    with Session(engine) as s:
        s.query(SessionReview).filter_by(session_id=TEST_SESSION).delete()
        s.query(GrammarCard).filter_by(user_id=TEST_USER).delete()
        s.commit()

@pytest.fixture(autouse=True)
def setup():
    seed_review()
    yield
    cleanup()

def test_review_card_renders(page):
    # 打开复盘页（带 session_id 参数，或通过 UI 导航）
    page.goto(f"{BASE_URL}/review?session_id={TEST_SESSION}&user_id={TEST_USER}")
    page.wait_for_selector("text=查看详情", timeout=10000)

    assert page.locator("text=今天聊了").count() > 0
    assert page.locator("text=可以改进").count() > 0

def test_error_detail_expandable(page):
    page.goto(f"{BASE_URL}/review?session_id={TEST_SESSION}&user_id={TEST_USER}")
    page.wait_for_selector("text=查看详情")
    page.click("text=查看详情")
    assert page.locator("text=I go yesterday").count() > 0
    assert page.locator("text=I went yesterday").count() > 0

def test_good_button_calls_api(page):
    page.goto(f"{BASE_URL}/review?session_id={TEST_SESSION}&user_id={TEST_USER}")
    page.wait_for_selector("text=查看详情")
    page.click("text=查看详情")
    with page.expect_response(lambda r: "/rate" in r.url) as resp_info:
        page.click("text=我记住了")
    assert resp_info.value.status == 200

def test_highlights_separate_from_errors(page):
    page.goto(f"{BASE_URL}/review?session_id={TEST_SESSION}&user_id={TEST_USER}")
    page.wait_for_selector("text=今天用得很地道")
    errors_section = page.locator("[data-section='errors']")
    highlights_section = page.locator("[data-section='highlights']")
    assert errors_section.count() > 0
    assert highlights_section.count() > 0
    # 两个 section 是兄弟元素，不嵌套
    assert errors_section.locator("text=throw sb off").count() == 0

def test_tip_fallback_renders(page):
    # 插入一条 type=tip 场景（用不存在的 session）
    page.goto(f"{BASE_URL}/review?session_id=nonexistent&user_id={TEST_USER}")
    page.wait_for_selector("text=今日一句", timeout=5000)
    assert page.locator("text=今日一句").count() > 0
```

运行：`pytest tests/test_step7_e2e.py -v`
全部 PASS 后打印 `✅ Step 7 完成`

---

## Step 8：点击提问 UI

> 参考 SPEC_V02B.md 第六节

### 实现要求

1. 每条 AI 气泡下方添加操作栏
2. 默认半透明，hover 时完全显示
3. 💬 按钮点击后，自动在输入框填入并发送：
   `Could you explain what you just said in simpler words?`
4. 携带完整 history 发送，Alex 能识别上下文

### 自测：Playwright e2e（tests/test_step8_e2e.py）

```python
import pytest
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8000"

def test_action_bar_visible_on_hover(page):
    page.goto(BASE_URL)
    # 触发一条 AI 回复
    page.fill("[data-testid='chat-input']", "Tell me something interesting.")
    page.click("[data-testid='send-button']")
    page.wait_for_selector("[data-testid='ai-bubble']")

    bubble = page.locator("[data-testid='ai-bubble']").first
    action_bar = page.locator("[data-testid='action-bar']").first

    # 默认半透明
    opacity_before = action_bar.evaluate("el => window.getComputedStyle(el).opacity")
    assert float(opacity_before) < 1.0

    bubble.hover()
    opacity_after = action_bar.evaluate("el => window.getComputedStyle(el).opacity")
    assert float(opacity_after) == 1.0

def test_explain_button_sends_message(page):
    page.goto(BASE_URL)
    page.fill("[data-testid='chat-input']", "The deadline is really looming.")
    page.click("[data-testid='send-button']")
    page.wait_for_selector("[data-testid='ai-bubble']")

    page.locator("[data-testid='ai-bubble']").first.hover()
    page.locator("[data-testid='explain-button']").first.click()

    # 自动发送
    page.wait_for_selector("[data-testid='ai-bubble']:nth-child(2)", timeout=10000)
    last_bubble = page.locator("[data-testid='ai-bubble']").last.inner_text()
    # Alex 的回复应比原句更简单（长度更长，解释性文字）
    assert len(last_bubble) > 10
```

运行：`pytest tests/test_step8_e2e.py -v`
全部 PASS 后打印 `✅ Step 8 完成`

---

## Step 9：全链路回归 + 汇报

### 执行

```bash
pip install pytest-asyncio playwright
playwright install chromium

# 启动服务（后台）
uvicorn app.main:app --reload &

# 全量回归
pytest tests/ -v --tb=short 2>&1 | tee test_report.txt
```

### 汇报格式

所有测试通过后，向 Human 输出以下报告：

```
## Speakeasy V0.2b 完成汇报

### 测试结果
✅ 通过：N 个用例
❌ 失败：0 个用例

### 各 Step 状态
- Step 1 环境 + 数据表        ✅
- Step 2 FSRS 记忆服务        ✅
- Step 3 对话分析服务         ✅
- Step 4 /chat/summary 升级   ✅
- Step 5 /chat 记忆注入       ✅
- Step 6 复盘查询 + 评分接口  ✅
- Step 7 复盘前端 UI          ✅
- Step 8 点击提问 UI          ✅

### 验收标准覆盖
- [ 已覆盖 ] POST /chat/summary 返回 type="review"
- [ 已覆盖 ] POST /chat/summary LLM 失败降级 type="tip"
- [ 已覆盖 ] GET /review/{session_id} 返回复盘数据
- [ 已覆盖 ] POST /review/{session_id}/rate 更新 FSRS
- [ 已覆盖 ] POST /chat system prompt 包含到期 grammar_cards

### 遗留问题
（如有则列出，无则填"无"）

### 待 Human 人工验收
- 复盘：错误展示正确，中文解释清晰
- 复盘：亮点独立，不与错误混排
- 复盘：👍/🔁 后下次复习时间正确更新
- 复盘：LLM 失败优雅降级
- 记忆：两次相同错误后，第三次对话 Alex 有针对性
- 点击提问：Alex 用简单语言重新解释
```

如果有测试未通过，**先自行修复，直到全绿，再汇报**。不提交带 FAIL 的报告。

---

## 附：关键路径速查

```
数据表          app/models/db.py
分析 Prompt     app/prompts/review.py
分析服务        app/services/review_service.py
记忆服务        app/services/memory_service.py
接口路由        app/routers/chat.py / review.py
前端复盘        frontend/src/components/ReviewCard.*
前端聊天气泡    frontend/src/components/ChatBubble.*
测试目录        tests/
规格文档        SPEC_V02B.md
```
