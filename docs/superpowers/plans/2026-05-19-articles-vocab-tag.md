# 文章学习 · 生词本自动入库 · 标签化 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `/practice` 重命名为 `/articles`「文章学习」，在解读发起时自动写入 vocabulary 占位记录，解读完成后回填 `explanation_json`；新增独立 `/vocabulary` 页支持来源标签筛选与卡片原地展开。

**Architecture:**
- 后端：新增 `vocab_service.update_explanation()` 专用回填函数（不复用 `save_item`，因后者已存在条目时不更新）；扩展 `ExplainRequest` / `StreamExplainRequest` 携带 `source_type` / `source_ref` / `item_type`；三个 explain 端点入口处先 `save_item` 占位（`explanation_json=None`）、流末尾/缓存命中后 `update_explanation` 回填；写入失败仅日志告警不影响解读。
- 前端：`/practice` → `/articles` 路由与组件改名，旧路径 `redirect`；删除 ExplanationModal 现有手动 saveToVocab 逻辑，调用 explain 时传源标签字段；新建 `Vocabulary.vue` 独立页（tag chip + 列表 + 卡片原地展开 + pending 自动重拉）。
- 文档：CLAUDE.md / README.md / 架构图同步；spec 已在 commit `1649e15` 与 issue [#42](https://github.com/bob798/speakeasy/issues/42) 中。

**Tech Stack:** Python · FastAPI · SQLAlchemy · pytest · Vue 3 · Pinia · Vite · Vitest

**Spec:** `docs/superpowers/specs/2026-05-19-articles-vocab-tag-design.md`

**Branch:** `feat/articles-vocab-tag`

---

## 阶段约定

- 测试 user_id 统一前缀：`test_user_v08_articles_<task>`
- 每个 task 完成 = 跑测试全 PASS + 一个独立 commit
- 仅 Mock LLM API（已有 fakes），不 Mock 内部 service
- 断言使用具体值（`assert x == "active"`），禁止 `assert x is not None` 模糊断言

---

### Task 1: vocab_service.update_explanation — 专用回填函数

> 不复用 `save_item`，因为 `save_item` 命中已存在记录时不更新任何字段（L77–83）。本函数语义：**默认仅在 explanation_json 为 NULL 时填入**；`force=True` 时强制覆盖（用于 refresh 路径）；软删条目也填，找不到记录静默 skip。

**Files:**
- Modify: `app/services/vocab_service.py:115`（在 `list_items` 之前插入）
- Test: `tests/test_v08_vocab_update_explanation.py`（新建）

- [ ] **Step 1: Write the failing test**

```python
# tests/test_v08_vocab_update_explanation.py
import pytest
from sqlalchemy.orm import Session as OrmSession
from app.models.db import engine, Vocabulary, init_db
from app.services.vocab_service import save_item, update_explanation

USER = "test_user_v08_articles_task1"


@pytest.fixture(autouse=True)
def _cleanup():
    init_db()
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_articles_%")).delete()
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_articles_%")).delete()
        s.commit()


def _seed(explanation_json=None, status="active"):
    item = save_item(
        user_id=USER, source_text="office banter",
        item_type="phrase", source_type="bbc_eaw", source_ref="ep-12",
        explanation_json=explanation_json,
    )
    if status == "deleted":
        with OrmSession(engine) as s:
            v = s.query(Vocabulary).filter_by(id=item["id"]).first()
            v.status = "deleted"
            s.commit()
    return item


def test_backfill_when_json_is_null():
    _seed(explanation_json=None)
    updated = update_explanation(
        user_id=USER, source_text="office banter", source_ref="ep-12",
        explanation_json='{"meaning": "办公室闲聊"}',
    )
    assert updated is True
    with OrmSession(engine) as s:
        v = s.query(Vocabulary).filter_by(user_id=USER, source_text="office banter").first()
        assert v.explanation_json == '{"meaning": "办公室闲聊"}'


def test_no_overwrite_when_json_already_set():
    _seed(explanation_json='{"meaning": "原值"}')
    updated = update_explanation(
        user_id=USER, source_text="office banter", source_ref="ep-12",
        explanation_json='{"meaning": "新值"}',
    )
    assert updated is False
    with OrmSession(engine) as s:
        v = s.query(Vocabulary).filter_by(user_id=USER, source_text="office banter").first()
        assert v.explanation_json == '{"meaning": "原值"}'


def test_force_overwrite_existing_json():
    """refresh=True 路径：必须能覆盖。"""
    _seed(explanation_json='{"meaning": "原值"}')
    updated = update_explanation(
        user_id=USER, source_text="office banter", source_ref="ep-12",
        explanation_json='{"meaning": "新值"}', force=True,
    )
    assert updated is True
    with OrmSession(engine) as s:
        v = s.query(Vocabulary).filter_by(user_id=USER, source_text="office banter").first()
        assert v.explanation_json == '{"meaning": "新值"}'


def test_backfill_works_on_deleted_record():
    _seed(explanation_json=None, status="deleted")
    updated = update_explanation(
        user_id=USER, source_text="office banter", source_ref="ep-12",
        explanation_json='{"meaning": "x"}',
    )
    assert updated is True


def test_record_not_found_returns_false():
    updated = update_explanation(
        user_id=USER, source_text="not-exists", source_ref="ep-99",
        explanation_json='{"meaning": "x"}',
    )
    assert updated is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_v08_vocab_update_explanation.py -v`
Expected: `ImportError: cannot import name 'update_explanation' from 'app.services.vocab_service'`

- [ ] **Step 3: Write minimal implementation**

在 `app/services/vocab_service.py` 第 115 行 `def list_items` 之前插入：

```python
def update_explanation(
    user_id: str,
    source_text: str,
    source_ref: Optional[str],
    explanation_json: str,
    force: bool = False,
) -> bool:
    """回填 explanation_json。

    默认仅在当前 explanation_json 为 NULL 时写入（保护已有解释不被首写覆盖）。
    force=True 时强制覆盖（用于 refresh=True 路径，用户主动重生）。
    软删条目也回填（保留历史，下次复活带完整数据）。
    找不到记录返回 False，不抛异常。
    """
    with OrmSession(engine) as s:
        v = (
            s.query(Vocabulary)
            .filter_by(user_id=user_id, source_text=source_text, source_ref=source_ref)
            .first()
        )
        if not v:
            logger.warning(
                "vocab_explanation_backfill_miss user_id=%s source_text=%s source_ref=%s",
                user_id, source_text, source_ref,
            )
            return False
        if v.explanation_json and not force:
            return False
        v.explanation_json = explanation_json
        s.commit()
        logger.info(
            "vocab_explanation_backfill user_id=%s id=%s len=%d force=%s",
            user_id, v.id, len(explanation_json), force,
        )
        return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_v08_vocab_update_explanation.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add app/services/vocab_service.py tests/test_v08_vocab_update_explanation.py
git commit -m "feat(vocab): add update_explanation for null-only backfill"
```

---

### Task 2: vocab_service.list_items 增加 source_type 过滤

**Files:**
- Modify: `app/services/vocab_service.py:116-135`
- Test: `tests/test_v08_vocab_list_by_source_type.py`（新建）

- [ ] **Step 1: Write the failing test**

```python
# tests/test_v08_vocab_list_by_source_type.py
import pytest
from sqlalchemy.orm import Session as OrmSession
from app.models.db import engine, Vocabulary, init_db
from app.services.vocab_service import save_item, list_items

USER = "test_user_v08_articles_task2"


@pytest.fixture(autouse=True)
def _cleanup():
    init_db()
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_articles_%")).delete()
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_articles_%")).delete()
        s.commit()


def test_filter_by_bbc_eaw_returns_only_bbc():
    save_item(user_id=USER, source_text="bbc word", item_type="word",
              source_type="bbc_eaw", source_ref="ep-1")
    save_item(user_id=USER, source_text="translate word", item_type="word",
              source_type="translate", source_ref=None)
    items = list_items(user_id=USER, source_type="bbc_eaw")
    assert len(items) == 1
    assert items[0]["source_text"] == "bbc word"


def test_no_filter_returns_all():
    save_item(user_id=USER, source_text="bbc word", item_type="word",
              source_type="bbc_eaw", source_ref="ep-1")
    save_item(user_id=USER, source_text="translate word", item_type="word",
              source_type="translate", source_ref=None)
    items = list_items(user_id=USER)
    assert len(items) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_v08_vocab_list_by_source_type.py -v`
Expected: `TypeError: list_items() got an unexpected keyword argument 'source_type'`

- [ ] **Step 3: Modify list_items signature and query**

替换 `app/services/vocab_service.py` 的 `list_items`（116–135 行）为：

```python
def list_items(
    user_id: str,
    item_type: Optional[str] = None,
    source_ref: Optional[str] = None,
    source_type: Optional[str] = None,
    due_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict]:
    with OrmSession(engine) as s:
        q = s.query(Vocabulary).filter_by(user_id=user_id, status="active")
        if item_type:
            q = q.filter_by(item_type=item_type)
        if source_ref:
            q = q.filter_by(source_ref=source_ref)
        if source_type:
            q = q.filter_by(source_type=source_type)
        rows = q.order_by(Vocabulary.created_at.desc()).all()

        items = [_to_dict(v) for v in rows]
        if due_only:
            items = [it for it in items if it["is_due"]]
        return items[offset : offset + limit]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_v08_vocab_list_by_source_type.py tests/test_v08_vocab_update_explanation.py -v`
Expected: 2 + 4 = 6 passed

- [ ] **Step 5: Commit**

```bash
git add app/services/vocab_service.py tests/test_v08_vocab_list_by_source_type.py
git commit -m "feat(vocab): list_items supports source_type filter"
```

---

### Task 3: GET /vocab 暴露 source_type query 参数

**Files:**
- Modify: `app/routers/vocab.py:62-79`
- Test: `tests/test_v08_vocab_router_source_type.py`（新建）

- [ ] **Step 1: Write the failing test**

```python
# tests/test_v08_vocab_router_source_type.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession
from main import app  # 项目入口在仓库根目录 main.py，不是 app/main.py
from app.models.db import engine, Vocabulary, init_db
from app.services.vocab_service import save_item
from app.routers.auth import get_current_user_id

USER = "test_user_v08_articles_task3"
client = TestClient(app)

app.dependency_overrides[get_current_user_id] = lambda: USER


@pytest.fixture(autouse=True)
def _cleanup():
    init_db()
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_articles_%")).delete()
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_articles_%")).delete()
        s.commit()


def test_get_vocab_with_source_type_bbc():
    save_item(user_id=USER, source_text="bbc", item_type="word", source_type="bbc_eaw", source_ref="ep-1")
    save_item(user_id=USER, source_text="trans", item_type="word", source_type="translate", source_ref=None)
    resp = client.get("/vocab?source_type=bbc_eaw")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["items"][0]["source_text"] == "bbc"


def test_get_vocab_no_source_type_returns_all():
    save_item(user_id=USER, source_text="bbc", item_type="word", source_type="bbc_eaw", source_ref="ep-1")
    save_item(user_id=USER, source_text="trans", item_type="word", source_type="translate", source_ref=None)
    resp = client.get("/vocab")
    assert resp.status_code == 200
    assert resp.json()["count"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_v08_vocab_router_source_type.py -v`
Expected: 第一个测试失败，因为 `/vocab?source_type=...` 不被路由识别

- [ ] **Step 3: Modify router**

替换 `app/routers/vocab.py` 的 `get_vocab`（L62–79）为：

```python
@router.get("/vocab")
async def get_vocab(
    user_id: str = Depends(get_current_user_id),
    item_type: Optional[str] = Query(None),
    source_ref: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None),
    due: bool = Query(False),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    items = list_items(
        user_id=user_id,
        item_type=item_type,
        source_ref=source_ref,
        source_type=source_type,
        due_only=due,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "count": len(items)}
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_v08_vocab_router_source_type.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add app/routers/vocab.py tests/test_v08_vocab_router_source_type.py
git commit -m "feat(vocab): GET /vocab supports source_type query param"
```

---

### Task 4: 扩展 ExplainRequest / StreamExplainRequest 携带源标签

**Files:**
- Modify: `app/routers/practice.py:77-81, 362-364`

> 仅做 schema 扩展，路由处理逻辑保持原样；新字段未传时为 None。本 task 不写新测试，由后续 Task 6/7/8 端到端测试覆盖（但要补一个 schema 反序列化测试避免 422）。

- [ ] **Step 1: Write the failing test**

```python
# tests/test_v08_explain_request_schema.py
from fastapi.testclient import TestClient
from main import app  # 项目入口在仓库根目录 main.py，不是 app/main.py
from app.routers.auth import get_current_user_id

USER = "test_user_v08_articles_task4"
client = TestClient(app)


@pytest.fixture(autouse=True)
def _override_user():
    """fixture-scoped dependency override，避免跨测试串用户。"""
    app.dependency_overrides[get_current_user_id] = lambda: USER
    yield
    app.dependency_overrides.pop(get_current_user_id, None)


def test_explain_request_accepts_source_fields():
    """直接实例化 model：扩展前缺字段会 AttributeError，扩展后 OK。"""
    from app.routers.practice import ExplainRequest
    req = ExplainRequest(
        text="Hello", kind="word", context="",
        source_type="bbc_eaw", source_ref="ep-1", item_type="word",
    )
    assert req.source_type == "bbc_eaw"
    assert req.source_ref == "ep-1"
    assert req.item_type == "word"


def test_stream_request_accepts_source_fields():
    from app.routers.practice import StreamExplainRequest
    req = StreamExplainRequest(
        text="Hello world.", source_type="bbc_eaw",
        source_ref="ep-1", item_type="sentence", context="paragraph context",
    )
    assert req.source_type == "bbc_eaw"
    assert req.context == "paragraph context"


def test_explain_request_omits_new_fields_defaults_none():
    """旧客户端不传新字段也应该正常解析。"""
    from app.routers.practice import ExplainRequest
    req = ExplainRequest(text="Hi", kind="word")
    assert req.source_type is None
    assert req.source_ref is None
    assert req.item_type is None
```

> 注：不能用 `assert resp.status_code != 422` 验证 schema 接受字段——Pydantic 默认 `extra="ignore"`，未知字段不会 422 而是被静默丢弃。必须直接实例化 model 断言字段存在。

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_v08_explain_request_schema.py -v`
Expected: `pydantic.ValidationError`（缺 source_type/source_ref/item_type/context 等字段时）或 `AttributeError`（model 上无此属性）

- [ ] **Step 3: Update schemas**

替换 `app/routers/practice.py:77-81` 的 `ExplainRequest` 为：

```python
class ExplainRequest(BaseModel):
    text: str
    kind: str                                # 'sentence' | 'word'
    context: Optional[str] = ""              # word 模式下可提供所在句子
    refresh: bool = False                    # V0.11 #8 · 跳过缓存强制重新生成
    # V0.8 自动入库：可选，传了就在解读入口自动写 vocabulary
    source_type: Optional[str] = None        # 'bbc_eaw' | 'translate' | ...
    source_ref: Optional[str] = None         # 例: BBC episode slug
    item_type: Optional[str] = None          # 'word' | 'phrase' | 'sentence'，缺省由 kind 推断
```

替换 `app/routers/practice.py:362-364` 的 `StreamExplainRequest` 为：

```python
class StreamExplainRequest(BaseModel):
    text: str
    refresh: bool = False                    # V0.11 #8
    # V0.8 自动入库
    source_type: Optional[str] = None
    source_ref: Optional[str] = None
    item_type: Optional[str] = None
    context: Optional[str] = ""              # 句子级 context（如所在段落）
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_v08_explain_request_schema.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/routers/practice.py tests/test_v08_explain_request_schema.py
git commit -m "feat(explain): request schemas accept optional source fields"
```

---

### Task 5: 抽取 `_auto_save_vocab` 工具函数 + `_resolve_item_type` 推断

> 三个 explain 端点要复用同一段"占位写入 vocabulary"逻辑，集中到一个工具函数；写入失败仅日志，不向上抛。

**Files:**
- Modify: `app/routers/practice.py`（在 `practice_explain` 函数之前插入工具函数）
- Test: `tests/test_v08_auto_save_vocab.py`（新建）

- [ ] **Step 1: Write the failing test**

```python
# tests/test_v08_auto_save_vocab.py
import pytest
from sqlalchemy.orm import Session as OrmSession
from app.models.db import engine, Vocabulary, init_db
from app.routers.practice import _auto_save_vocab, _resolve_item_type

USER = "test_user_v08_articles_task5"


@pytest.fixture(autouse=True)
def _cleanup():
    init_db()
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_articles_%")).delete()
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_articles_%")).delete()
        s.commit()


def test_resolve_item_type_explicit_wins():
    assert _resolve_item_type(text="Hello world", explicit="phrase", kind="sentence") == "phrase"


def test_resolve_item_type_falls_back_to_kind():
    assert _resolve_item_type(text="Hello", explicit=None, kind="word") == "word"
    assert _resolve_item_type(text="Hello world.", explicit=None, kind="sentence") == "sentence"


def test_resolve_item_type_word_kind_multi_token_becomes_phrase():
    assert _resolve_item_type(text="rocket science", explicit=None, kind="word") == "phrase"


def test_auto_save_writes_pending_record():
    ok = _auto_save_vocab(
        user_id=USER, text="office banter", context="Some context.",
        source_type="bbc_eaw", source_ref="ep-12", item_type="phrase",
    )
    assert ok is True
    with OrmSession(engine) as s:
        v = s.query(Vocabulary).filter_by(user_id=USER, source_text="office banter").first()
        assert v is not None
        assert v.source_type == "bbc_eaw"
        assert v.source_ref == "ep-12"
        assert v.item_type == "phrase"
        assert v.explanation_json is None
        assert v.status == "active"


def test_auto_save_no_source_type_is_noop():
    ok = _auto_save_vocab(
        user_id=USER, text="x", context="", source_type=None, source_ref=None, item_type="word",
    )
    assert ok is False
    with OrmSession(engine) as s:
        cnt = s.query(Vocabulary).filter_by(user_id=USER).count()
        assert cnt == 0


def test_auto_save_no_user_id_is_noop():
    """匿名场景（phonetic 端点未登录）安全跳过。"""
    ok = _auto_save_vocab(
        user_id=None, text="x", context="", source_type="bbc_eaw",
        source_ref="ep-1", item_type="word",
    )
    assert ok is False


def test_auto_save_failure_does_not_raise(monkeypatch):
    """vocab_service.save_item 抛错时，_auto_save_vocab 应吞掉并返回 False。"""
    from app.services import vocab_service as vs

    def _raise(**kwargs):
        raise RuntimeError("db locked")

    monkeypatch.setattr(vs, "save_item", _raise)
    ok = _auto_save_vocab(
        user_id=USER, text="x", context="", source_type="bbc_eaw",
        source_ref="ep-1", item_type="word",
    )
    assert ok is False  # 异常被吞，返回 False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_v08_auto_save_vocab.py -v`
Expected: `ImportError: cannot import name '_auto_save_vocab' from 'app.routers.practice'`

- [ ] **Step 3: Add utility functions in `app/routers/practice.py`**

在 `app/routers/practice.py` 文件顶部 import 区之后，找到 `# ── 句子/单词解读 ─` 标题（约 L327）之前插入：

```python
from app.services import vocab_service as _vocab_service


def _resolve_item_type(text: str, explicit: Optional[str], kind: str) -> str:
    """优先显式 item_type，否则按 kind 推断；word 多 token 视作 phrase。"""
    if explicit in ("word", "phrase", "sentence"):
        return explicit
    if kind == "word":
        tokens = (text or "").strip().split()
        return "word" if len(tokens) <= 1 else "phrase"
    return "sentence"


def _auto_save_vocab(
    user_id: Optional[str],
    text: str,
    context: Optional[str],
    source_type: Optional[str],
    source_ref: Optional[str],
    item_type: str,
) -> bool:
    """解读发起时占位写入 vocabulary（explanation_json=None）。

    跳过条件：未登录 / 未提供 source_type / text 为空。
    写入失败：logger.warning，绝不向上抛。
    """
    if not user_id or not source_type or not text or not text.strip():
        return False
    try:
        _vocab_service.save_item(
            user_id=user_id,
            source_text=text,
            translated_text="",
            direction="en2zh",
            context=context or None,
            item_type=item_type,
            source_type=source_type,
            source_ref=source_ref,
            explanation_json=None,
        )
        logger.info(
            "vocab_auto_save_attempt user_id=%s text=%s source_type=%s source_ref=%s item_type=%s",
            user_id, text[:40], source_type, source_ref, item_type,
        )
        return True
    except Exception as e:
        logger.warning(
            "vocab_auto_save_failed user_id=%s text=%s err=%s",
            user_id, text[:40], e,
        )
        return False
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_v08_auto_save_vocab.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add app/routers/practice.py tests/test_v08_auto_save_vocab.py
git commit -m "feat(explain): add _auto_save_vocab + _resolve_item_type helpers"
```

---

### Task 6: `/practice/explain` (同步) 接入自动入库 + 回填

**Files:**
- Modify: `app/routers/practice.py:329-347`
- Test: `tests/test_v08_explain_autosave.py`（新建）

- [ ] **Step 1: Write the failing test**

```python
# tests/test_v08_explain_autosave.py
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession
from main import app  # 项目入口在仓库根目录 main.py，不是 app/main.py
from app.models.db import engine, Vocabulary, init_db
from app.routers.auth import get_current_user_id

USER = "test_user_v08_articles_task6"
client = TestClient(app)


@pytest.fixture(autouse=True)
def _override_user():
    """fixture-scoped dependency override，避免跨测试串用户。"""
    app.dependency_overrides[get_current_user_id] = lambda: USER
    yield
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture(autouse=True)
def _cleanup():
    init_db()
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_articles_%")).delete()
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_articles_%")).delete()
        s.commit()


@pytest.fixture
def stub_explain(monkeypatch):
    """避免真实 LLM 调用。"""
    from app.services import explain_service

    async def _fake(text, kind, user_id, context="", force=False):
        return {"explanation": {"meaning": "stub-" + text}, "cefr_level": "B1", "cached": False}

    monkeypatch.setattr(explain_service, "explain_text", _fake)
    # 也替换路由直接 import 的那个引用
    import app.routers.practice as pr
    monkeypatch.setattr(pr, "explain_text", _fake)


def test_explain_with_source_creates_pending_then_backfills(stub_explain):
    body = {
        "text": "office banter", "kind": "word",
        "source_type": "bbc_eaw", "source_ref": "ep-12", "item_type": "phrase",
    }
    resp = client.post("/practice/explain", json=body)
    assert resp.status_code == 200
    with OrmSession(engine) as s:
        v = s.query(Vocabulary).filter_by(user_id=USER, source_text="office banter").first()
        assert v is not None
        # 回填应在响应返回前完成
        assert v.explanation_json is not None
        assert json.loads(v.explanation_json)["meaning"] == "stub-office banter"


def test_explain_without_source_no_vocab(stub_explain):
    body = {"text": "hello", "kind": "word"}
    resp = client.post("/practice/explain", json=body)
    assert resp.status_code == 200
    with OrmSession(engine) as s:
        cnt = s.query(Vocabulary).filter_by(user_id=USER).count()
        assert cnt == 0


def test_explain_refresh_overwrites_existing_json(stub_explain):
    """refresh=True 路径：已有 explanation_json 应被新值覆盖。"""
    from app.services.vocab_service import save_item
    save_item(
        user_id=USER, source_text="重写测试", item_type="word",
        source_type="bbc_eaw", source_ref="ep-1",
        explanation_json='{"meaning": "旧值"}',
    )
    body = {
        "text": "重写测试", "kind": "word", "refresh": True,
        "source_type": "bbc_eaw", "source_ref": "ep-1", "item_type": "word",
    }
    resp = client.post("/practice/explain", json=body)
    assert resp.status_code == 200
    with OrmSession(engine) as s:
        v = s.query(Vocabulary).filter_by(user_id=USER, source_text="重写测试").first()
        assert json.loads(v.explanation_json)["meaning"] == "stub-重写测试"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_v08_explain_autosave.py -v`
Expected: 第一个失败（vocabulary 中无记录）

- [ ] **Step 3: Modify `/practice/explain` handler**

替换 `app/routers/practice.py:329-347` 的 `practice_explain` 为：

```python
@router.post("/practice/explain")
async def practice_explain(
    req: ExplainRequest,
    user_id: str = Depends(get_current_user_id),
):
    # 入口占位写入
    item_type = _resolve_item_type(req.text, req.item_type, req.kind)
    _auto_save_vocab(
        user_id=user_id, text=req.text, context=req.context,
        source_type=req.source_type, source_ref=req.source_ref,
        item_type=item_type,
    )

    try:
        result = await explain_text(
            text=req.text,
            kind=req.kind,
            user_id=user_id,
            context=req.context or "",
            force=req.refresh,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("解读失败: %s", e, exc_info=True)
        raise HTTPException(503, "解读服务暂时不可用，请稍后重试")

    # 解读完成回填（refresh=True 时 force-overwrite，否则仅 NULL 写入）
    if req.source_type and result.get("explanation"):
        try:
            _vocab_service.update_explanation(
                user_id=user_id,
                source_text=req.text,
                source_ref=req.source_ref,
                explanation_json=json.dumps(result["explanation"], ensure_ascii=False),
                force=req.refresh,
            )
        except Exception as e:
            logger.warning("vocab_backfill_failed user_id=%s err=%s", user_id, e)

    return result
```

并在文件顶部确认有 `import json`（如果没有，加上）。

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_v08_explain_autosave.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/routers/practice.py tests/test_v08_explain_autosave.py
git commit -m "feat(explain): /practice/explain auto-saves vocab + backfills explanation"
```

---

### Task 7: `/practice/explain/phonetic` 注入 user_id + 自动入库

> 现状该端点为公开接口，没有 user_id。改为可选 user_id 依赖：登录态触发入库（仅占位、不回填，因为 phonetic 不产生完整 explanation_json）；匿名仍可访问。
>
> ⚠️ **复用现有依赖**：`app/routers/auth.py:73` 已有 `get_current_user_id_optional`，直接 import 使用，**不要**新建 `get_current_user_id_optional` 之类的重复函数。

**Files:**
- Modify: `app/routers/practice.py:350-359`
- Test: `tests/test_v08_phonetic_autosave.py`（新建）

- [ ] **Step 1: Confirm existing optional auth dependency**

Run: `grep -n "get_current_user_id_optional" app/routers/auth.py`

预期：在 line 73 附近找到 `async def get_current_user_id_optional(...)`。继续下一步。

- [ ] **Step 2: Write the failing test**

```python
# tests/test_v08_phonetic_autosave.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession
from main import app  # 项目入口在仓库根目录 main.py，不是 app/main.py
from app.models.db import engine, Vocabulary, init_db
from app.routers.auth import get_current_user_id_optional  # 或现有 optional 依赖

USER = "test_user_v08_articles_task7"
client = TestClient(app)


@pytest.fixture(autouse=True)
def _cleanup():
    init_db()
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_articles_%")).delete()
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_articles_%")).delete()
        s.commit()


def test_phonetic_logged_in_with_source_creates_pending():
    app.dependency_overrides[get_current_user_id_optional] = lambda: USER
    try:
        body = {"text": "office", "source_type": "bbc_eaw", "source_ref": "ep-12", "item_type": "word"}
        resp = client.post("/practice/explain/phonetic", json=body)
        assert resp.status_code == 200
        with OrmSession(engine) as s:
            v = s.query(Vocabulary).filter_by(user_id=USER, source_text="office").first()
            assert v is not None, "phonetic 端点应已写入 vocabulary 占位"
            assert v.explanation_json is None  # phonetic 不回填
            assert v.source_type == "bbc_eaw"
            assert v.item_type == "word"
    finally:
        app.dependency_overrides.pop(get_current_user_id_optional, None)


def test_phonetic_anonymous_still_returns_ipa_no_vocab():
    app.dependency_overrides[get_current_user_id_optional] = lambda: None
    try:
        body = {"text": "office", "source_type": "bbc_eaw", "source_ref": "ep-12", "item_type": "word"}
        resp = client.post("/practice/explain/phonetic", json=body)
        assert resp.status_code == 200
        with OrmSession(engine) as s:
            cnt = s.query(Vocabulary).filter_by(source_text="office").count()
            assert cnt == 0
    finally:
        app.dependency_overrides.pop(get_current_user_id_optional, None)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_v08_phonetic_autosave.py -v`
Expected: 第一个 test 失败（vocabulary 中无记录），因为 phonetic 端点尚未注入 user_id 也未触发入库

- [ ] **Step 4: Modify phonetic endpoint**

替换 `app/routers/practice.py:350-359` 为：

```python
class QuickPhoneticRequest(BaseModel):
    text: str
    source_type: Optional[str] = None
    source_ref: Optional[str] = None
    item_type: Optional[str] = None         # 前端推断后传入，避免与后续 explain 不一致


@router.post("/practice/explain/phonetic")
async def practice_explain_phonetic(
    req: QuickPhoneticRequest,
    user_id: Optional[str] = Depends(get_current_user_id_optional),
):
    """单词 IPA 本地秒出；未知词 phonetic=null，前端退回等 LLM 结果。"""
    if not req.text or not req.text.strip():
        raise HTTPException(400, "text is required")
    # 登录态 + 带 source 时占位入库；phonetic 不产生完整解读，不回填
    if user_id and req.source_type:
        # 注意：必须用前端传来的 item_type；前端在 ExplanationModal 入口处一次推断。
        # 若前端没传，按 word kind 推断（多 token 视作 phrase），与后续 explain 行为一致。
        item_type = _resolve_item_type(req.text, req.item_type, "word")
        _auto_save_vocab(
            user_id=user_id, text=req.text, context=None,
            source_type=req.source_type, source_ref=req.source_ref,
            item_type=item_type,
        )
    return {"phonetic": quick_phonetic(req.text)}
```

确保 `get_current_user_id_optional` 已 import：在 import 块加 `from app.routers.auth import get_current_user_id, get_current_user_id_optional`。

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_v08_phonetic_autosave.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add app/routers/practice.py tests/test_v08_phonetic_autosave.py
git commit -m "feat(explain): phonetic endpoint auto-saves vocab when logged-in"
```

---

### Task 8: `/practice/explain/stream` 接入自动入库 + 流末尾回填

> 路由入口处占位；流末尾 `_done` 事件之前根据收集到的字段拼 `explanation_json` 并回填。

**Files:**
- Modify: `app/routers/practice.py:367-395`
- Test: `tests/test_v08_explain_stream_autosave.py`（新建）

- [ ] **Step 1: Write the failing test**

```python
# tests/test_v08_explain_stream_autosave.py
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession
from main import app  # 项目入口在仓库根目录 main.py，不是 app/main.py
from app.models.db import engine, Vocabulary, init_db
from app.routers.auth import get_current_user_id

USER = "test_user_v08_articles_task8"
client = TestClient(app)


@pytest.fixture(autouse=True)
def _override_user():
    """fixture-scoped dependency override，避免跨测试串用户。"""
    app.dependency_overrides[get_current_user_id] = lambda: USER
    yield
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture(autouse=True)
def _cleanup():
    init_db()
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_articles_%")).delete()
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_articles_%")).delete()
        s.commit()


@pytest.fixture
def stub_stream(monkeypatch):
    """伪造流式：返回 field/value 事件，最后 _done。"""
    async def _fake(text, user_id, force=False):
        yield json.dumps({"field": "meaning", "value": "办公室闲聊"}, ensure_ascii=False)
        yield json.dumps({"field": "grammar", "value": "名词短语"}, ensure_ascii=False)
        yield json.dumps({"_done": True, "cefr_level": "B1"}, ensure_ascii=False)

    import app.routers.practice as pr
    monkeypatch.setattr(pr, "stream_sentence_explanation", _fake)


def test_stream_writes_pending_at_entry_and_backfills_on_done(stub_stream):
    body = {
        "text": "office banter exists", "source_type": "bbc_eaw",
        "source_ref": "ep-12", "item_type": "sentence", "context": "in the meeting",
    }
    with client.stream("POST", "/practice/explain/stream", json=body) as resp:
        assert resp.status_code == 200
        # 强制消费完整流
        chunks = list(resp.iter_lines())
    assert any('"_done"' in c for c in chunks)
    with OrmSession(engine) as s:
        v = s.query(Vocabulary).filter_by(user_id=USER, source_text="office banter exists").first()
        assert v is not None
        assert v.source_type == "bbc_eaw"
        assert v.item_type == "sentence"
        parsed = json.loads(v.explanation_json)
        assert parsed["meaning"] == "办公室闲聊"
        assert parsed["grammar"] == "名词短语"


def test_stream_cache_hit_backfills(monkeypatch):
    async def _fake_cached(text, user_id, force=False):
        yield json.dumps({
            "_cached": True, "cefr_level": "B1",
            "explanation": {"meaning": "cached"},
        }, ensure_ascii=False)
        yield json.dumps({"_done": True}, ensure_ascii=False)

    import app.routers.practice as pr
    monkeypatch.setattr(pr, "stream_sentence_explanation", _fake_cached)

    body = {"text": "cached text", "source_type": "bbc_eaw", "source_ref": "ep-1", "item_type": "sentence"}
    with client.stream("POST", "/practice/explain/stream", json=body) as resp:
        list(resp.iter_lines())
    with OrmSession(engine) as s:
        v = s.query(Vocabulary).filter_by(user_id=USER, source_text="cached text").first()
        assert v is not None
        assert json.loads(v.explanation_json)["meaning"] == "cached"


def test_stream_without_source_no_vocab(stub_stream):
    body = {"text": "no source"}
    with client.stream("POST", "/practice/explain/stream", json=body) as resp:
        list(resp.iter_lines())
    with OrmSession(engine) as s:
        cnt = s.query(Vocabulary).filter_by(user_id=USER, source_text="no source").count()
        assert cnt == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_v08_explain_stream_autosave.py -v`
Expected: 3 failures（vocabulary 中无记录）

- [ ] **Step 3: Modify stream handler**

替换 `app/routers/practice.py:367-395` 为：

```python
@router.post("/practice/explain/stream")
async def practice_explain_stream(
    req: StreamExplainRequest,
    user_id: str = Depends(get_current_user_id),
):
    """句子解读流式接口（NDJSON，每行一个 JSON 事件）。

    事件形式：
      {"field": "...", "value": ...}
      {"_cached": true, "cefr_level": "B1", "explanation": {...}}     # 缓存命中
      {"_done": true, "cefr_level": "B1"}                              # 流结束
      {"_error": "..."}                                                # 错误
    """
    if not req.text or not req.text.strip():
        raise HTTPException(400, "text is required")

    # 入口占位写入
    item_type = _resolve_item_type(req.text, req.item_type, "sentence")
    _auto_save_vocab(
        user_id=user_id, text=req.text, context=req.context,
        source_type=req.source_type, source_ref=req.source_ref,
        item_type=item_type,
    )

    async def event_stream():
        collected: dict = {}
        try:
            async for line in stream_sentence_explanation(req.text, user_id, force=req.refresh):
                # 解析事件以便收集 explanation 字段（同时透传 line 给前端）
                try:
                    evt = json.loads(line)
                except Exception:
                    evt = None
                if isinstance(evt, dict):
                    if evt.get("_cached") and isinstance(evt.get("explanation"), dict):
                        collected = dict(evt["explanation"])
                    elif "field" in evt and "value" in evt:
                        collected[evt["field"]] = evt["value"]
                yield line + "\n"
        except ValueError as e:
            yield json.dumps({"_error": str(e)}, ensure_ascii=False) + "\n"
            return
        except Exception as e:
            logger.error("stream 解读失败: %s", e, exc_info=True)
            yield json.dumps({"_error": "解读服务暂时不可用"}, ensure_ascii=False) + "\n"
            return

        # 流末尾回填（best-effort）：
        # · 如果客户端中途断开，Starlette 抛 ClientDisconnect → generator 不会到这里
        #   → pending 留存，由前端 /vocabulary 重拉路径兜底（这是 by design）
        # · refresh=True 时 force-overwrite 已有 explanation_json
        if req.source_type and collected:
            try:
                _vocab_service.update_explanation(
                    user_id=user_id,
                    source_text=req.text,
                    source_ref=req.source_ref,
                    explanation_json=json.dumps(collected, ensure_ascii=False),
                    force=req.refresh,
                )
            except Exception as e:
                logger.warning("vocab_stream_backfill_failed user_id=%s err=%s", user_id, e)

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_v08_explain_stream_autosave.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/routers/practice.py tests/test_v08_explain_stream_autosave.py
git commit -m "feat(explain): /practice/explain/stream auto-saves + backfills on done"
```

---

### Task 9: 后端路由 prefix 改名 + `/practice/*` alias

> 文件改名 `practice.py` → `articles.py`，模块同时挂在 `/articles` 和 `/practice` 两个 prefix 下（同一 router，include 两次）。三个 explain 端点的内部装饰器 `@router.post("/practice/explain")` 也要相应改为 `@router.post("/explain")` 等，统一在 include 时加 prefix。

**Files:**
- Rename: `app/routers/practice.py` → `app/routers/articles.py`（git mv）
- Modify: `app/routers/articles.py`（新名）—— 把所有 `@router.post("/practice/...")` 装饰器中的 `/practice` 前缀剥离
- Modify: `app/main.py` —— `include_router` 改用新模块，注册两次（`/articles` 主、 `/practice` alias）
- Test: `tests/test_v08_route_alias.py`（新建）

- [ ] **Step 1: Write the failing test**

```python
# tests/test_v08_route_alias.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession
from main import app  # 项目入口在仓库根目录 main.py，不是 app/main.py
from app.models.db import engine, Vocabulary, init_db
from app.routers.auth import get_current_user_id

USER = "test_user_v08_articles_task9"
client = TestClient(app)


@pytest.fixture(autouse=True)
def _override_user():
    """fixture-scoped dependency override，避免跨测试串用户。"""
    app.dependency_overrides[get_current_user_id] = lambda: USER
    yield
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture(autouse=True)
def _cleanup():
    init_db()
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_articles_%")).delete()
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_articles_%")).delete()
        s.commit()


@pytest.fixture
def stub(monkeypatch):
    async def _fake_explain(text, kind, user_id, context="", force=False):
        return {"explanation": {"meaning": "x"}, "cefr_level": "B1", "cached": False}
    import app.routers.articles as ar
    monkeypatch.setattr(ar, "explain_text", _fake_explain)


def test_articles_explain_works(stub):
    resp = client.post("/articles/explain", json={"text": "hi", "kind": "word"})
    assert resp.status_code == 200


def test_practice_alias_still_works(stub):
    resp = client.post("/practice/explain", json={"text": "hi", "kind": "word"})
    assert resp.status_code == 200


def test_articles_phonetic_works():
    resp = client.post("/articles/explain/phonetic", json={"text": "office"})
    assert resp.status_code == 200


def test_practice_phonetic_alias_works():
    resp = client.post("/practice/explain/phonetic", json={"text": "office"})
    assert resp.status_code == 200


def test_articles_due_works():
    """非 explain 端点也得跟着改名（不只是 explain 这 3 个）。"""
    resp = client.get("/articles/due")
    # 200 或 401 都算路由挂上；404 = 没挂上
    assert resp.status_code != 404


def test_articles_subtitles_works():
    """sample 抽查另一组端点。"""
    resp = client.post("/articles/subtitles", json={"video_url": ""})
    assert resp.status_code != 404


def test_openapi_no_duplicate_practice_paths():
    """alias 注册需 include_in_schema=False，防止 OpenAPI 出现两套同名接口。"""
    schema = client.get("/openapi.json").json()
    paths = list(schema.get("paths", {}).keys())
    practice_paths = [p for p in paths if p.startswith("/practice")]
    assert practice_paths == [], f"OpenAPI 不应暴露 /practice/* 别名: {practice_paths}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_v08_route_alias.py -v`
Expected: `/articles/*` 全部 404（路由未挂）

- [ ] **Step 3: Rename router file**

```bash
git mv app/routers/practice.py app/routers/articles.py
```

- [ ] **Step 4: Strip `/practice` prefix from ALL in-file decorators**

`practice.py` 有 13 个端点（用前面 Task 改完的版本为准），不只 explain 三个。先 grep 列出全部：

```bash
grep -nE '^@router\.' app/routers/articles.py
```

预期看到类似：

```
@router.post("/practice/subtitles")
@router.get("/practice/subtitles")
@router.get("/practice/subtitles/{source_id}")
@router.post("/practice/sources/import", status_code=201)
@router.post("/practice/cards", status_code=201)
@router.get("/practice/cards")
@router.post("/practice/cards/{card_id}/review")
@router.delete("/practice/cards/{card_id}")
@router.get("/practice/due")
@router.post("/practice/explain")
@router.post("/practice/explain/phonetic")
@router.post("/practice/explain/stream")
@router.post("/practice/tts")
```

**全部**把装饰器内的 `/practice` 前缀剥掉（保留后续路径段）。例：

| 旧 | 新 |
|---|---|
| `@router.post("/practice/subtitles")` | `@router.post("/subtitles")` |
| `@router.get("/practice/subtitles/{source_id}")` | `@router.get("/subtitles/{source_id}")` |
| `@router.post("/practice/sources/import", status_code=201)` | `@router.post("/sources/import", status_code=201)` |
| `@router.post("/practice/cards", status_code=201)` | `@router.post("/cards", status_code=201)` |
| `@router.get("/practice/cards")` | `@router.get("/cards")` |
| `@router.post("/practice/cards/{card_id}/review")` | `@router.post("/cards/{card_id}/review")` |
| `@router.delete("/practice/cards/{card_id}")` | `@router.delete("/cards/{card_id}")` |
| `@router.get("/practice/due")` | `@router.get("/due")` |
| `@router.post("/practice/explain")` | `@router.post("/explain")` |
| `@router.post("/practice/explain/phonetic")` | `@router.post("/explain/phonetic")` |
| `@router.post("/practice/explain/stream")` | `@router.post("/explain/stream")` |
| `@router.post("/practice/tts")` | `@router.post("/tts")` |

> 验证：`grep -nE '^@router\..*"/practice' app/routers/articles.py` 应为 0 结果。

- [ ] **Step 5: Update main.py registration（项目根目录的 main.py，不是 app/main.py）**

修改根目录 `main.py`：

```python
# 旧（约 line 14）
from app.routers.practice import router as practice_router
# 新
from app.routers.articles import router as articles_router

# 旧（约 line 91）
app.include_router(practice_router)
# 新
app.include_router(articles_router, prefix="/articles")
app.include_router(articles_router, prefix="/practice", include_in_schema=False)
# ↑ alias，include_in_schema=False 防止 OpenAPI 重复条目；1–2 个版本后移除
```

并把 `API_PREFIXES`（main.py:38）补 `"articles/"`：

```python
# 旧
API_PREFIXES = (
    "api/",
    ...
    "practice/",
    ...
)
# 新（保留 "practice/"，新增 "articles/"）
API_PREFIXES = (
    "api/",
    ...
    "practice/",
    "articles/",
    ...
)
```

- [ ] **Step 6: Update existing imports referencing app.routers.practice**

Run: `grep -rn "from app.routers.practice\|app\.routers\.practice" tests/ app/ frontend/ 2>/dev/null`

把 `app.routers.practice` 全部替换为 `app.routers.articles`（包括前面 Task 5–8 刚创建的测试中的 `import app.routers.practice as pr`）。注意：

- 这一步要**逐个文件 Edit**，不要全局 sed（避免改到字符串/注释里的偶然匹配）
- 也要 grep `app/routers/practice` 看是否有 fixture/conftest 引用文件路径

- [ ] **Step 7: Run all V0.8 tests**

Run: `pytest tests/test_v08_*.py -v`
Expected: 全部 passed（包括 OpenAPI 不重复的断言）

- [ ] **Step 8: Manual sanity check**

启动 uvicorn 跑两条 curl：

```bash
curl -s http://localhost:8000/articles/explain/phonetic -H 'Content-Type: application/json' -d '{"text":"office"}'
curl -s http://localhost:8000/practice/explain/phonetic -H 'Content-Type: application/json' -d '{"text":"office"}'
```

两个应该返回相同内容。

访问 `http://localhost:8000/openapi.json | jq '.paths | keys[] | select(startswith("/practice"))'` 应为空。

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(articles): rename practice→articles router (all 13 endpoints), keep /practice alias hidden from OpenAPI"
```

---

### Task 10: 前端 — Vue Router 改名 + `/practice` redirect + 新增 `/vocabulary`

**Files:**
- Modify: `frontend/src/router/index.js`
- Rename: `frontend/src/views/Practice.vue` → `frontend/src/views/Articles.vue`
- Create: `frontend/src/views/Vocabulary.vue`（先放空骨架，下个 task 填充）

- [ ] **Step 1: Rename view file**

```bash
cd frontend
git mv src/views/Practice.vue src/views/Articles.vue
cd ..
```

- [ ] **Step 2: Create Vocabulary.vue skeleton**

新建 `frontend/src/views/Vocabulary.vue`：

```vue
<template>
  <div class="vocabulary-page">
    <h1>我的生词本</h1>
    <p>TODO Task 11+ 填充列表与 tag chip</p>
  </div>
</template>

<script setup>
// Task 11+ 实现
</script>

<style scoped>
.vocabulary-page { padding: 16px; }
</style>
```

- [ ] **Step 3: Update router/index.js**

打开 `frontend/src/router/index.js`，在路由表中（L18–64）做以下改动：

```javascript
// 旧
{
  path: '/practice',
  name: 'Practice',
  component: () => import('@/views/Practice.vue'),
  meta: { requiresAuth: true },
},

// 新
{
  path: '/articles',
  name: 'Articles',
  component: () => import('@/views/Articles.vue'),
  meta: { requiresAuth: true },
},
{
  path: '/practice',
  redirect: '/articles',
},
{
  path: '/vocabulary',
  name: 'Vocabulary',
  component: () => import('@/views/Vocabulary.vue'),
  meta: { requiresAuth: true },
},
```

- [ ] **Step 4: Add API.ARTICLES constant in frontend/src/config.js**

`API` 常量定义在 `frontend/src/config.js`（L6 起的 `export const API = {...}`）。打开后追加一条：

```javascript
export const API = {
  BASE: '',
  ...
  PRACTICE: '/practice',
  ARTICLES: '/articles',  // V0.8：文章学习模块新名；后端 /practice/* alias 仍在
  ...
}
```

保留 `PRACTICE`（后端 alias 兜底，老调用不需要立刻全改）；下面所有 task 的新代码一律用 `API.ARTICLES`。

- [ ] **Step 5: Run frontend test suite**

Run:
```bash
cd frontend && npm run test 2>&1 | tail -30
```
Expected: 现有测试不应回归（路由变更不影响组件测试）

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(frontend): rename /practice→/articles, add /vocabulary route + API.ARTICLES const"
```

---

### Task 11: Articles.vue 文案更新 + 导航菜单文案

**Files:**
- Modify: `frontend/src/views/Articles.vue`（标题、副标题）
- Modify: `frontend/src/views/Home.vue` 或对应导航组件
- Modify: 任何硬编码 "发音练习" 字样的位置

- [ ] **Step 1: Find all "发音练习" occurrences**

Run: `grep -rn "发音练习" frontend/src/ | grep -v node_modules`

- [ ] **Step 2: Replace strings**

对 grep 出的每个位置：

- 主标题位置（应在 `Articles.vue` 顶部）→ 改为 `文章学习`
- 在 `Articles.vue` 主标题下方加副标题 `BBC English at Work`（如组件结构允许；如不允许就跳过本步，记入 follow-up）
- 导航 / 菜单卡片：`发音练习` → `文章学习`
- README / 其他 markdown 在此 task 不动（Task 18 集中处理文档）

- [ ] **Step 3: Verify in browser**

启动 dev server 手动验证：

```bash
cd frontend && npm run dev
```

访问：
- `http://localhost:5173/articles` → 标题显示「文章学习」
- `http://localhost:5173/practice` → 自动跳到 `/articles`
- 主页 / 导航 → 看到「文章学习」字样

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(frontend): rebrand practice→文章学习 across views & nav"
```

---

### Task 12: ExplanationModal 调用 explain* 时传源标签字段 + 删除手动 saveToVocab

> 让后端自动入库接管；删除模板中的"加入生词本"按钮、`starState` 状态、`saveToVocab` 函数。`deriveVocabSource()` 保留，但只用来给 explain 请求拼字段。

**Files:**
- Modify: `frontend/src/components/ExplanationModal.vue`

- [ ] **Step 1: 在 ExplanationModal.vue 入口处一次性推断 `item_type`**

⚠️ Critical 修复点（C5）：phonetic 与 explain 调用**必须共用同一个 item_type**，否则同一短语先 phonetic（写成 word）后 explain（应该写成 phrase）会让 vocabulary 永久错存为 word（save_item 命中已存在不更新字段）。

在 `frontend/src/components/ExplanationModal.vue` 的 `<script setup>` 顶部、`fetchWord` / `fetchSentence` 共用范围内，加：

```javascript
import { computed } from 'vue'

// item_type 全组件一致：word 单 token = word；word 多 token = phrase；句子级 = sentence
const inferredItemType = computed(() => {
  if (!props.target?.content) return 'word'
  if (props.target.type === 'word') {
    const tokens = props.target.content.trim().split(/\s+/)
    return tokens.length === 1 ? 'word' : 'phrase'
  }
  return 'sentence'
})
```

- [ ] **Step 2: Update fetchWord (single-shot explain) body**

定位 `frontend/src/components/ExplanationModal.vue:329`（`authFetchJson(\`${API.PRACTICE}/explain\`, ...)`），替换调用为：

```javascript
const { source_type, source_ref } = deriveVocabSource()
const resp = await authFetchJson(`${API.ARTICLES}/explain`, {
  text: props.target.content,
  kind: 'word',
  context: props.target.sentence || '',
  refresh,
  source_type: source_type || null,
  source_ref: source_ref || null,
  item_type: inferredItemType.value,  // ← 与 phonetic 共用
})
```

phonetic 请求（约 L318）：

```javascript
const { source_type, source_ref } = deriveVocabSource()
const p = await authFetchJson(`${API.ARTICLES}/explain/phonetic`, {
  text: props.target.content,
  source_type: source_type || null,
  source_ref: source_ref || null,
  item_type: inferredItemType.value,  // ← 与 explain 共用（不再固定 'word'）
})
```

- [ ] **Step 3: Update fetchSentence (stream) body**

定位 L378 附近的 sseStream 调用，替换为：

```javascript
const { source_type, source_ref } = deriveVocabSource()
await sseStream(
  `${API.ARTICLES}/explain/stream`,
  {
    text: props.target.content,
    refresh,
    source_type: source_type || null,
    source_ref: source_ref || null,
    item_type: inferredItemType.value,  // sentence
    context: props.target.sentence || '',
  },
  /* ... 其余配置不变 ... */
)
```

- [ ] **Step 4: Remove manual saveToVocab function & UI**

删除 `frontend/src/components/ExplanationModal.vue:265-313` 整个 `saveToVocab` 函数。

在模板中找到调用 `saveToVocab` 的按钮（如 `<button @click="saveToVocab"...>` 或 `★` / 收藏图标），删除整段。

删除相关响应式状态：`starState`、`starError`。

- [ ] **Step 5: Update existing ExplanationModal.spec.js**

ExplanationModal.spec.js 现有断言可能验证"加入生词本按钮可见"或"saveToVocab 点击调 /vocab"。这次必改：

- 删除任何关于"加入生词本按钮"的断言
- 新增断言：mount 组件 + 触发 explain → mock 的 `authFetchJson` 收到的 body 含 `source_type` / `source_ref` / `item_type`，且 phonetic 与 explain 调用的 `item_type` 相同

- [ ] **Step 6: Run frontend tests**

```bash
cd frontend && npm run test -- ExplanationModal
```
Expected: 全绿（更新后的断言）

- [ ] **Step 7: Manual smoke test**

启动 dev server，登录后打开 `/articles`，点一个 BBC 单词与一个 BBC 句子。打开浏览器 DevTools Network，确认 `/articles/explain/phonetic`、`/articles/explain`、`/articles/explain/stream` 请求 body 中携带 `source_type: 'bbc_eaw'`、`source_ref: <slug>`、`item_type`，且 phonetic 与 explain 的 `item_type` 一致。

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(frontend): explain requests carry source fields; phonetic & explain share inferred item_type; remove manual saveToVocab"
```

---

### Task 13: Vocabulary.vue — 列表 + tag chip + 分页 + 接口对接

**Files:**
- Modify: `frontend/src/views/Vocabulary.vue`
- Modify: `frontend/src/composables/`（若需要可新建 `useVocabList.js`）

- [ ] **Step 1: Implement list fetching + tag chip + pagination**

替换 `frontend/src/views/Vocabulary.vue` 内容为：

```vue
<template>
  <div class="vocab-page">
    <header class="vocab-header">
      <h1>我的生词本</h1>
      <span class="vocab-count">已加载 {{ items.length }} 条</span>
    </header>

    <nav class="tag-chips">
      <button
        v-for="t in tabs"
        :key="t.value"
        :class="['chip', { active: currentTag === t.value }]"
        @click="switchTag(t.value)"
      >
        {{ t.label }}
      </button>
    </nav>

    <div v-if="loading" class="vocab-loading">加载中...</div>
    <div v-else-if="items.length === 0" class="vocab-empty">暂无条目</div>
    <ul v-else class="vocab-list">
      <li v-for="item in items" :key="item.id" class="vocab-item">
        <div class="vocab-head" @click="toggle(item.id)">
          <span class="vocab-text">{{ truncate(item.source_text, 80) }}</span>
          <span :class="['vocab-tag', `tag-${item.source_type}`]">{{ tagLabel(item.source_type) }}</span>
        </div>
        <div class="vocab-translated">{{ item.translated_text || '—' }}</div>
        <div class="vocab-meta">
          ⏱ {{ relativeTime(item.created_at) }}
          <span v-if="!item.explanation_json" class="vocab-pending">⚠ 解读生成中</span>
        </div>
        <!-- 展开区由 Task 14 实现 -->
        <div v-if="expandedId === item.id" class="vocab-detail">
          <!-- 占位，Task 14 接入 explanation 渲染 -->
        </div>
      </li>
    </ul>

    <div v-if="hasMore" class="vocab-loadmore">
      <button @click="loadMore">加载更多</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAuthFetch, getErrorMessage } from '@/composables/useAuthFetch'
import { API } from '@/config'

const { authFetchJson } = useAuthFetch()

const tabs = [
  { value: '', label: '全部' },
  { value: 'bbc_eaw', label: 'BBC' },
  { value: 'translate', label: '翻译收藏' },
]

const currentTag = ref('')
const items = ref([])
const loading = ref(false)
const expandedId = ref(null)
const offset = ref(0)
const PAGE_SIZE = 20
const hasMore = ref(false)

function tagLabel(source_type) {
  return tabs.find(t => t.value === source_type)?.label || source_type
}

function truncate(text, n) {
  if (!text) return ''
  return text.length > n ? text.slice(0, n) + '…' : text
}

function relativeTime(iso) {
  if (!iso) return ''
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  return `${Math.floor(diff / 86400)} 天前`
}

async function fetchList(reset = false) {
  loading.value = true
  if (reset) {
    offset.value = 0
    items.value = []
  }
  const params = new URLSearchParams({
    limit: String(PAGE_SIZE),
    offset: String(offset.value),
  })
  if (currentTag.value) params.set('source_type', currentTag.value)
  try {
    // useAuthFetch 的 authFetchJson 是 (url, body?, options?) → body 为 null/undefined 走 GET。
    // 注意：当前 /vocab 接口 `count` 只是当前页数量，不是全量总数；UI 上故以 items.length 展示「已加载 N 条」。
    // 若未来要显示全量总数，应在后端 `list_items` 加 count 查询，并在 API 返回 `total` 字段。
    const data = await authFetchJson(`${API.VOCAB}?${params}`)
    items.value = reset ? data.items : [...items.value, ...data.items]
    hasMore.value = data.items.length === PAGE_SIZE
    offset.value += data.items.length
  } catch (err) {
    console.error('vocab list failed:', getErrorMessage(err, '加载失败'))
  } finally {
    loading.value = false
  }
}

function switchTag(t) {
  currentTag.value = t
  fetchList(true)
}

function loadMore() {
  fetchList(false)
}

function toggle(id) {
  expandedId.value = expandedId.value === id ? null : id
}

onMounted(() => fetchList(true))
</script>

<style scoped>
.vocab-page { padding: 16px; max-width: 720px; margin: 0 auto; }
.vocab-header { display: flex; align-items: baseline; gap: 12px; }
.vocab-count { color: #888; font-size: 14px; }
.tag-chips { display: flex; gap: 8px; margin: 12px 0; }
.chip { padding: 6px 14px; border-radius: 16px; border: 1px solid #ccc; background: transparent; cursor: pointer; }
.chip.active { background: var(--accent, #4a90e2); color: white; border-color: transparent; }
.vocab-list { list-style: none; padding: 0; }
.vocab-item { border-bottom: 1px solid #eee; padding: 12px 0; }
.vocab-head { display: flex; justify-content: space-between; align-items: center; cursor: pointer; }
.vocab-text { font-weight: 600; }
.vocab-tag { font-size: 12px; padding: 2px 8px; border-radius: 8px; background: #eee; }
.tag-bbc_eaw { background: #ffe9d6; }
.tag-translate { background: #d6f0ff; }
.vocab-translated { color: #555; margin: 4px 0; }
.vocab-meta { font-size: 12px; color: #888; }
.vocab-pending { color: #c97c00; margin-left: 8px; }
.vocab-loadmore { text-align: center; margin-top: 16px; }
.vocab-empty, .vocab-loading { padding: 24px; text-align: center; color: #888; }
</style>
```

> 上面代码使用的 import 都已确认存在：`@/composables/useAuthFetch`（含 `useAuthFetch`、`getErrorMessage`、`authFetchJson(url, body?, options?)`）和 `@/config`（含 `API.VOCAB` / `API.ARTICLES`，后者由 Task 10 新增）。**不要**用 `@/utils/api` / `@/api/endpoints` 这些路径，它们不存在。

- [ ] **Step 2: Navigation entry**

在 Home.vue（或主导航组件）的话题卡片区追加：

```vue
<router-link to="/vocabulary" class="nav-card">
  <h3>📖 生词本</h3>
  <p>所有点过的语言点</p>
</router-link>
```

样式沿用旁边卡片。

- [ ] **Step 3: Manual smoke test**

`npm run dev`，登录后：
1. 访问 `/vocabulary` → 看到列表（如为空，先在 /articles 点几个词触发自动入库再回来看）
2. 切换 chip：全部 / BBC / 翻译收藏 → 列表对应过滤
3. 点条目 → 占位展开（详细渲染在 Task 14）
4. 分页：若条目 > 20，点"加载更多"能追加

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(vocabulary): standalone /vocabulary page with tag chips & pagination"
```

---

### Task 14: Vocabulary 卡片原地展开 → 渲染完整 explanation

> 复用 ExplanationModal 内部的字段渲染思路；为避免大改组件，本 task 在 Vocabulary.vue 内**直接实现一个轻量 explanation 渲染段**（不抽公共组件）。如 explanation_json 字段较多，先渲染最常用的 meaning / grammar / phrases / liaison / phonetic / definitions / examples 七个。

**Files:**
- Modify: `frontend/src/views/Vocabulary.vue`

- [ ] **Step 1: Add detail rendering**

在 `Vocabulary.vue` 模板的 `<div v-if="expandedId === item.id" class="vocab-detail">` 内插入：

```vue
<template v-if="parsedExplanation(item)">
  <div v-if="parsedExplanation(item).phonetic" class="exp-row">
    <strong>音标：</strong>/{{ parsedExplanation(item).phonetic }}/
  </div>
  <div v-if="parsedExplanation(item).meaning" class="exp-row">
    <strong>含义：</strong>{{ parsedExplanation(item).meaning }}
  </div>
  <div v-if="parsedExplanation(item).grammar" class="exp-row">
    <strong>语法：</strong>{{ parsedExplanation(item).grammar }}
  </div>
  <div v-if="parsedExplanation(item).definitions?.length" class="exp-row">
    <strong>释义：</strong>
    <ul><li v-for="d in parsedExplanation(item).definitions" :key="d">{{ d }}</li></ul>
  </div>
  <div v-if="parsedExplanation(item).examples?.length" class="exp-row">
    <strong>例句：</strong>
    <ul><li v-for="e in parsedExplanation(item).examples" :key="e">{{ e }}</li></ul>
  </div>
  <div v-if="parsedExplanation(item).phrases?.length" class="exp-row">
    <strong>短语：</strong>
    <ul><li v-for="p in parsedExplanation(item).phrases" :key="JSON.stringify(p)">{{ typeof p === 'string' ? p : (p.phrase + ' — ' + p.meaning) }}</li></ul>
  </div>
  <div v-if="parsedExplanation(item).liaison?.length" class="exp-row">
    <strong>连读：</strong>
    <ul><li v-for="l in parsedExplanation(item).liaison" :key="JSON.stringify(l)">{{ typeof l === 'string' ? l : JSON.stringify(l) }}</li></ul>
  </div>
</template>
<template v-else>
  <!-- Task 15 接入 pending 重拉 -->
  <button class="exp-fetch" @click="fetchPending(item)">点击生成解读</button>
</template>
```

在 `<script setup>` 中追加：

```javascript
function parsedExplanation(item) {
  if (!item.explanation_json) return null
  try {
    return typeof item.explanation_json === 'string'
      ? JSON.parse(item.explanation_json)
      : item.explanation_json
  } catch {
    return null
  }
}

function fetchPending(item) {
  /* Task 15 实现 */
}
```

样式补：

```css
.vocab-detail { padding: 12px 0 4px; border-top: 1px dashed #ddd; margin-top: 8px; }
.exp-row { margin: 6px 0; }
.exp-row ul { margin: 4px 0 4px 18px; }
.exp-fetch { padding: 6px 12px; border: 1px solid #4a90e2; color: #4a90e2; background: transparent; border-radius: 8px; cursor: pointer; }
```

- [ ] **Step 2: Manual smoke test**

`/vocabulary` 中点一个 ready 条目（`explanation_json` 非空）→ 应看到 meaning / grammar 等渲染；点一个 pending 条目 → 显示「点击生成解读」按钮。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/Vocabulary.vue
git commit -m "feat(vocabulary): expand card renders explanation fields inline"
```

---

### Task 15: Vocabulary pending 条目点开自动拉新解读 + 回填到列表

**Files:**
- Modify: `frontend/src/views/Vocabulary.vue`

- [ ] **Step 1: Implement fetchPending**

替换 Task 14 中占位的 `fetchPending(item)` 为：

```javascript
async function fetchPending(item) {
  // 句子级走 stream，词级走单次 explain
  const isSentence = item.item_type === 'sentence'
  try {
    if (isSentence) {
      const fields = {}
      await sseStream(`${API.ARTICLES}/explain/stream`, {
        text: item.source_text,
        source_type: item.source_type,
        source_ref: item.source_ref,
        item_type: 'sentence',
        context: item.context || '',
      }, {
        mode: 'ndjson',
        onEvent: (evt) => {
          if (evt._cached && evt.explanation) Object.assign(fields, evt.explanation)
          else if (evt.field) fields[evt.field] = evt.value
        },
      })
      item.explanation_json = JSON.stringify(fields)
    } else {
      const resp = await authFetchJson(`${API.ARTICLES}/explain`, {
        text: item.source_text,
        kind: 'word',
        context: item.context || '',
        source_type: item.source_type,
        source_ref: item.source_ref,
        item_type: item.item_type,
      })
      item.explanation_json = JSON.stringify(resp.explanation || {})
    }
  } catch (e) {
    item._fetchError = '生成失败，请稍后重试'
  }
}
```

`authFetchJson` 已通过 Task 13 顶部的 `useAuthFetch()` 得到。`sseStream` 在仓库的 composable 中：`import { sseStream } from '@/composables/useSSE'`（参考 `frontend/src/composables/useSSE.js`）。一并在 Vocabulary.vue 顶部 import：

```javascript
import { sseStream } from '@/composables/useSSE'
```

- [ ] **Step 2: Update template for error state**

在 pending 模板分支增加：

```vue
<template v-else>
  <button class="exp-fetch" @click="fetchPending(item)" :disabled="item._fetching">
    {{ item._fetching ? '生成中...' : '点击生成解读' }}
  </button>
  <p v-if="item._fetchError" class="exp-error">{{ item._fetchError }}</p>
</template>
```

并在 `fetchPending` 开头设置 `item._fetching = true`、finally 设回 false（让模板响应式生效需 `import { reactive }` 或使用 ref 数组——若 items 是 `ref([])` 则 push 进去的对象本身是 reactive 的，直接赋值生效）。

- [ ] **Step 3: Manual smoke test**

`/vocabulary` 中找一个 pending 条目（手动构造：调用 `/articles/explain/phonetic` 仅写 IPA → vocabulary 入库时 explanation_json=null），点"生成解读" → 应触发 `/articles/explain` 拉新内容 → 展开区渲染。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/Vocabulary.vue
git commit -m "feat(vocabulary): pending entries fetch + render explanation on demand"
```

---

### Task 16: 移除 Translate.vue 内嵌 vocabulary 折叠面板

> 生词本入口已移到 `/vocabulary`；Translate.vue 不再承担列表展示。

**Files:**
- Modify: `frontend/src/views/Translate.vue`

- [ ] **Step 1: Locate vocabulary panel**

Run: `grep -n "vocab\|生词" frontend/src/views/Translate.vue`

定位与生词本相关的：组件 import、template 区块、相关状态、API 调用。

- [ ] **Step 2: Remove**

- 删除 template 中的折叠面板 `<details>` 或对应组件标签
- 删除 `<script setup>` 中相关的 ref/方法/import
- 收藏译文到生词本的逻辑保留（POST /vocab）；只删"在本页展示已有生词列表"的那部分

- [ ] **Step 3: Manual smoke test**

`/translate` 页面 → 不再有生词列表，但翻译后"收藏到生词本"功能保留；`/vocabulary` 仍能看到刚刚收藏的条目。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/Translate.vue
git commit -m "refactor(translate): remove embedded vocabulary panel (moved to /vocabulary)"
```

---

### Task 17: 文档同步 — CLAUDE.md / README / 架构图 / flow 文档

**Files:**
- Modify: `.claude/CLAUDE.md`（API 清单 + 数据表说明 + 版本状态）
- Modify: `README.md`（路由、模块介绍）
- Modify: `docs/architecture/c4-container.md`
- Create: `docs/architecture/flows/article-explain-vocab-flow.md`（新建）

- [ ] **Step 1: Update CLAUDE.md**

打开 `.claude/CLAUDE.md`：

1. **API 接口清单**段（约 line 116–146）：
   - `/practice/subtitles` → `/articles/subtitles`
   - `/practice/cards*` → `/articles/cards*`
   - `/practice/due` → `/articles/due`
   - `/practice/explain/*` → `/articles/explain/*`
   - 在 `/practice/explain/stream` 行后追加注释 "V0.8 起：解读发起自动写入 vocabulary"
   - `/practice` (GET) → `/articles` (GET 返回 articles.html 文章学习页)
   - 在 `GET /vocab` 行末追加 "（V0.8 起支持 source_type 过滤）"
   - 新增条目（如尚未列出）：`/vocabulary` GET 返回独立生词本页

2. **版本状态**段，新增 V0.8 块：

```markdown
### 当前版本：V0.8（开发中）

**核心交付：**
- /practice → /articles 路由重命名（"文章学习"模块）
- 解读自动入库 vocabulary（占位 + 回填）
- 独立 /vocabulary 页 + source_type 标签筛选
- ExplanationModal 删除手动 saveToVocab，改由后端自动接管

**保留 alias：** `/practice/*` 路由仍可访问，与 `/articles/*` 等价；将在后续版本移除。

**关联 issue：** [#42 source_type 与表名重构为 article-* 通用语义](https://github.com/bob798/speakeasy/issues/42)（独立跟踪，不在 V0.8 范围）
```

3. **数据表清单**中 `vocabulary` 行末追加："V0.8 起 explain 接口发起即自动入库（explanation_json 由解读完成回填）"

- [ ] **Step 2: Update README.md**

`grep -n "练习\|/practice" README.md`，把发音练习模块相关描述更新为"文章学习"+ 提到新增的"生词本"独立页。具体改动按 README 实际章节调整。

- [ ] **Step 3: Update c4-container.md**

`docs/architecture/c4-container.md` 中，模块图把 `Practice` 改为 `Articles`，新增容器 `Vocabulary`（依赖 `vocab_service` + 跨模块订阅 explain 自动入库流）。

- [ ] **Step 4: Create flow doc**

新建 `docs/architecture/flows/article-explain-vocab-flow.md`：

```markdown
# Article Explain → Vocab 自动入库流

> V0.8 引入。spec: docs/superpowers/specs/2026-05-19-articles-vocab-tag-design.md

## 触发

用户在 `/articles` 文章页点击词/句子触发 ExplanationModal，发起以下三种请求之一：
- `POST /articles/explain` (单次词解读)
- `POST /articles/explain/phonetic` (IPA 本地秒出)
- `POST /articles/explain/stream` (流式句子解读)

请求体携带 `source_type='bbc_eaw'`、`source_ref=<slug>`、`item_type`。

## 路由层流程

1. 入口处调 `_auto_save_vocab(...)` 占位写入 vocabulary（`explanation_json=NULL`）
   - 唯一键 `(user_id, source_text, source_ref)` 命中 → 复活已删除条目，否则保持现状
   - 写入失败仅 `logger.warning`，不影响后续解读返回
2. 调用 explain_service 拿解读结果（缓存命中或流式）
3. 解读完成 → 调 `vocab_service.update_explanation(..., force=req.refresh)` 回填 `explanation_json`
   - `force=False`（默认）：仅在原值为 NULL 时填入
   - `force=True`（用户带 refresh）：强制覆盖

## 可靠性边界（best-effort）

- **入口占位写入**：与前端生命周期解耦，地铁断网/切走依然有 pending 记录
- **流末尾回填**：耦合在 generator 末尾，**best-effort**。客户端在流式过程中断开 → Starlette 抛 `ClientDisconnect` → generator 未跑到末尾 → 回填不执行
- **断流恢复路径**：pending 留存 → 用户从 `/vocabulary` 点开条目 → 前端再次调 `/articles/explain` → 这次客户端正常消费完整响应 → 后端回填
- 不引入 background task / Celery：与本项目规模匹配，少做不少错

## 数据语义

- `vocabulary.status='active' AND explanation_json IS NULL` → pending（生词本前端显示"⚠ 解读生成中"）
- pending 条目用户点开 → 前端再次调 `/articles/explain*` → 回填

## 关键日志锚点

- `vocab_auto_save_attempt`
- `vocab_explanation_backfill` / `vocab_explanation_backfill_miss`
- `vocab_auto_save_failed`
```

- [ ] **Step 5: Commit**

```bash
git add .claude/CLAUDE.md README.md docs/architecture/c4-container.md docs/architecture/flows/article-explain-vocab-flow.md
git commit -m "docs: V0.8 articles + vocab auto-save documentation"
```

---

### Task 18: 全量回归 + 手动 E2E 验收清单

**Files:** （仅运行测试，不改代码）

- [ ] **Step 1: Backend full test suite**

```bash
source venv/bin/activate
pytest tests/ -v 2>&1 | tail -40
```
Expected: 全绿。任何失败先回到对应 task 修复（不要在本 task 顺手改）。

- [ ] **Step 2: Frontend test suite**

```bash
cd frontend && npm run test 2>&1 | tail -30
```
Expected: 全绿。失败同上。

- [ ] **Step 3: Run dev server + manual E2E checklist**

启动：

```bash
# 终端 1（项目入口在根目录 main.py，不是 app/main.py）
source venv/bin/activate && uvicorn main:app --reload

# 终端 2
cd frontend && npm run dev
```

逐项手测并打勾：

- [ ] 访问 `/practice` → 浏览器地址栏自动跳到 `/articles`
- [ ] `/articles` 页面顶部标题显示「文章学习」，副标题「BBC English at Work」
- [ ] 在 `/articles` 点击 BBC 文章中的一个单词 → ExplanationModal 弹出 → IPA 秒出 → LLM 解读流式渲染
- [ ] 在浏览器 DevTools Network 看到 `/articles/explain/phonetic`、`/articles/explain` 或 `/articles/explain/stream` 请求 body 含 `source_type: "bbc_eaw"`、`source_ref: <slug>`、`item_type: ...`
- [ ] 切到 `/vocabulary` → 看到刚才点的词条目，时间显示「刚刚」/「N 分钟前」
- [ ] 该条目展开 → 显示完整 explanation（meaning / phonetic / definitions / 等）
- [ ] 切换 chip 「BBC」 → 仅显示 source_type=bbc_eaw 的条目
- [ ] 切换 chip 「翻译收藏」 → 仅显示 translate
- [ ] 切换 chip 「全部」 → 全显示
- [ ] 在 `/articles` 点一个仅触发 phonetic 的词（关闭弹窗，不等 LLM）→ 切到 `/vocabulary` → 该条目为 pending（⚠ 解读生成中）→ 点开 → 点"生成解读" → 自动拉新内容并展开
- [ ] 同一短语先 phonetic 后 explain（在文章页连贯操作）→ 切到 `/vocabulary` 看条目的 `item_type`，应为 `phrase`（**不是** `word`，验证 C5 修复）
- [ ] 在 ExplanationModal 点击「重新生成」（触发 `refresh=true`）→ 等流式跑完 → 切到 `/vocabulary` 看条目展开的 explanation 是新内容（验证 C2 force-overwrite）
- [ ] 流式生成进行到一半时关掉浏览器标签 → 切回 `/vocabulary` → 该条目仍存在且为 pending（验证 C1 best-effort + pending 留存）→ 点开重拉，重新生成
- [ ] OpenAPI 文档 `http://localhost:8000/docs` 中**没有** `/practice/*` 接口（被 `include_in_schema=False` 隐藏）
- [ ] `/translate` 页面不再显示生词本面板，但翻译后仍可收藏到生词本，收藏后 `/vocabulary` 能看到
- [ ] 主导航/菜单看到"生词本"入口卡片
- [ ] 旧的 ExplanationModal "★ 加入生词本"按钮不再出现

- [ ] **Step 4: Push branch**

```bash
git push -u origin feat/articles-vocab-tag
```

- [ ] **Step 5: Open PR**

```bash
gh pr create --title "feat: 文章学习 · 生词本自动入库 · 标签化 (V0.8)" --body "$(cat <<'EOF'
## Summary

- /practice → /articles 路由与文案重命名（"文章学习"模块），保留 /practice 兼容 alias
- 解读发起时自动写入 vocabulary（占位），解读完成回填 explanation_json
- 新增独立 /vocabulary 页 + source_type 标签筛选 + pending 条目原地重拉
- ExplanationModal 删除手动「加入生词本」按钮，改由后端自动接管
- 文档同步：CLAUDE.md / README / 架构图 / flow 文档

Spec: \`docs/superpowers/specs/2026-05-19-articles-vocab-tag-design.md\`
关联 issue: #42（后端 source_type 与表名重构，独立跟踪，不在本 PR 范围）

## Test plan

- [x] 后端 \`pytest tests/ -v\` 全绿
- [x] 前端 \`npm run test\` 全绿
- [x] 手动 E2E checklist（见 plan Task 18）全部通过
- [x] /practice → /articles 跳转、/practice/explain* alias 仍可访问
- [x] 自动入库 + 回填 + pending 重拉链路打通
- [x] tag chip 切换正确过滤

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review 结果

**Spec coverage check（spec 段落 → task）：**

| Spec 段落 | 对应 Task |
|---|---|
| 1. 路由与模块重命名 | Task 9（后端）+ Task 10–11（前端） |
| 2. 自动入库时序 | Task 5–8（三个端点 + 共享 helper） |
| 3. 标签机制 | Task 2–3（list_items + GET /vocab 过滤）+ Task 13（前端 tag chip） |
| 4. 生词本独立页 | Task 13–16（页面 / 展开 / pending / 移旧入口） |
| 5. 错误处理 | Task 5（容错单测）+ Task 6/8（吞异常分支） |
| 6. 改动清单（后端/前端/文档） | 分别落在 Task 1–9 / Task 10–16 / Task 17 |
| 7. 测试策略 | 每个 task 自带 TDD 步骤；Task 18 全量回归 |
| 8. 关联 issue | spec + plan 已链入 #42 |

**Placeholder scan：** 无 TBD / TODO 占位；几处「按本仓库实际调整」（API.VOCAB / sseStream import）已显式标注是查找步骤，非空占位。

**Type consistency：** `update_explanation`、`_auto_save_vocab`、`_resolve_item_type` 三个新函数在 Task 1/5 定义，签名在 Task 6/7/8 调用处与定义一致；前端 `source_type` / `source_ref` / `item_type` 在 backend schema (Task 4)、前端调用 (Task 12)、Vocabulary 渲染 (Task 13) 三处字段名统一。

**已知风险与跟进项：**

1. `tests/test_v07_*.py` 或更早测试可能引用 `app.routers.practice` —— Task 9 Step 6 grep 替换处理
2. `frontend/src/components/__tests__/ExplanationModal.spec.js` 现有断言可能验证"加入生词本按钮存在" —— Task 12 Step 5 显式更新
3. `API.PRACTICE` 在前端可能在多处定义，Task 10 仅引入 `API.ARTICLES`，不一刀切替换旧引用，让 backend alias 兜底
4. **流末尾回填是 best-effort**：客户端在流式过程中断开 → generator 不会跑到末尾 → 回填不执行。这是 by design（spec §2 已明确），由 Task 15 的 pending 重拉路径兜底；不引入 background task 复杂度

---

## Revision History

**2026-05-19 (round 1, post-codex-review)** — 应用 codex 评审到 spec + plan：

- **C1**：澄清流末尾回填是 best-effort（spec §2 关键设计点 + Task 8 注释 + flow 文档「可靠性边界」段 + Task 18 验收 checklist 新增断流场景）。基于产品决策（不引入 background task）保持架构 V1
- **C2**：`update_explanation` 加 `force=False` 参数（Task 1）；`/articles/explain` 同步路径回填带 `force=req.refresh`（Task 6）；流式同样（Task 8）；测试覆盖 force 分支（Task 1 + Task 6）
- **C3**：Task 9 列全 practice.py 的 13 个端点（不只 explain 3 个），剥前缀策略说明完整化，加 OpenAPI 不重复断言
- **C4**：全文 `from app.main import app` → `from main import app`；`app/main.py` → 根目录 `main.py`
- **C5**：spec §2 加 "save_item 命中不更新字段" 隐患说明；Task 12 前端在 ExplanationModal 顶部一次性推断 `inferredItemType`，phonetic 与 explain 共用
- **I1**：Task 4 / 7 schema 测试改为直接实例化 model 断言字段（不用 422，Pydantic 默认 ignore extra）
- **I2**：Task 9 alias router 加 `include_in_schema=False`，避免 OpenAPI 重复条目
- **I3**：Task 9 顺手把 `main.py` 的 `API_PREFIXES` 加 `"articles/"`
- **I4**：所有 `app.dependency_overrides` 改 fixture-scoped 自动清理
- **I5**：Task 7 复用现有 `get_current_user_id_optional`（auth.py:73），不新建重复函数
- **I6**：Vocabulary.vue 计数文案改 "已加载 N 条"（避免 `count` 语义歧义）
- **I7**：前端 import 路径修正为 `@/composables/useAuthFetch` + `@/config`（`@/utils/api` / `@/api/endpoints` 不存在）

Codex 评审原文：`.omc/artifacts/ask/codex-review-spec-plan-2026-05-19.md`
