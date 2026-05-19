# 文章库 · 技术文档阅读器 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `/library` 模块，让用户粘贴 URL 或 Markdown 正文导入英文技术文档，在阅读页点词 / 选区触发翻译解读，所有解读结果自动沉淀到 `vocabulary`（`source_type='library'`），文章详情页右侧侧栏「本文沉淀」原地复习。

**Architecture:**
- 后端：新增 `library_articles` 表与 `library_service`；`trafilatura` 任意 URL 提正文输出 Markdown；新增 `app/routers/library.py` 暴露 7 个端点（5 个 CRUD + 3 个 explain）；三个 explain 端点入口处通过通用工具函数 `_auto_save_library_vocab` 占位写 `vocabulary`，LLM 完成 / 缓存命中后回填 `explanation_json`（沿用既有 `vocab_service.update_explanation`）。
- 前端：新增 `Library.vue` 列表 + `AddArticleModal.vue` 导入弹窗 + `LibraryArticle.vue` 阅读详情；`marked` + `DOMPurify` 渲染 Markdown；点词浮气泡走 `quick_phonetic` 端点 + 「展开解读」按钮拉 `explain` 整体；选区 ≥2 词出气泡菜单（MVP 仅「翻译」按钮）；右侧侧栏「本文沉淀」用 `GET /vocab?source_type=library&source_ref=<id>` 取数；ExplanationCard 共享组件从 ExplanationModal 抽出。
- 文档：CLAUDE.md 数据表 + API 清单 + 版本状态升 V0.8；README.md 模块介绍；c4-container.md 增模块块与数据流；spec 在 commit `<spec PR>` 与 issue `<#tracking>` 中。

**Tech Stack:** Python 3 · FastAPI · SQLAlchemy · SQLite · trafilatura · pytest · Vue 3 · Pinia · Vite · Vitest · marked · DOMPurify

**Spec:** `docs/superpowers/specs/2026-05-19-library-tech-doc-reader-design.md`

**Branch base:** `feat/library-spec`（spec PR 合并后切新分支 `feat/library-step-N` 每 Task 一个）

---

## 阶段约定

- 测试 user_id 统一前缀：`test_user_v08_library_<task>`
- 每个 Task = 一个独立 commit + 一个 PR（题头 `[V0.8 library / Step N] ...`，body `Refs ##46`）
- 仅 Mock 外部依赖（`trafilatura.fetch_url` / `trafilatura.extract` / LLM 客户端），不 Mock 内部 service
- 断言用具体值（如 `assert article["status"] == "active"`），禁止 `assert x is not None` 模糊断言
- 每个 Task 完成判定：`pytest tests/test_v08_library_<task>.py -v` 全 PASS + 涉及到的既有测试 `pytest tests/ -k vocab -v` 不回归

---

## Task 1: 依赖与 LibraryArticle ORM model

**Files:**
- Modify: `requirements.txt`
- Modify: `app/models/db.py`（在 `Vocabulary` 之后，`TranslationCache` 之前插入）
- Test: `tests/test_v08_library_task1_model.py`（新建）

- [ ] **Step 1: Add trafilatura dependency**

```diff
# requirements.txt
+ trafilatura>=2.0.0
```

- [ ] **Step 2: Install in venv**

Run: `source venv/bin/activate && pip install -r requirements.txt`

Expected: `Successfully installed ... trafilatura-2.0.x`

- [ ] **Step 3: Write the failing test**

```python
# tests/test_v08_library_task1_model.py
import pytest
from datetime import datetime
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.exc import IntegrityError

from app.models.db import engine, LibraryArticle, init_db

USER = "test_user_v08_library_task1"


@pytest.fixture(autouse=True)
def _cleanup():
    init_db()
    with OrmSession(engine) as s:
        s.query(LibraryArticle).filter(LibraryArticle.user_id.like("test_user_v08_library_%")).delete()
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(LibraryArticle).filter(LibraryArticle.user_id.like("test_user_v08_library_%")).delete()
        s.commit()


def test_create_with_url():
    with OrmSession(engine) as s:
        article = LibraryArticle(
            user_id=USER,
            source_url="https://example.com/a",
            title="Title A",
            markdown="# Hello\n\nWorld",
            word_count=2,
            source_meta='{"site_name":"example.com"}',
        )
        s.add(article)
        s.commit()
        s.refresh(article)
        assert article.id > 0
        assert article.status == "active"
        assert article.created_at is not None


def test_paste_mode_url_null():
    with OrmSession(engine) as s:
        article = LibraryArticle(
            user_id=USER,
            source_url=None,
            title="Pasted",
            markdown="just text",
            word_count=2,
        )
        s.add(article)
        s.commit()
        assert article.id > 0


def test_unique_user_url():
    with OrmSession(engine) as s:
        s.add(LibraryArticle(user_id=USER, source_url="https://dup.com/x", title="A", markdown="x", word_count=1))
        s.commit()
    with OrmSession(engine) as s:
        s.add(LibraryArticle(user_id=USER, source_url="https://dup.com/x", title="B", markdown="y", word_count=1))
        with pytest.raises(IntegrityError):
            s.commit()


def test_multiple_paste_null_url_allowed():
    """source_url IS NULL 时唯一索引不约束 — 用户可重复粘贴正文。"""
    with OrmSession(engine) as s:
        s.add(LibraryArticle(user_id=USER, source_url=None, title="A", markdown="x", word_count=1))
        s.add(LibraryArticle(user_id=USER, source_url=None, title="B", markdown="y", word_count=1))
        s.commit()
        cnt = s.query(LibraryArticle).filter_by(user_id=USER).count()
        assert cnt == 2
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/test_v08_library_task1_model.py -v`
Expected: ImportError / `AttributeError: module 'app.models.db' has no attribute 'LibraryArticle'`

- [ ] **Step 5: Add LibraryArticle model**

```python
# app/models/db.py — 在 class Vocabulary 之后、class TranslationCache 之前插入

# ── V0.8 文章库（用户自带技术文档）──────────────────────────

class LibraryArticle(Base):
    __tablename__ = "library_articles"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    user_id      = Column(String, nullable=False, index=True)
    source_url   = Column(String, nullable=True)                          # 粘贴正文时为 NULL
    title        = Column(String, nullable=False)
    markdown     = Column(String, nullable=False)
    word_count   = Column(Integer, nullable=False, default=0)
    source_meta  = Column(String, nullable=True)                          # JSON: author/site_name/published_at/extracted_at/truncated
    status       = Column(String, nullable=False, default="active")       # active | deleted
    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index(
            "ux_library_articles_user_url",
            "user_id",
            "source_url",
            unique=True,
            sqlite_where=text("source_url IS NOT NULL"),
        ),
        Index("ix_library_articles_user_status", "user_id", "status", "created_at"),
    )
```

并在文件顶部 `from sqlalchemy import ...` 行确保引入了 `Index, text`：

```python
from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint, Index, text
```

（如已存在则跳过；同理检查 `Index` 与 `text` 是否已 import）

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_v08_library_task1_model.py -v`
Expected: 4 passed

- [ ] **Step 7: Commit**

```bash
git checkout -b feat/library-step-1
git add requirements.txt app/models/db.py tests/test_v08_library_task1_model.py
git commit -m "$(cat <<'EOF'
feat(library): 新增 LibraryArticle 表 + trafilatura 依赖 (V0.8 Step 1)

Refs ##46

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: library_service.import_article — URL 抓取 + Markdown 粘贴

**Files:**
- Create: `app/services/library_service.py`
- Test: `tests/test_v08_library_task2_import.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_v08_library_task2_import.py
import pytest
from unittest.mock import patch
from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, LibraryArticle, init_db
from app.services.library_service import import_article, ImportError as LibImportError

USER = "test_user_v08_library_task2"


@pytest.fixture(autouse=True)
def _cleanup():
    init_db()
    with OrmSession(engine) as s:
        s.query(LibraryArticle).filter(LibraryArticle.user_id.like("test_user_v08_library_%")).delete()
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(LibraryArticle).filter(LibraryArticle.user_id.like("test_user_v08_library_%")).delete()
        s.commit()


def test_import_from_url_success():
    fake_html = "<html><head><title>Spec Driven</title></head><body><article><h1>Spec Driven Development</h1><p>Hello world, this is content.</p></article></body></html>"
    with patch("app.services.library_service.fetch_url", return_value=fake_html), \
         patch(
             "app.services.library_service.extract",
             return_value='# Spec Driven Development\n\nHello world, this is content.',
         ), \
         patch(
             "app.services.library_service.extract_metadata",
             return_value=type("M", (), {"title": "Spec Driven", "author": None, "sitename": "example.com", "date": None})(),
         ):
        result = import_article(user_id=USER, url="https://example.com/spec")
    assert result["existing"] is False
    assert result["article"]["title"] == "Spec Driven"
    assert result["article"]["source_url"] == "https://example.com/spec"
    assert "Spec Driven Development" in result["article"]["markdown"]
    assert result["article"]["word_count"] > 0
    assert result["article"]["status"] == "active"


def test_import_dedupes_existing_url():
    with patch("app.services.library_service.fetch_url", return_value="x"), \
         patch("app.services.library_service.extract", return_value="# A\n\nbody"), \
         patch(
             "app.services.library_service.extract_metadata",
             return_value=type("M", (), {"title": "A", "author": None, "sitename": None, "date": None})(),
         ):
        first = import_article(user_id=USER, url="https://dup.com/x")
        second = import_article(user_id=USER, url="https://dup.com/x")
    assert first["existing"] is False
    assert second["existing"] is True
    assert second["article"]["id"] == first["article"]["id"]


def test_import_from_paste_markdown():
    result = import_article(
        user_id=USER,
        markdown="# Pasted\n\nLine one. Line two.",
        title="Pasted",
    )
    assert result["existing"] is False
    assert result["article"]["source_url"] is None
    assert result["article"]["title"] == "Pasted"
    assert result["article"]["word_count"] == 4


def test_import_from_paste_requires_title():
    with pytest.raises(ValueError, match="title"):
        import_article(user_id=USER, markdown="# Hello\n\nbody")


def test_import_from_url_fetch_fail_raises():
    with patch("app.services.library_service.fetch_url", return_value=None):
        with pytest.raises(LibImportError, match="fetch_failed"):
            import_article(user_id=USER, url="https://broken.example/x")


def test_import_from_url_extract_empty_raises():
    with patch("app.services.library_service.fetch_url", return_value="<html></html>"), \
         patch("app.services.library_service.extract", return_value=""):
        with pytest.raises(LibImportError, match="fetch_failed"):
            import_article(user_id=USER, url="https://empty.example/x")


def test_truncation_marks_meta():
    long_md = "# Long\n\n" + ("a " * 60_000)  # 约 120k 字符
    result = import_article(user_id=USER, markdown=long_md, title="Long")
    assert len(result["article"]["markdown"]) == 100_000
    import json
    meta = json.loads(result["article"]["source_meta"])
    assert meta.get("truncated") is True


def test_paste_xor_url_required():
    with pytest.raises(ValueError, match="url 或 markdown 必须二选一"):
        import_article(user_id=USER)
    with pytest.raises(ValueError, match="url 或 markdown 必须二选一"):
        import_article(user_id=USER, url="https://a", markdown="# x", title="x")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_v08_library_task2_import.py -v`
Expected: ModuleNotFoundError `app.services.library_service`

- [ ] **Step 3: Implement library_service.import_article**

```python
# app/services/library_service.py
"""文章库服务 — 用户自带技术文档的抓取、入库、列表、详情、软删。"""
import json
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.exc import IntegrityError

from trafilatura import fetch_url, extract
from trafilatura.metadata import extract_metadata

from app.models.db import engine, LibraryArticle
from app.logger import get_logger

logger = get_logger("library_service")

MAX_MARKDOWN_LEN = 100_000


class ImportError(Exception):
    """抓取 / 提取失败的领域异常。"""


def _to_dict(a: LibraryArticle) -> Dict:
    return {
        "id": a.id,
        "user_id": a.user_id,
        "source_url": a.source_url,
        "title": a.title,
        "markdown": a.markdown,
        "word_count": a.word_count,
        "source_meta": a.source_meta,
        "status": a.status,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


def _word_count(markdown: str) -> int:
    # 粗估：英文按空格分，对中文按字符（技术文档多英文，足够近似）
    return len([w for w in markdown.split() if w.strip()])


def _truncate(markdown: str, meta: Dict) -> tuple[str, Dict]:
    if len(markdown) > MAX_MARKDOWN_LEN:
        logger.warning("library_article_truncated original_len=%d", len(markdown))
        return markdown[:MAX_MARKDOWN_LEN], {**meta, "truncated": True}
    return markdown, meta


def _fetch_and_extract(url: str) -> tuple[str, Dict]:
    """抓取 url，返回 (markdown, meta)。失败抛 ImportError。"""
    html = fetch_url(url)
    if not html:
        logger.warning("library_article_fetch_failed url=%s reason=fetch_url_none", url)
        raise ImportError(f"fetch_failed: {url}")

    md = extract(html, output_format="markdown", include_links=True, include_tables=True)
    if not md or not md.strip():
        logger.warning("library_article_fetch_failed url=%s reason=extract_empty", url)
        raise ImportError(f"fetch_failed: {url}")

    meta_obj = extract_metadata(html) if html else None
    meta = {
        "extracted_at": datetime.utcnow().isoformat(),
    }
    if meta_obj is not None:
        for attr in ("title", "author", "sitename", "date"):
            v = getattr(meta_obj, attr, None)
            if v:
                meta[attr] = v
    return md, meta


def _title_from_markdown(md: str) -> str:
    for line in md.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return "Untitled"


def import_article(
    user_id: str,
    url: Optional[str] = None,
    markdown: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict:
    """导入文章。url 与 markdown 二选一。

    返回 `{"existing": bool, "article": {...}}`。URL 命中已存条目时 existing=True 不重抓。
    """
    if (url and markdown) or (not url and not markdown):
        raise ValueError("url 或 markdown 必须二选一")

    if url:
        # URL 模式：先查重
        with OrmSession(engine) as s:
            existing = (
                s.query(LibraryArticle)
                .filter_by(user_id=user_id, source_url=url)
                .first()
            )
            if existing:
                if existing.status == "deleted":
                    existing.status = "active"
                    s.commit()
                    s.refresh(existing)
                return {"existing": True, "article": _to_dict(existing)}

        md, meta = _fetch_and_extract(url)
        resolved_title = title or meta.get("title") or _title_from_markdown(md)
    else:
        # 粘贴模式：title 必填
        if not title or not title.strip():
            raise ValueError("粘贴正文模式 title 不能为空")
        md = markdown
        meta = {"extracted_at": datetime.utcnow().isoformat(), "source": "paste"}
        resolved_title = title.strip()

    md, meta = _truncate(md, meta)

    article = LibraryArticle(
        user_id=user_id,
        source_url=url,
        title=resolved_title,
        markdown=md,
        word_count=_word_count(md),
        source_meta=json.dumps(meta, ensure_ascii=False),
        status="active",
    )
    with OrmSession(engine) as s:
        s.add(article)
        try:
            s.commit()
        except IntegrityError:
            # 并发去重兜底
            s.rollback()
            existing = (
                s.query(LibraryArticle)
                .filter_by(user_id=user_id, source_url=url)
                .first()
            )
            if existing:
                return {"existing": True, "article": _to_dict(existing)}
            raise
        s.refresh(article)
        logger.info(
            "library_article_imported user_id=%s id=%s mode=%s len=%d",
            user_id, article.id, "url" if url else "paste", len(md),
        )
        return {"existing": False, "article": _to_dict(article)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_v08_library_task2_import.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add app/services/library_service.py tests/test_v08_library_task2_import.py
git commit -m "$(cat <<'EOF'
feat(library): library_service.import_article — URL 抓取 + Markdown 粘贴 (V0.8 Step 2)

trafilatura 抓正文输出 Markdown；超长截断 100k；URL 命中去重；
软删条目复活；并发 IntegrityError 兜底。失败抛 ImportError。

Refs ##46

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: library_service — list / get / delete / refetch

**Files:**
- Modify: `app/services/library_service.py`（追加 4 个函数）
- Test: `tests/test_v08_library_task3_crud.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_v08_library_task3_crud.py
import pytest
from unittest.mock import patch
from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, LibraryArticle, Vocabulary, init_db
from app.services.library_service import (
    import_article, list_articles, get_article, delete_article, refetch_article,
    ImportError as LibImportError,
)

USER = "test_user_v08_library_task3"


@pytest.fixture(autouse=True)
def _cleanup():
    init_db()
    with OrmSession(engine) as s:
        s.query(LibraryArticle).filter(LibraryArticle.user_id.like("test_user_v08_library_%")).delete()
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_library_%")).delete()
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(LibraryArticle).filter(LibraryArticle.user_id.like("test_user_v08_library_%")).delete()
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_library_%")).delete()
        s.commit()


def _seed(n: int):
    ids = []
    for i in range(n):
        a = import_article(user_id=USER, markdown=f"# A{i}\n\nbody", title=f"A{i}")
        ids.append(a["article"]["id"])
    return ids


def test_list_returns_active_only_desc():
    ids = _seed(3)
    delete_article(ids[1], USER)
    items = list_articles(USER, page=1, page_size=20)
    assert len(items) == 2
    # created_at DESC
    assert items[0]["title"] == "A2"
    assert items[1]["title"] == "A0"


def test_list_pagination():
    _seed(5)
    p1 = list_articles(USER, page=1, page_size=2)
    p2 = list_articles(USER, page=2, page_size=2)
    p3 = list_articles(USER, page=3, page_size=2)
    assert len(p1) == 2 and len(p2) == 2 and len(p3) == 1
    assert p1[0]["id"] != p2[0]["id"]


def test_list_includes_vocab_count():
    [aid] = _seed(1)
    from app.services.vocab_service import save_item
    save_item(user_id=USER, source_text="hello", source_type="library",
              source_ref=str(aid), item_type="word")
    save_item(user_id=USER, source_text="world", source_type="library",
              source_ref=str(aid), item_type="word")
    items = list_articles(USER, page=1, page_size=20)
    assert items[0]["vocab_count"] == 2


def test_get_article_returns_full_markdown():
    [aid] = _seed(1)
    a = get_article(aid, USER)
    assert a["id"] == aid
    assert a["markdown"].startswith("# A0")
    assert a["status"] == "active"


def test_get_article_missing_returns_none():
    assert get_article(99999, USER) is None


def test_get_article_other_user_returns_none():
    [aid] = _seed(1)
    assert get_article(aid, "test_user_v08_library_task3_other") is None


def test_delete_article_soft_deletes():
    [aid] = _seed(1)
    ok = delete_article(aid, USER)
    assert ok is True
    with OrmSession(engine) as s:
        v = s.query(LibraryArticle).filter_by(id=aid).first()
        assert v.status == "deleted"


def test_delete_does_not_cascade_vocabulary():
    [aid] = _seed(1)
    from app.services.vocab_service import save_item
    save_item(user_id=USER, source_text="kept", source_type="library",
              source_ref=str(aid), item_type="word")
    delete_article(aid, USER)
    with OrmSession(engine) as s:
        v = s.query(Vocabulary).filter_by(user_id=USER, source_text="kept").first()
        assert v is not None
        assert v.status == "active"  # 不级联


def test_refetch_rejects_paste_articles():
    [aid] = _seed(1)  # paste 模式（无 url）
    with pytest.raises(ValueError, match="非 URL"):
        refetch_article(aid, USER)


def test_refetch_replaces_markdown():
    with patch("app.services.library_service.fetch_url", return_value="x"), \
         patch("app.services.library_service.extract", return_value="# Old\n\nold body"), \
         patch(
             "app.services.library_service.extract_metadata",
             return_value=type("M", (), {"title": "Old", "author": None, "sitename": None, "date": None})(),
         ):
        a = import_article(USER, url="https://refetch.example/x")
    aid = a["article"]["id"]
    with patch("app.services.library_service.fetch_url", return_value="x"), \
         patch("app.services.library_service.extract", return_value="# New\n\nnew body"), \
         patch(
             "app.services.library_service.extract_metadata",
             return_value=type("M", (), {"title": "New", "author": None, "sitename": None, "date": None})(),
         ):
        result = refetch_article(aid, USER)
    assert "New" in result["markdown"]
    assert "old" not in result["markdown"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_v08_library_task3_crud.py -v`
Expected: ImportError — list_articles / get_article / delete_article / refetch_article undefined

- [ ] **Step 3: Append 4 functions to library_service.py**

```python
# app/services/library_service.py — 追加在 import_article 之后

def list_articles(user_id: str, page: int = 1, page_size: int = 20) -> list[Dict]:
    """文章列表，仅 active；按 created_at DESC；每条附带 vocab_count。"""
    from sqlalchemy import func
    from app.models.db import Vocabulary

    offset = max(0, (page - 1) * page_size)
    with OrmSession(engine) as s:
        rows = (
            s.query(LibraryArticle)
            .filter_by(user_id=user_id, status="active")
            .order_by(LibraryArticle.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )
        result = []
        for a in rows:
            count = (
                s.query(func.count(Vocabulary.id))
                .filter_by(
                    user_id=user_id,
                    source_type="library",
                    source_ref=str(a.id),
                    status="active",
                )
                .scalar()
            ) or 0
            d = _to_dict(a)
            d["vocab_count"] = int(count)
            result.append(d)
        return result


def get_article(article_id: int, user_id: str) -> Optional[Dict]:
    """获取文章详情；越权 / 不存在均返 None。"""
    with OrmSession(engine) as s:
        a = (
            s.query(LibraryArticle)
            .filter_by(id=article_id, user_id=user_id)
            .first()
        )
        if not a:
            return None
        return _to_dict(a)


def delete_article(article_id: int, user_id: str) -> bool:
    """软删；vocabulary 条目不级联。"""
    with OrmSession(engine) as s:
        a = (
            s.query(LibraryArticle)
            .filter_by(id=article_id, user_id=user_id, status="active")
            .first()
        )
        if not a:
            return False
        a.status = "deleted"
        s.commit()
        logger.info("library_article_deleted user_id=%s id=%s", user_id, article_id)
        return True


def refetch_article(article_id: int, user_id: str) -> Dict:
    """强制重抓（仅 URL 类）。粘贴正文模式拒绝。"""
    with OrmSession(engine) as s:
        a = (
            s.query(LibraryArticle)
            .filter_by(id=article_id, user_id=user_id)
            .first()
        )
        if not a:
            raise LookupError("文章不存在")
        if not a.source_url:
            raise ValueError("非 URL 模式文章不支持重抓")
        md, meta = _fetch_and_extract(a.source_url)
        md, meta = _truncate(md, meta)
        a.markdown = md
        a.word_count = _word_count(md)
        a.source_meta = json.dumps(meta, ensure_ascii=False)
        a.title = meta.get("title") or a.title
        a.updated_at = datetime.utcnow()
        s.commit()
        s.refresh(a)
        logger.info("library_article_refetched user_id=%s id=%s", user_id, article_id)
        return _to_dict(a)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_v08_library_task3_crud.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add app/services/library_service.py tests/test_v08_library_task3_crud.py
git commit -m "$(cat <<'EOF'
feat(library): list/get/delete/refetch service 函数 (V0.8 Step 3)

list 返回时带 vocab_count，避免前端 N+1；
delete 不级联 vocabulary；refetch 拒绝粘贴模式。

Refs ##46

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: app/routers/library.py — CRUD 5 端点

**Files:**
- Create: `app/routers/library.py`
- Modify: `main.py`（在 `practice_router` 注册附近追加 `library_router` import + include）
- Test: `tests/test_v08_library_task4_router_crud.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_v08_library_task4_router_crud.py
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from main import app
from app.models.db import engine, LibraryArticle, Vocabulary, init_db

USER = "test_user_v08_library_task4"
HEADERS = {"X-User-Id": USER}


@pytest.fixture(autouse=True)
def _cleanup():
    init_db()
    with OrmSession(engine) as s:
        s.query(LibraryArticle).filter(LibraryArticle.user_id.like("test_user_v08_library_%")).delete()
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_library_%")).delete()
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(LibraryArticle).filter(LibraryArticle.user_id.like("test_user_v08_library_%")).delete()
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_library_%")).delete()
        s.commit()


client = TestClient(app)


def test_post_articles_paste_mode_201():
    r = client.post(
        "/library/articles",
        json={"markdown": "# Hello\n\nbody.", "title": "Hello"},
        headers=HEADERS,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["existing"] is False
    assert data["article"]["title"] == "Hello"


def test_post_articles_paste_missing_title_400():
    r = client.post(
        "/library/articles",
        json={"markdown": "# x"},
        headers=HEADERS,
    )
    assert r.status_code == 400


def test_post_articles_url_mode_calls_trafilatura():
    with patch("app.services.library_service.fetch_url", return_value="<html>x</html>"), \
         patch("app.services.library_service.extract", return_value="# Title\n\nbody"), \
         patch(
             "app.services.library_service.extract_metadata",
             return_value=type("M", (), {"title": "Title", "author": None, "sitename": None, "date": None})(),
         ):
        r = client.post(
            "/library/articles",
            json={"url": "https://example.com/x"},
            headers=HEADERS,
        )
    assert r.status_code == 201
    assert r.json()["article"]["source_url"] == "https://example.com/x"


def test_post_articles_url_dedup_200():
    with patch("app.services.library_service.fetch_url", return_value="<html>x</html>"), \
         patch("app.services.library_service.extract", return_value="# T\n\nb"), \
         patch(
             "app.services.library_service.extract_metadata",
             return_value=type("M", (), {"title": "T", "author": None, "sitename": None, "date": None})(),
         ):
        client.post("/library/articles", json={"url": "https://dup.example/a"}, headers=HEADERS)
        r = client.post("/library/articles", json={"url": "https://dup.example/a"}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["existing"] is True


def test_post_articles_fetch_failed_400():
    with patch("app.services.library_service.fetch_url", return_value=None):
        r = client.post(
            "/library/articles",
            json={"url": "https://broken.example/x"},
            headers=HEADERS,
        )
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "fetch_failed"
    assert "粘贴正文" in r.json()["detail"]["hint"]


def test_get_articles_lists_active():
    client.post("/library/articles", json={"markdown": "# A", "title": "A"}, headers=HEADERS)
    client.post("/library/articles", json={"markdown": "# B", "title": "B"}, headers=HEADERS)
    r = client.get("/library/articles", headers=HEADERS)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 2


def test_get_article_detail():
    r = client.post("/library/articles", json={"markdown": "# X\n\nbody", "title": "X"}, headers=HEADERS)
    aid = r.json()["article"]["id"]
    r2 = client.get(f"/library/articles/{aid}", headers=HEADERS)
    assert r2.status_code == 200
    assert r2.json()["article"]["title"] == "X"


def test_get_article_404():
    r = client.get("/library/articles/999999", headers=HEADERS)
    assert r.status_code == 404


def test_delete_article_204():
    r = client.post("/library/articles", json={"markdown": "# X", "title": "X"}, headers=HEADERS)
    aid = r.json()["article"]["id"]
    r2 = client.delete(f"/library/articles/{aid}", headers=HEADERS)
    assert r2.status_code == 204
    r3 = client.get(f"/library/articles/{aid}", headers=HEADERS)
    # 软删后不可见
    assert r3.status_code == 404 or r3.json()["article"]["status"] == "deleted"


def test_refetch_url_article():
    with patch("app.services.library_service.fetch_url", return_value="x"), \
         patch("app.services.library_service.extract", return_value="# Old\n\nold"), \
         patch(
             "app.services.library_service.extract_metadata",
             return_value=type("M", (), {"title": "Old", "author": None, "sitename": None, "date": None})(),
         ):
        r = client.post("/library/articles", json={"url": "https://r.example/a"}, headers=HEADERS)
    aid = r.json()["article"]["id"]
    with patch("app.services.library_service.fetch_url", return_value="x"), \
         patch("app.services.library_service.extract", return_value="# New\n\nnew"), \
         patch(
             "app.services.library_service.extract_metadata",
             return_value=type("M", (), {"title": "New", "author": None, "sitename": None, "date": None})(),
         ):
        r2 = client.post(f"/library/articles/{aid}/refetch", headers=HEADERS)
    assert r2.status_code == 200
    assert "New" in r2.json()["article"]["markdown"]


def test_refetch_paste_400():
    r = client.post("/library/articles", json={"markdown": "# P", "title": "P"}, headers=HEADERS)
    aid = r.json()["article"]["id"]
    r2 = client.post(f"/library/articles/{aid}/refetch", headers=HEADERS)
    assert r2.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_v08_library_task4_router_crud.py -v`
Expected: 404 on all `/library/articles*` endpoints (router not registered)

- [ ] **Step 3: Implement library router**

```python
# app/routers/library.py
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from app.routers.auth import get_current_user_id
from app.services import library_service
from app.services.library_service import ImportError as LibImportError
from app.logger import get_logger

logger = get_logger("library_router")
router = APIRouter()


class ImportArticleRequest(BaseModel):
    url: Optional[str] = None
    markdown: Optional[str] = None
    title: Optional[str] = None


@router.post("/library/articles")
async def post_article(
    req: ImportArticleRequest,
    user_id: str = Depends(get_current_user_id),
):
    try:
        result = library_service.import_article(
            user_id=user_id,
            url=req.url,
            markdown=req.markdown,
            title=req.title,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except LibImportError as e:
        raise HTTPException(
            400,
            detail={"error": "fetch_failed", "hint": "抓取失败，请改用粘贴正文模式"},
        )
    except Exception as e:
        logger.error("import_article 失败: %s", e, exc_info=True)
        raise HTTPException(503, "服务暂时不可用，请稍后重试")
    # 命中已存条目走 200；新条目走 201
    from fastapi.responses import JSONResponse
    status_code = 200 if result["existing"] else 201
    return JSONResponse(content=result, status_code=status_code)


@router.get("/library/articles")
async def get_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
):
    items = library_service.list_articles(user_id=user_id, page=page, page_size=page_size)
    return {"items": items, "page": page, "page_size": page_size}


@router.get("/library/articles/{article_id}")
async def get_article(
    article_id: int,
    user_id: str = Depends(get_current_user_id),
):
    article = library_service.get_article(article_id, user_id)
    if not article or article["status"] == "deleted":
        raise HTTPException(404, "文章不存在")
    return {"article": article}


@router.delete("/library/articles/{article_id}", status_code=204)
async def delete_article(
    article_id: int,
    user_id: str = Depends(get_current_user_id),
):
    ok = library_service.delete_article(article_id, user_id)
    if not ok:
        raise HTTPException(404, "文章不存在")
    return None


@router.post("/library/articles/{article_id}/refetch")
async def refetch_article(
    article_id: int,
    user_id: str = Depends(get_current_user_id),
):
    try:
        article = library_service.refetch_article(article_id, user_id)
    except LookupError:
        raise HTTPException(404, "文章不存在")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except LibImportError:
        raise HTTPException(
            400,
            detail={"error": "fetch_failed", "hint": "重新抓取失败"},
        )
    return {"article": article}
```

- [ ] **Step 4: Register router in main.py**

```python
# main.py — 在现有 router import 区追加：
from app.routers.library import router as library_router

# 在 include_router 区追加（与其它紧邻）：
app.include_router(library_router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_v08_library_task4_router_crud.py -v`
Expected: 11 passed

- [ ] **Step 6: Commit**

```bash
git add app/routers/library.py main.py tests/test_v08_library_task4_router_crud.py
git commit -m "$(cat <<'EOF'
feat(library): /library CRUD 路由 (V0.8 Step 4)

POST /library/articles (URL/粘贴二选一, 201/200/400);
GET /library/articles 分页; GET /library/articles/{id}; DELETE; POST /refetch.

Refs ##46

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: 扩展 source_type='library' + 自动入库工具函数

**Files:**
- Modify: `app/services/vocab_service.py:28`（`VALID_SOURCE_TYPES` 加 `library`）
- Modify: `app/routers/library.py`（追加 `_auto_save_library_vocab` 工具）
- Test: `tests/test_v08_library_task5_auto_save.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_v08_library_task5_auto_save.py
import pytest
from sqlalchemy.orm import Session as OrmSession

from app.models.db import engine, LibraryArticle, Vocabulary, init_db
from app.services.vocab_service import save_item, list_items, VALID_SOURCE_TYPES
from app.routers.library import _auto_save_library_vocab

USER = "test_user_v08_library_task5"


@pytest.fixture(autouse=True)
def _cleanup():
    init_db()
    with OrmSession(engine) as s:
        s.query(LibraryArticle).filter(LibraryArticle.user_id.like("test_user_v08_library_%")).delete()
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_library_%")).delete()
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(LibraryArticle).filter(LibraryArticle.user_id.like("test_user_v08_library_%")).delete()
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_library_%")).delete()
        s.commit()


def test_library_in_valid_source_types():
    assert "library" in VALID_SOURCE_TYPES


def test_save_item_accepts_library_source_type():
    item = save_item(
        user_id=USER, source_text="banter", item_type="word",
        source_type="library", source_ref="42",
    )
    assert item["source_type"] == "library"
    assert item["source_ref"] == "42"


def test_auto_save_resolves_word_kind():
    _auto_save_library_vocab(USER, text="banter", kind="word", article_id=7, context="office banter today")
    items = list_items(USER)
    assert len(items) == 1
    assert items[0]["item_type"] == "word"
    assert items[0]["source_type"] == "library"
    assert items[0]["source_ref"] == "7"
    assert items[0]["context"] == "office banter today"
    assert items[0]["explanation_json"] is None  # 占位


def test_auto_save_idempotent_on_same_source_ref():
    _auto_save_library_vocab(USER, text="banter", kind="word", article_id=7)
    _auto_save_library_vocab(USER, text="banter", kind="word", article_id=7)
    items = list_items(USER)
    assert len(items) == 1


def test_auto_save_swallows_exception(monkeypatch):
    def boom(**_): raise RuntimeError("db down")
    monkeypatch.setattr("app.routers.library.save_item", boom)
    # 不应抛
    _auto_save_library_vocab(USER, text="x", kind="word", article_id=1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_v08_library_task5_auto_save.py -v`
Expected: ImportError `_auto_save_library_vocab`；`VALID_SOURCE_TYPES` 不含 library

- [ ] **Step 3: Extend VALID_SOURCE_TYPES**

```python
# app/services/vocab_service.py:28
VALID_SOURCE_TYPES = {"translate", "bbc_eaw", "practice", "chat", "library"}
```

- [ ] **Step 4: Add _auto_save_library_vocab to library.py**

```python
# app/routers/library.py — 顶部新增 import
from app.services.vocab_service import save_item

# 文件底部追加
def _auto_save_library_vocab(
    user_id: str,
    text: str,
    kind: str,
    article_id: int,
    context: str = "",
) -> None:
    """路由入口处的占位写入；任何异常仅记日志，不抛。

    kind ∈ {'word', 'phrase', 'sentence'} 对应 vocabulary.item_type；本函数直接透传。
    """
    try:
        save_item(
            user_id=user_id,
            source_text=text,
            translated_text="",
            direction="en2zh",
            context=context or None,
            item_type=kind,
            source_type="library",
            source_ref=str(article_id),
            explanation_json=None,
        )
        logger.info(
            "library_vocab_auto_save user_id=%s article_id=%s kind=%s len=%d",
            user_id, article_id, kind, len(text),
        )
    except Exception as e:
        logger.warning(
            "library_vocab_auto_save_failed user_id=%s article_id=%s err=%s",
            user_id, article_id, e,
        )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_v08_library_task5_auto_save.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add app/services/vocab_service.py app/routers/library.py tests/test_v08_library_task5_auto_save.py
git commit -m "$(cat <<'EOF'
feat(library): vocab source_type='library' + _auto_save_library_vocab (V0.8 Step 5)

VALID_SOURCE_TYPES 加 library; 自动入库工具吞异常仅日志。

Refs ##46

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `/library/articles/{id}/explain` 同步解读 + 自动入库 + 回填

**Files:**
- Modify: `app/routers/library.py`（追加端点）
- Test: `tests/test_v08_library_task6_explain.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_v08_library_task6_explain.py
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from main import app
from app.models.db import engine, LibraryArticle, Vocabulary, init_db

USER = "test_user_v08_library_task6"
HEADERS = {"X-User-Id": USER}
client = TestClient(app)


@pytest.fixture(autouse=True)
def _cleanup():
    init_db()
    with OrmSession(engine) as s:
        s.query(LibraryArticle).filter(LibraryArticle.user_id.like("test_user_v08_library_%")).delete()
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_library_%")).delete()
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(LibraryArticle).filter(LibraryArticle.user_id.like("test_user_v08_library_%")).delete()
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_library_%")).delete()
        s.commit()


def _make_article():
    r = client.post(
        "/library/articles",
        json={"markdown": "# A\n\nbody with banter.", "title": "A"},
        headers=HEADERS,
    )
    return r.json()["article"]["id"]


def test_explain_writes_placeholder_then_backfills():
    aid = _make_article()
    fake_explanation = {"meaning": "办公室闲聊", "grammar": "...", "phrases": []}
    with patch(
        "app.routers.library.explain_text",
        new=AsyncMock(return_value={
            "explanation": fake_explanation,
            "cefr_level": "B1",
            "cached": False,
        }),
    ):
        r = client.post(
            f"/library/articles/{aid}/explain",
            json={"text": "banter", "kind": "word", "context": "office banter today"},
            headers=HEADERS,
        )
    assert r.status_code == 200
    assert r.json()["explanation"]["meaning"] == "办公室闲聊"

    # 占位写入 + 回填
    with OrmSession(engine) as s:
        v = s.query(Vocabulary).filter_by(
            user_id=USER, source_text="banter", source_ref=str(aid)
        ).first()
        assert v is not None
        assert v.source_type == "library"
        assert v.item_type == "word"
        assert v.explanation_json is not None
        assert "办公室闲聊" in v.explanation_json


def test_explain_swallows_save_error_returns_result(monkeypatch):
    aid = _make_article()
    def boom(*a, **kw): raise RuntimeError("db boom")
    monkeypatch.setattr("app.routers.library.save_item", boom)
    with patch(
        "app.routers.library.explain_text",
        new=AsyncMock(return_value={
            "explanation": {"meaning": "x"}, "cefr_level": "B1", "cached": False,
        }),
    ):
        r = client.post(
            f"/library/articles/{aid}/explain",
            json={"text": "x", "kind": "word"},
            headers=HEADERS,
        )
    assert r.status_code == 200
    assert r.json()["explanation"]["meaning"] == "x"


def test_explain_returns_500_friendly_on_llm_failure():
    aid = _make_article()
    with patch(
        "app.routers.library.explain_text",
        new=AsyncMock(side_effect=RuntimeError("llm down")),
    ):
        r = client.post(
            f"/library/articles/{aid}/explain",
            json={"text": "x", "kind": "word"},
            headers=HEADERS,
        )
    assert r.status_code == 503


def test_explain_404_for_missing_article():
    r = client.post(
        "/library/articles/999999/explain",
        json={"text": "x", "kind": "word"},
        headers=HEADERS,
    )
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_v08_library_task6_explain.py -v`
Expected: 404 on POST `/library/articles/{id}/explain`

- [ ] **Step 3: Add explain endpoint**

```python
# app/routers/library.py — 顶部 import 区追加
from app.services.explain_service import explain_text, quick_phonetic, stream_sentence_explanation
from app.services.vocab_service import update_explanation
import json as _json

# 追加在 refetch 端点之后

class ExplainRequest(BaseModel):
    text: str
    kind: str  # word | sentence
    context: Optional[str] = None
    refresh: bool = False


@router.post("/library/articles/{article_id}/explain")
async def article_explain(
    article_id: int,
    req: ExplainRequest,
    user_id: str = Depends(get_current_user_id),
):
    article = library_service.get_article(article_id, user_id)
    if not article or article["status"] == "deleted":
        raise HTTPException(404, "文章不存在")
    if not req.text or not req.text.strip():
        raise HTTPException(400, "text is required")

    # 路由入口：占位写入 vocabulary
    _auto_save_library_vocab(
        user_id=user_id, text=req.text.strip(),
        kind=req.kind, article_id=article_id,
        context=req.context or "",
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
        logger.error("library_article_explain_failed: %s", e, exc_info=True)
        raise HTTPException(503, "解读服务暂时不可用，请稍后重试")

    # 回填 explanation_json
    try:
        update_explanation(
            user_id=user_id,
            source_text=req.text.strip(),
            source_ref=str(article_id),
            explanation_json=_json.dumps(result["explanation"], ensure_ascii=False),
            force=req.refresh,
        )
    except Exception as e:
        logger.warning("library_vocab_backfill_failed: %s", e)

    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_v08_library_task6_explain.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add app/routers/library.py tests/test_v08_library_task6_explain.py
git commit -m "$(cat <<'EOF'
feat(library): /library/articles/{id}/explain 同步解读 + 自动入库 + 回填 (V0.8 Step 6)

入口占位; LLM 完成后 update_explanation 回填; 入库异常吞日志.

Refs ##46

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: `/library/articles/{id}/explain/phonetic` IPA 秒出 + 入库

**Files:**
- Modify: `app/routers/library.py`（追加端点）
- Test: `tests/test_v08_library_task7_phonetic.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_v08_library_task7_phonetic.py
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from main import app
from app.models.db import engine, LibraryArticle, Vocabulary, init_db

USER = "test_user_v08_library_task7"
HEADERS = {"X-User-Id": USER}
client = TestClient(app)


@pytest.fixture(autouse=True)
def _cleanup():
    init_db()
    with OrmSession(engine) as s:
        s.query(LibraryArticle).filter(LibraryArticle.user_id.like("test_user_v08_library_%")).delete()
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_library_%")).delete()
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(LibraryArticle).filter(LibraryArticle.user_id.like("test_user_v08_library_%")).delete()
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_library_%")).delete()
        s.commit()


def _make_article():
    r = client.post(
        "/library/articles",
        json={"markdown": "# A\n\nbody.", "title": "A"},
        headers=HEADERS,
    )
    return r.json()["article"]["id"]


def test_phonetic_writes_word_vocab_placeholder():
    aid = _make_article()
    with patch("app.routers.library.quick_phonetic", return_value="/ˈhɛloʊ/"):
        r = client.post(
            f"/library/articles/{aid}/explain/phonetic",
            json={"text": "hello"},
            headers=HEADERS,
        )
    assert r.status_code == 200
    assert r.json()["phonetic"] == "/ˈhɛloʊ/"
    with OrmSession(engine) as s:
        v = s.query(Vocabulary).filter_by(
            user_id=USER, source_text="hello", source_ref=str(aid)
        ).first()
        assert v is not None
        assert v.item_type == "word"
        assert v.source_type == "library"


def test_phonetic_unknown_word_returns_null_but_still_saves():
    aid = _make_article()
    with patch("app.routers.library.quick_phonetic", return_value=None):
        r = client.post(
            f"/library/articles/{aid}/explain/phonetic",
            json={"text": "qwerty"},
            headers=HEADERS,
        )
    assert r.status_code == 200
    assert r.json()["phonetic"] is None
    with OrmSession(engine) as s:
        v = s.query(Vocabulary).filter_by(
            user_id=USER, source_text="qwerty", source_ref=str(aid)
        ).first()
        assert v is not None


def test_phonetic_empty_text_400():
    aid = _make_article()
    r = client.post(
        f"/library/articles/{aid}/explain/phonetic",
        json={"text": ""},
        headers=HEADERS,
    )
    assert r.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_v08_library_task7_phonetic.py -v`
Expected: 404 / endpoint missing

- [ ] **Step 3: Add phonetic endpoint**

```python
# app/routers/library.py — 追加在 article_explain 之后

class QuickPhoneticRequest(BaseModel):
    text: str


@router.post("/library/articles/{article_id}/explain/phonetic")
async def article_explain_phonetic(
    article_id: int,
    req: QuickPhoneticRequest,
    user_id: str = Depends(get_current_user_id),
):
    article = library_service.get_article(article_id, user_id)
    if not article or article["status"] == "deleted":
        raise HTTPException(404, "文章不存在")
    if not req.text or not req.text.strip():
        raise HTTPException(400, "text is required")

    _auto_save_library_vocab(
        user_id=user_id, text=req.text.strip(),
        kind="word", article_id=article_id,
    )
    return {"phonetic": quick_phonetic(req.text)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_v08_library_task7_phonetic.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/routers/library.py tests/test_v08_library_task7_phonetic.py
git commit -m "$(cat <<'EOF'
feat(library): /library/articles/{id}/explain/phonetic IPA 秒出 + 入库 (V0.8 Step 7)

仅点 IPA 也视为用户对该词感兴趣的信号 — 同步入 vocabulary 占位.

Refs ##46

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: `/library/articles/{id}/explain/stream` 流式 + 流末尾回填

**Files:**
- Modify: `app/routers/library.py`（追加流式端点）
- Test: `tests/test_v08_library_task8_stream.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_v08_library_task8_stream.py
import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from main import app
from app.models.db import engine, LibraryArticle, Vocabulary, init_db

USER = "test_user_v08_library_task8"
HEADERS = {"X-User-Id": USER}
client = TestClient(app)


@pytest.fixture(autouse=True)
def _cleanup():
    init_db()
    with OrmSession(engine) as s:
        s.query(LibraryArticle).filter(LibraryArticle.user_id.like("test_user_v08_library_%")).delete()
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_library_%")).delete()
        s.commit()
    yield
    with OrmSession(engine) as s:
        s.query(LibraryArticle).filter(LibraryArticle.user_id.like("test_user_v08_library_%")).delete()
        s.query(Vocabulary).filter(Vocabulary.user_id.like("test_user_v08_library_%")).delete()
        s.commit()


def _make_article():
    r = client.post(
        "/library/articles",
        json={"markdown": "# A\n\nIt's not rocket science.", "title": "A"},
        headers=HEADERS,
    )
    return r.json()["article"]["id"]


async def _fake_stream(*args, **kwargs):
    yield json.dumps({"field": "meaning", "value": "这又不是难事"})
    yield json.dumps({"field": "grammar", "value": "It is + ..."})
    yield json.dumps({"_done": True, "cefr_level": "B1",
                       "explanation": {"meaning": "这又不是难事", "grammar": "It is + ..."}})


def test_stream_writes_placeholder_at_entry():
    aid = _make_article()
    with patch("app.routers.library.stream_sentence_explanation", new=_fake_stream):
        r = client.post(
            f"/library/articles/{aid}/explain/stream",
            json={"text": "It's not rocket science."},
            headers=HEADERS,
        )
        # 消费 stream
        body = b"".join(r.iter_bytes()).decode()
    # 占位记录已存在
    with OrmSession(engine) as s:
        v = s.query(Vocabulary).filter_by(
            user_id=USER, source_text="It's not rocket science.", source_ref=str(aid),
        ).first()
        assert v is not None
        assert v.item_type == "sentence"
        # 回填后 explanation_json 非空
        assert v.explanation_json is not None
        assert "这又不是难事" in v.explanation_json


def test_stream_404_for_missing_article():
    r = client.post(
        "/library/articles/999999/explain/stream",
        json={"text": "x"},
        headers=HEADERS,
    )
    assert r.status_code == 404


def test_stream_empty_text_400():
    aid = _make_article()
    r = client.post(
        f"/library/articles/{aid}/explain/stream",
        json={"text": ""},
        headers=HEADERS,
    )
    assert r.status_code == 400


def test_stream_backfill_failure_does_not_break_stream(monkeypatch):
    aid = _make_article()
    def boom(*a, **kw): raise RuntimeError("backfill boom")
    monkeypatch.setattr("app.routers.library.update_explanation", boom)
    with patch("app.routers.library.stream_sentence_explanation", new=_fake_stream):
        r = client.post(
            f"/library/articles/{aid}/explain/stream",
            json={"text": "It's not rocket science."},
            headers=HEADERS,
        )
        body = b"".join(r.iter_bytes()).decode()
    # 流仍正常返回（不抛）
    assert "meaning" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_v08_library_task8_stream.py -v`
Expected: 404 / endpoint missing

- [ ] **Step 3: Add stream endpoint**

```python
# app/routers/library.py — 顶部 import 区追加
from fastapi.responses import StreamingResponse


class StreamExplainRequest(BaseModel):
    text: str
    refresh: bool = False


@router.post("/library/articles/{article_id}/explain/stream")
async def article_explain_stream(
    article_id: int,
    req: StreamExplainRequest,
    user_id: str = Depends(get_current_user_id),
):
    article = library_service.get_article(article_id, user_id)
    if not article or article["status"] == "deleted":
        raise HTTPException(404, "文章不存在")
    if not req.text or not req.text.strip():
        raise HTTPException(400, "text is required")

    text = req.text.strip()
    # 入口：占位写入（句子类）
    _auto_save_library_vocab(
        user_id=user_id, text=text, kind="sentence", article_id=article_id,
    )

    async def event_stream():
        final_explanation = None
        try:
            async for line in stream_sentence_explanation(text, user_id, force=req.refresh):
                # 边发边解析最后的 done 事件以拿到完整 explanation
                try:
                    obj = _json.loads(line)
                    if obj.get("_done") and obj.get("explanation"):
                        final_explanation = obj["explanation"]
                    if obj.get("_cached") and obj.get("explanation"):
                        final_explanation = obj["explanation"]
                except Exception:
                    pass
                yield line + "\n"
        except ValueError as e:
            yield _json.dumps({"_error": str(e)}, ensure_ascii=False) + "\n"
        except Exception as e:
            logger.error("library_stream_explain_failed: %s", e, exc_info=True)
            yield _json.dumps({"_error": "解读服务暂时不可用"}, ensure_ascii=False) + "\n"

        # 流末尾回填 explanation_json
        if final_explanation:
            try:
                update_explanation(
                    user_id=user_id,
                    source_text=text,
                    source_ref=str(article_id),
                    explanation_json=_json.dumps(final_explanation, ensure_ascii=False),
                    force=req.refresh,
                )
            except Exception as e:
                logger.warning("library_vocab_backfill_failed: %s", e)

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_v08_library_task8_stream.py -v`
Expected: 4 passed

- [ ] **Step 5: Run full backend regression**

Run: `pytest tests/ -v -k "library or vocab" --tb=short`
Expected: 全 PASS，无 BBC / 翻译相关回归

- [ ] **Step 6: Commit**

```bash
git add app/routers/library.py tests/test_v08_library_task8_stream.py
git commit -m "$(cat <<'EOF'
feat(library): /library/articles/{id}/explain/stream NDJSON 流式 + 末尾回填 (V0.8 Step 8)

入口占位; 流式时解析 _done/_cached 事件拿到 explanation; 回填异常不破流.

Refs ##46

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

后端阶段完成。下一阶段进入前端。

---

## Task 9: 前端依赖 + API 常量 + composable wrapper

**Files:**
- Modify: `frontend/package.json`（加 `marked`、`dompurify` 依赖）
- Modify: `frontend/src/config.js`（加 `API.LIBRARY` 常量）
- Create: `frontend/src/composables/useLibraryApi.js`（封装 7 个端点）

- [ ] **Step 1: Add frontend deps**

```bash
cd frontend && npm install marked dompurify && cd ..
```

校验 `frontend/package.json` 中已多出：
```json
"marked": "^15.x",
"dompurify": "^3.x"
```

- [ ] **Step 2: Bundle size check**

Run: `cd frontend && npm run build 2>&1 | tail -20`
Expected: 通过；新增 gzip 后约 +30KB，仍在 300KB 预算内。

- [ ] **Step 3: Add API.LIBRARY**

```javascript
// frontend/src/config.js — 在 API 对象内（按字母序列附近）追加
export const API = {
  ...
  LIBRARY: '/library',  // V0.8 文章库 · 技术文档阅读器
  ...
}
```

- [ ] **Step 4: Create useLibraryApi composable**

```javascript
// frontend/src/composables/useLibraryApi.js
import { useAuthFetch } from '@/composables/useAuthFetch'
import { API } from '@/config'

export function useLibraryApi() {
  const { authFetch, authFetchJson } = useAuthFetch()

  async function listArticles({ page = 1, pageSize = 20 } = {}) {
    const resp = await authFetch(
      `${API.LIBRARY}/articles?page=${page}&page_size=${pageSize}`
    )
    if (!resp.ok) throw new Error(`listArticles ${resp.status}`)
    return resp.json()
  }

  async function getArticle(id) {
    const resp = await authFetch(`${API.LIBRARY}/articles/${id}`)
    if (resp.status === 404) return null
    if (!resp.ok) throw new Error(`getArticle ${resp.status}`)
    const data = await resp.json()
    return data.article
  }

  async function importArticle({ url, markdown, title }) {
    const resp = await authFetch(`${API.LIBRARY}/articles`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, markdown, title }),
    })
    const data = await resp.json()
    if (!resp.ok) {
      // 400 + fetch_failed
      if (data?.detail?.error === 'fetch_failed') {
        const err = new Error(data.detail.hint || '抓取失败')
        err.code = 'fetch_failed'
        throw err
      }
      throw new Error(data?.detail || `importArticle ${resp.status}`)
    }
    return data
  }

  async function deleteArticle(id) {
    const resp = await authFetch(`${API.LIBRARY}/articles/${id}`, { method: 'DELETE' })
    return resp.status === 204
  }

  async function refetchArticle(id) {
    const resp = await authFetch(`${API.LIBRARY}/articles/${id}/refetch`, { method: 'POST' })
    const data = await resp.json()
    if (!resp.ok) {
      const err = new Error(data?.detail?.hint || 'refetch 失败')
      err.code = data?.detail?.error
      throw err
    }
    return data.article
  }

  async function explainPhonetic(articleId, text) {
    const resp = await authFetch(`${API.LIBRARY}/articles/${articleId}/explain/phonetic`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    })
    if (!resp.ok) return { phonetic: null }
    return resp.json()
  }

  async function explain(articleId, { text, kind, context, refresh = false }) {
    const resp = await authFetchJson(`${API.LIBRARY}/articles/${articleId}/explain`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, kind, context, refresh }),
    })
    return resp
  }

  /** 流式解读；onLine(jsonObj) 每行回调。 */
  async function explainStream(articleId, { text, refresh = false }, onLine) {
    const resp = await authFetch(`${API.LIBRARY}/articles/${articleId}/explain/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, refresh }),
    })
    if (!resp.ok || !resp.body) throw new Error(`explainStream ${resp.status}`)
    const reader = resp.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buf = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let nl
      while ((nl = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, nl).trim()
        buf = buf.slice(nl + 1)
        if (!line) continue
        try { onLine(JSON.parse(line)) } catch (e) { /* skip malformed */ }
      }
    }
    if (buf.trim()) {
      try { onLine(JSON.parse(buf.trim())) } catch (e) {}
    }
  }

  return {
    listArticles, getArticle, importArticle, deleteArticle, refetchArticle,
    explainPhonetic, explain, explainStream,
  }
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/config.js frontend/src/composables/useLibraryApi.js
git commit -m "$(cat <<'EOF'
feat(library/fe): 加 marked + dompurify + useLibraryApi composable (V0.8 Step 9)

7 个端点 client 封装；流式 NDJSON 按行回调；fetch_failed 错误码归一.

Refs ##46

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Library.vue 列表页 + AddArticleModal

**Files:**
- Create: `frontend/src/views/Library.vue`
- Create: `frontend/src/components/library/AddArticleModal.vue`
- Modify: `frontend/src/router/index.js`（加 `/library` 路由）
- Modify: `frontend/src/views/Home.vue` 或导航组件（加「文章库」入口卡片）

- [ ] **Step 1: Create Library.vue**

```vue
<!-- frontend/src/views/Library.vue -->
<template>
  <div class="library-page">
    <div class="library-header">
      <h1>我的文章库</h1>
      <button class="primary" @click="showAdd = true">+ 添加文章</button>
    </div>

    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="items.length === 0" class="empty">
      <p>还没有文章。点「+ 添加文章」从 URL 抓取或粘贴正文。</p>
    </div>

    <ul v-else class="article-list">
      <li v-for="a in items" :key="a.id" class="article-card" @click="open(a.id)">
        <div class="title">{{ a.title }}</div>
        <div class="meta">
          <span v-if="hostOf(a.source_url)">{{ hostOf(a.source_url) }} · </span>
          {{ a.word_count }} 词 · ~{{ readingTime(a.word_count) }} 分钟读
        </div>
        <div class="footer">
          <span class="time">{{ relTime(a.created_at) }}</span>
          <span class="vocab">💬 已沉淀 {{ a.vocab_count || 0 }} 个词</span>
          <button class="ghost" @click.stop="doDelete(a.id)">删除</button>
        </div>
      </li>
    </ul>

    <AddArticleModal
      v-if="showAdd"
      @close="showAdd = false"
      @imported="onImported"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useLibraryApi } from '@/composables/useLibraryApi'
import AddArticleModal from '@/components/library/AddArticleModal.vue'

const api = useLibraryApi()
const router = useRouter()

const items = ref([])
const loading = ref(true)
const showAdd = ref(false)

async function refresh() {
  loading.value = true
  try {
    const data = await api.listArticles({ page: 1, pageSize: 50 })
    items.value = data.items || []
  } finally {
    loading.value = false
  }
}

function open(id) {
  router.push(`/library/${id}`)
}

async function doDelete(id) {
  if (!confirm('确定删除这篇文章？已沉淀的生词会保留。')) return
  await api.deleteArticle(id)
  await refresh()
}

function onImported({ article, existing }) {
  showAdd.value = false
  if (existing) {
    alert('文章已在文章库中。')
  }
  router.push(`/library/${article.id}`)
}

function hostOf(url) {
  if (!url) return ''
  try { return new URL(url).host } catch { return '' }
}

function readingTime(wc) {
  return Math.max(1, Math.round(wc / 200))
}

function relTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const diff = (Date.now() - d.getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  return d.toLocaleDateString()
}

onMounted(refresh)
</script>

<style scoped>
.library-page { max-width: 900px; margin: 0 auto; padding: 24px 16px; }
.library-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.library-header h1 { margin: 0; }
.primary { background: var(--accent, #2563eb); color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; }
.ghost { background: transparent; border: 1px solid #ccc; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.state, .empty { text-align: center; padding: 60px 0; color: #888; }
.article-list { list-style: none; padding: 0; margin: 0; }
.article-card { padding: 16px; border-bottom: 1px solid #eee; cursor: pointer; }
.article-card:hover { background: #fafafa; }
.title { font-weight: 600; margin-bottom: 4px; }
.meta { font-size: 13px; color: #666; margin-bottom: 6px; }
.footer { display: flex; gap: 12px; align-items: center; font-size: 12px; color: #888; }
.footer .vocab { margin-left: auto; }
@media (max-width: 720px) {
  .library-page { padding: 16px 12px; }
}
</style>
```

- [ ] **Step 2: Create AddArticleModal.vue**

```vue
<!-- frontend/src/components/library/AddArticleModal.vue -->
<template>
  <div class="modal-mask" @click.self="$emit('close')">
    <div class="modal">
      <div class="tabs">
        <button :class="{ active: mode === 'url' }" @click="mode = 'url'">粘贴 URL</button>
        <button :class="{ active: mode === 'paste' }" @click="mode = 'paste'">粘贴正文</button>
      </div>

      <div v-if="mode === 'url'" class="form">
        <label>URL</label>
        <input v-model="url" placeholder="https://github.com/... 或任意英文文章链接" :disabled="loading" />
        <p v-if="error" class="error">{{ error }} <a href="#" @click.prevent="mode = 'paste'">切换到粘贴正文</a></p>
      </div>

      <div v-else class="form">
        <label>标题（必填）</label>
        <input v-model="title" placeholder="文章标题" :disabled="loading" />
        <label>正文（Markdown）</label>
        <textarea v-model="markdown" rows="10" placeholder="粘贴 Markdown 或纯文本..." :disabled="loading" />
        <p v-if="error" class="error">{{ error }}</p>
      </div>

      <div class="actions">
        <button class="ghost" @click="$emit('close')" :disabled="loading">取消</button>
        <button class="primary" @click="submit" :disabled="loading || !canSubmit">
          {{ loading ? '处理中…' : '抓取并加入' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useLibraryApi } from '@/composables/useLibraryApi'

const emit = defineEmits(['close', 'imported'])
const api = useLibraryApi()

const mode = ref('url')
const url = ref('')
const title = ref('')
const markdown = ref('')
const loading = ref(false)
const error = ref('')

const canSubmit = computed(() => {
  if (mode.value === 'url') return url.value.trim().length > 0
  return title.value.trim().length > 0 && markdown.value.trim().length > 0
})

async function submit() {
  error.value = ''
  loading.value = true
  try {
    const payload = mode.value === 'url'
      ? { url: url.value.trim() }
      : { markdown: markdown.value, title: title.value.trim() }
    const result = await api.importArticle(payload)
    emit('imported', result)
  } catch (e) {
    if (e.code === 'fetch_failed') {
      error.value = e.message || '抓取失败，请改用粘贴正文模式'
    } else {
      error.value = e.message || '导入失败'
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: white; border-radius: 8px; padding: 24px; width: 560px; max-width: 90vw; }
.tabs { display: flex; gap: 8px; margin-bottom: 16px; border-bottom: 1px solid #eee; }
.tabs button { padding: 8px 16px; background: none; border: none; cursor: pointer; border-bottom: 2px solid transparent; }
.tabs button.active { border-bottom-color: var(--accent, #2563eb); font-weight: 600; }
.form label { display: block; font-size: 13px; color: #555; margin-bottom: 4px; margin-top: 12px; }
.form input, .form textarea { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; font-family: inherit; }
.actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
.primary { background: var(--accent, #2563eb); color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; }
.primary:disabled { opacity: 0.5; cursor: not-allowed; }
.ghost { background: transparent; border: 1px solid #ccc; padding: 8px 16px; border-radius: 6px; cursor: pointer; }
.error { color: #d33; font-size: 13px; margin-top: 8px; }
</style>
```

- [ ] **Step 3: Add /library route**

```javascript
// frontend/src/router/index.js — 在路由数组中追加
{
  path: '/library',
  name: 'Library',
  component: () => import('@/views/Library.vue'),
  meta: { requiresAuth: true },
},
{
  path: '/library/:id',
  name: 'LibraryArticle',
  component: () => import('@/views/LibraryArticle.vue'),
  meta: { requiresAuth: true },
},
```

- [ ] **Step 4: Add navigation entry in Home.vue**

```bash
grep -n "翻译\|发音练习\|/translate\|/practice" frontend/src/views/Home.vue
```

仿照已有的入口卡片（如「翻译」），在 Home.vue 加一项：

```vue
<router-link to="/library" class="entry-card">
  <h3>文章库</h3>
  <p>导入英文技术文档，点词秒查，沉淀回顾</p>
</router-link>
```

具体 class / 容器以现有 Home.vue 风格为准；如果 Home.vue 使用配置数组渲染，则在数组中加一项。

- [ ] **Step 5: Smoke test in dev**

Run:
```bash
cd frontend && npm run dev &
DEV_PID=$!
sleep 4
curl -s http://localhost:5173/library | grep -q "Library\|文章库" && echo "OK" || echo "FAIL"
kill $DEV_PID
```

或手动浏览器打开 `http://localhost:5173/library`，应看到"我的文章库"标题与空状态。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/Library.vue frontend/src/components/library/AddArticleModal.vue frontend/src/router/index.js frontend/src/views/Home.vue
git commit -m "$(cat <<'EOF'
feat(library/fe): /library 列表页 + AddArticleModal (V0.8 Step 10)

URL / 粘贴两种 tab；fetch_failed 自动建议切粘贴；
列表带 vocab_count、阅读时长；Home 导航入口卡片.

Refs ##46

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: LibraryArticle.vue 骨架 + Markdown 渲染 + 点词浮气泡

**Files:**
- Create: `frontend/src/views/LibraryArticle.vue`
- Create: `frontend/src/components/library/MarkdownReader.vue`（隔离 marked + DOMPurify + 点词监听）
- Create: `frontend/src/components/library/WordPopover.vue`（浮气泡：IPA + 展开按钮）

- [ ] **Step 1: Create MarkdownReader.vue (only render, no interaction)**

```vue
<!-- frontend/src/components/library/MarkdownReader.vue -->
<template>
  <article class="md-reader" v-html="html" @click="onClick" @mouseup="onMouseUp"></article>
</template>

<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps({
  markdown: { type: String, required: true },
})
const emit = defineEmits(['word-click', 'selection'])

const html = computed(() => {
  const raw = marked.parse(props.markdown, { breaks: true, gfm: true })
  return DOMPurify.sanitize(raw)
})

function inCodeBlock(el) {
  while (el && el !== document.body) {
    if (el.tagName === 'CODE' || el.tagName === 'PRE') return true
    el = el.parentElement
  }
  return false
}

function onClick(e) {
  if (inCodeBlock(e.target)) return
  // 单击：若未选中文本，且点击位置在一个英文词上，触发 word-click
  const sel = window.getSelection()
  if (sel && sel.toString().trim()) return  // 选区交给 mouseup 处理
  const range = document.caretRangeFromPoint
    ? document.caretRangeFromPoint(e.clientX, e.clientY)
    : null
  if (!range) return
  const node = range.startContainer
  if (node.nodeType !== Node.TEXT_NODE) return
  const text = node.textContent || ''
  const idx = range.startOffset
  // 向左右扩展拿单词
  let l = idx, r = idx
  while (l > 0 && /[A-Za-z'-]/.test(text[l - 1])) l--
  while (r < text.length && /[A-Za-z'-]/.test(text[r])) r++
  const word = text.slice(l, r).trim()
  if (!word || word.length < 2) return
  // 上下文：句子（粗略以句末标点切）
  const before = text.slice(0, l)
  const after = text.slice(r)
  const ctxStart = Math.max(
    before.lastIndexOf('. '), before.lastIndexOf('? '), before.lastIndexOf('! '), 0
  )
  const ctxEndRel = (() => {
    for (const p of ['. ', '? ', '! ']) {
      const i = after.indexOf(p)
      if (i >= 0) return i + 1
    }
    return after.length
  })()
  const context = (text.slice(ctxStart, l) + word + text.slice(r, r + ctxEndRel)).trim()
  emit('word-click', { word, context, x: e.clientX, y: e.clientY })
}

function onMouseUp(e) {
  if (inCodeBlock(e.target)) return
  const sel = window.getSelection()
  const text = sel ? sel.toString().trim() : ''
  // 单词级（< 2 个词）走点词；多词出选区菜单
  if (!text || text.split(/\s+/).length < 2) return
  const range = sel.getRangeAt(0)
  const rect = range.getBoundingClientRect()
  emit('selection', { text, x: rect.left + rect.width / 2, y: rect.bottom })
}
</script>

<style scoped>
.md-reader { max-width: 720px; margin: 0 auto; line-height: 1.7; font-size: 16px; }
.md-reader :deep(h1) { font-size: 28px; margin: 32px 0 16px; }
.md-reader :deep(h2) { font-size: 22px; margin: 24px 0 12px; }
.md-reader :deep(h3) { font-size: 18px; margin: 20px 0 8px; }
.md-reader :deep(p) { margin: 0 0 16px; }
.md-reader :deep(code) { background: #f5f5f5; padding: 2px 4px; border-radius: 3px; font-size: 14px; user-select: text; cursor: text; }
.md-reader :deep(pre) { background: #f5f5f5; padding: 12px; border-radius: 6px; overflow-x: auto; user-select: text; cursor: text; }
.md-reader :deep(pre code) { background: none; padding: 0; }
.md-reader :deep(a) { color: var(--accent, #2563eb); }
.md-reader :deep(blockquote) { border-left: 3px solid #ddd; padding-left: 12px; color: #666; margin: 16px 0; }
</style>
```

- [ ] **Step 2: Create WordPopover.vue**

```vue
<!-- frontend/src/components/library/WordPopover.vue -->
<template>
  <div class="popover" :style="{ left: x + 'px', top: y + 'px' }">
    <div class="ipa">{{ word }} <span v-if="phonetic">{{ phonetic }}</span></div>
    <div v-if="!phonetic && !loading" class="hint">未知音标</div>
    <div v-if="loading" class="hint">加载中…</div>
    <div class="actions">
      <button @click="$emit('expand')">展开解读</button>
      <button class="ghost" @click="$emit('close')">关闭</button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  word: String,
  phonetic: { type: [String, null], default: null },
  loading: Boolean,
  x: Number,
  y: Number,
})
defineEmits(['expand', 'close'])
</script>

<style scoped>
.popover { position: fixed; background: white; border: 1px solid #ddd; border-radius: 6px; padding: 8px 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); z-index: 100; max-width: 320px; }
.ipa { font-weight: 600; margin-bottom: 6px; }
.ipa span { font-weight: 400; color: #666; margin-left: 8px; }
.hint { color: #888; font-size: 13px; margin-bottom: 6px; }
.actions { display: flex; gap: 6px; }
.actions button { padding: 4px 10px; font-size: 13px; border: none; background: var(--accent, #2563eb); color: white; border-radius: 4px; cursor: pointer; }
.actions .ghost { background: transparent; border: 1px solid #ccc; color: #333; }
</style>
```

- [ ] **Step 3: Create LibraryArticle.vue skeleton**

```vue
<!-- frontend/src/views/LibraryArticle.vue -->
<template>
  <div class="article-page">
    <div class="topbar">
      <button class="ghost" @click="$router.push('/library')">← 返回</button>
      <span class="title">{{ article?.title }}</span>
    </div>

    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="!article" class="state">文章不存在或已删除</div>

    <div v-else class="layout">
      <MarkdownReader
        :markdown="article.markdown"
        @word-click="onWordClick"
        @selection="onSelection"
      />
      <!-- 侧栏（Task 13 实现）-->
      <aside class="sidebar"><h3>本文沉淀</h3><p class="hint">Task 13 填充</p></aside>
    </div>

    <WordPopover
      v-if="popover"
      :word="popover.word"
      :phonetic="popover.phonetic"
      :loading="popover.loading"
      :x="popover.x"
      :y="popover.y"
      @expand="onExpand"
      @close="popover = null"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useLibraryApi } from '@/composables/useLibraryApi'
import MarkdownReader from '@/components/library/MarkdownReader.vue'
import WordPopover from '@/components/library/WordPopover.vue'

const route = useRoute()
const api = useLibraryApi()

const article = ref(null)
const loading = ref(true)
const popover = ref(null)

async function load() {
  loading.value = true
  try {
    article.value = await api.getArticle(route.params.id)
  } finally {
    loading.value = false
  }
}

async function onWordClick({ word, context, x, y }) {
  popover.value = { word, context, phonetic: null, loading: true, x, y }
  const { phonetic } = await api.explainPhonetic(article.value.id, word)
  if (popover.value && popover.value.word === word) {
    popover.value.phonetic = phonetic
    popover.value.loading = false
  }
}

function onSelection({ text, x, y }) {
  // Task 12 接入选区菜单
  console.debug('selection', text, x, y)
}

function onExpand() {
  // Task 12 接入：触发 explain 完整解读
  console.debug('expand', popover.value)
}

onMounted(load)
</script>

<style scoped>
.article-page { padding: 24px 16px; max-width: 1280px; margin: 0 auto; }
.topbar { display: flex; align-items: center; gap: 16px; margin-bottom: 24px; }
.topbar .title { font-weight: 600; }
.ghost { background: transparent; border: 1px solid #ccc; padding: 6px 12px; border-radius: 4px; cursor: pointer; }
.state { text-align: center; padding: 60px 0; color: #888; }
.layout { display: grid; grid-template-columns: 1fr 320px; gap: 32px; }
.sidebar { background: #fafafa; padding: 16px; border-radius: 6px; height: fit-content; }
.sidebar h3 { margin-top: 0; }
.hint { color: #888; font-size: 13px; }
@media (max-width: 1024px) {
  .layout { grid-template-columns: 1fr; }
  .sidebar { position: fixed; bottom: 0; left: 0; right: 0; max-height: 50vh; overflow-y: auto; border-top: 1px solid #ddd; border-radius: 0; }
}
</style>
```

- [ ] **Step 4: Manual smoke test**

```bash
cd frontend && npm run dev
```

1. 浏览器到 `/library`，导入一篇粘贴正文（标题"测试", 正文 `# Hello\n\nThis is a banter test sentence.`）
2. 点进详情页
3. 单击 `banter` → 应弹气泡显示 IPA（若 banter 不在 eng_to_ipa 字典则"未知音标"）
4. 选中 `banter test sentence` → 控制台应打印 selection

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/LibraryArticle.vue frontend/src/components/library/MarkdownReader.vue frontend/src/components/library/WordPopover.vue
git commit -m "$(cat <<'EOF'
feat(library/fe): LibraryArticle 骨架 + MarkdownReader + 点词浮气泡 (V0.8 Step 11)

marked + DOMPurify 渲染；caretRangeFromPoint 精准定位单词；
代码块整块 user-select=text 但不响应点词；句级上下文用句末标点切分。

Refs ##46

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: 选区菜单 + 完整 explain 浮层（流式）

**Files:**
- Create: `frontend/src/components/library/SelectionMenu.vue`
- Create: `frontend/src/components/library/ExplanationCard.vue`（共享渲染组件，BBC spec 后续也会复用）
- Modify: `frontend/src/views/LibraryArticle.vue`（接入 selection / expand）

- [ ] **Step 1: Create SelectionMenu.vue**

```vue
<!-- frontend/src/components/library/SelectionMenu.vue -->
<template>
  <div class="menu" :style="{ left: x + 'px', top: y + 'px' }">
    <button @click="$emit('translate')">翻译</button>
    <!-- 后续 Step 加：高亮 / 评论 -->
  </div>
</template>

<script setup>
defineProps({ x: Number, y: Number })
defineEmits(['translate'])
</script>

<style scoped>
.menu { position: fixed; background: #222; color: white; border-radius: 6px; padding: 6px; display: flex; gap: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.2); z-index: 100; transform: translate(-50%, 8px); }
.menu button { background: transparent; border: none; color: white; padding: 6px 12px; cursor: pointer; font-size: 13px; border-radius: 4px; }
.menu button:hover { background: rgba(255,255,255,0.15); }
</style>
```

- [ ] **Step 2: Create ExplanationCard.vue (shared renderer)**

```vue
<!-- frontend/src/components/library/ExplanationCard.vue -->
<template>
  <div class="card">
    <button class="close" @click="$emit('close')">×</button>
    <div class="source">{{ sourceText }}</div>
    <div v-if="explanation" class="body">
      <section v-if="explanation.meaning">
        <h4>含义</h4>
        <p>{{ explanation.meaning }}</p>
      </section>
      <section v-if="explanation.grammar">
        <h4>语法</h4>
        <p>{{ explanation.grammar }}</p>
      </section>
      <section v-if="explanation.phrases && explanation.phrases.length">
        <h4>短语</h4>
        <ul><li v-for="(p, i) in explanation.phrases" :key="i">{{ p.phrase || p }}: {{ p.meaning || '' }}</li></ul>
      </section>
      <section v-if="explanation.liaison && explanation.liaison.length">
        <h4>连读</h4>
        <ul><li v-for="(l, i) in explanation.liaison" :key="i">{{ l }}</li></ul>
      </section>
    </div>
    <div v-else-if="loading" class="hint">加载中…</div>
    <div v-else-if="error" class="error">{{ error }} <button class="ghost" @click="$emit('retry')">重试</button></div>
  </div>
</template>

<script setup>
defineProps({
  sourceText: String,
  explanation: { type: Object, default: null },
  loading: Boolean,
  error: { type: String, default: '' },
})
defineEmits(['close', 'retry'])
</script>

<style scoped>
.card { background: white; border: 1px solid #ddd; border-radius: 8px; padding: 16px 20px; box-shadow: 0 8px 24px rgba(0,0,0,0.12); max-width: 480px; position: fixed; right: 24px; bottom: 24px; max-height: 70vh; overflow-y: auto; z-index: 200; }
.close { position: absolute; top: 8px; right: 12px; background: none; border: none; font-size: 20px; cursor: pointer; color: #888; }
.source { font-weight: 600; margin-bottom: 12px; padding-right: 24px; }
.body section { margin-bottom: 12px; }
.body h4 { margin: 0 0 4px; font-size: 13px; color: #666; }
.body p, .body ul { margin: 0; font-size: 14px; }
.body ul { padding-left: 18px; }
.hint, .error { color: #888; padding: 12px 0; }
.error { color: #d33; }
.ghost { margin-left: 8px; background: transparent; border: 1px solid #ccc; padding: 2px 8px; border-radius: 3px; cursor: pointer; font-size: 12px; }
</style>
```

- [ ] **Step 3: Wire selection + expand in LibraryArticle.vue**

替换 LibraryArticle.vue 中 `onSelection` 与 `onExpand` 的实现，并加 SelectionMenu / ExplanationCard：

```vue
<!-- 在 template 内加 -->
<SelectionMenu
  v-if="selectionMenu"
  :x="selectionMenu.x"
  :y="selectionMenu.y"
  @translate="onSelectionTranslate"
/>
<ExplanationCard
  v-if="explainPanel"
  :source-text="explainPanel.text"
  :explanation="explainPanel.explanation"
  :loading="explainPanel.loading"
  :error="explainPanel.error"
  @close="explainPanel = null"
  @retry="retryExplain"
/>
```

```vue
<!-- script setup 内补 -->
import SelectionMenu from '@/components/library/SelectionMenu.vue'
import ExplanationCard from '@/components/library/ExplanationCard.vue'

const selectionMenu = ref(null)
const explainPanel = ref(null)

function onSelection({ text, x, y }) {
  selectionMenu.value = { text, x, y }
}

async function onSelectionTranslate() {
  const { text } = selectionMenu.value
  const isSentence = /[.!?]/.test(text)
  selectionMenu.value = null
  await runExplain({ text, kind: isSentence ? 'sentence' : 'phrase' })
}

async function onExpand() {
  const { word, context } = popover.value
  popover.value = null
  await runExplain({ text: word, kind: 'word', context })
}

async function runExplain({ text, kind, context }) {
  explainPanel.value = { text, explanation: null, loading: true, error: '', kind, context }
  try {
    if (kind === 'sentence') {
      let acc = {}
      await api.explainStream(article.value.id, { text }, (line) => {
        if (line.field) acc[line.field] = line.value
        if (line.explanation) acc = { ...acc, ...line.explanation }
        if (line._error) throw new Error(line._error)
        if (explainPanel.value && explainPanel.value.text === text) {
          explainPanel.value.explanation = { ...acc }
        }
      })
      if (explainPanel.value) explainPanel.value.loading = false
    } else {
      const result = await api.explain(article.value.id, { text, kind, context })
      if (explainPanel.value) {
        explainPanel.value.explanation = result.explanation
        explainPanel.value.loading = false
      }
    }
  } catch (e) {
    if (explainPanel.value) {
      explainPanel.value.loading = false
      explainPanel.value.error = e.message || '解读失败'
    }
  }
}

async function retryExplain() {
  if (!explainPanel.value) return
  const { text, kind, context } = explainPanel.value
  await runExplain({ text, kind, context })
}
```

- [ ] **Step 4: Manual smoke test**

```bash
cd frontend && npm run dev
```

1. 在文章中选中 `It's not rocket science.` → 工具条出现「翻译」
2. 点「翻译」→ 右下角浮层流式渲染 meaning / grammar / phrases
3. 单击 `banter` → 气泡 IPA → 「展开解读」→ 右下角浮层渲染 word 解读
4. 模拟网络异常（DevTools throttle to offline）→ 浮层显示「解读失败」+ 重试按钮

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/library/SelectionMenu.vue frontend/src/components/library/ExplanationCard.vue frontend/src/views/LibraryArticle.vue
git commit -m "$(cat <<'EOF'
feat(library/fe): 选区菜单 + 流式 explain 浮层 + 共享 ExplanationCard (V0.8 Step 12)

ExplanationCard 抽取为可复用组件，BBC spec 后续 /vocabulary 页一并使用.

Refs ##46

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: 「本文沉淀」侧栏 + 原地展开

**Files:**
- Modify: `frontend/src/views/LibraryArticle.vue`（加载 vocab + 渲染侧栏）
- Create: `frontend/src/components/library/VocabSidebar.vue`

vocabulary 接口已存在 (`GET /vocab`)，本 Step 仅前端工作。

- [ ] **Step 1: Verify backend GET /vocab supports source_type filter**

```bash
grep -n "source_type\|source_ref" app/routers/vocab.py | head -10
```

如已支持（按 BBC spec Task 3 已合或本 spec 范围内补一个 query 参数），跳过。
若不支持，先开一个 micro-PR 加上 query：

```python
# app/routers/vocab.py
@router.get("/vocab")
async def list_vocab(
    source_type: Optional[str] = Query(None),
    source_ref: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
):
    items = list_items(
        user_id=user_id,
        # 现有 list_items 暂未支持 source_type 过滤，但支持 source_ref；
        # MVP 用 source_ref 即可定位本文（library 已经天然以 article_id 为 ref）
        source_ref=source_ref,
        limit=limit,
    )
    if source_type:
        items = [it for it in items if it["source_type"] == source_type]
    return {"items": items}
```

> 注：若 BBC spec Task 2/3 已实装 `list_items(source_type=...)` 直接传参更优；本 Step 用前后兼容写法。

- [ ] **Step 2: Create VocabSidebar.vue**

```vue
<!-- frontend/src/components/library/VocabSidebar.vue -->
<template>
  <aside class="sidebar">
    <h3>本文沉淀 ({{ items.length }})</h3>
    <div v-if="loading" class="hint">加载中…</div>
    <div v-else-if="items.length === 0" class="hint">还没有沉淀的词</div>
    <ul v-else>
      <li v-for="it in items" :key="it.id" class="vocab-item">
        <div class="row" @click="toggle(it.id)">
          <span class="text">{{ it.source_text }}</span>
          <span class="badge" :class="badgeClass(it)">{{ badgeText(it) }}</span>
        </div>
        <div v-if="expanded[it.id]" class="expanded">
          <ExplanationCard
            v-if="parsed(it)"
            :source-text="it.source_text"
            :explanation="parsed(it)"
            :loading="false"
            :inline="true"
          />
          <div v-else class="hint">解读尚未生成 <button class="ghost" @click="pull(it)">点击拉取</button></div>
        </div>
      </li>
    </ul>
  </aside>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useAuthFetch } from '@/composables/useAuthFetch'
import { useLibraryApi } from '@/composables/useLibraryApi'
import { API } from '@/config'
import ExplanationCard from './ExplanationCard.vue'

const props = defineProps({
  articleId: { type: [Number, String], required: true },
})

const { authFetch } = useAuthFetch()
const api = useLibraryApi()

const items = ref([])
const loading = ref(true)
const expanded = ref({})

async function refresh() {
  loading.value = true
  const resp = await authFetch(
    `/vocab?source_type=library&source_ref=${props.articleId}&limit=200`
  )
  const data = await resp.json()
  items.value = data.items || []
  loading.value = false
}

function toggle(id) {
  expanded.value[id] = !expanded.value[id]
}

function parsed(it) {
  if (!it.explanation_json) return null
  try { return JSON.parse(it.explanation_json) } catch { return null }
}

function badgeClass(it) {
  return parsed(it) ? 'ready' : 'pending'
}
function badgeText(it) {
  return parsed(it) ? 'ready' : 'pending'
}

async function pull(it) {
  // pending 条目主动拉一次完整解读
  const kind = it.item_type === 'word' ? 'word' : (it.item_type === 'sentence' ? 'sentence' : 'phrase')
  try {
    await api.explain(props.articleId, { text: it.source_text, kind })
  } catch (e) { /* 已写入日志 */ }
  await refresh()
}

defineExpose({ refresh })

watch(() => props.articleId, refresh, { immediate: false })
onMounted(refresh)
</script>

<style scoped>
.sidebar { background: #fafafa; padding: 16px; border-radius: 6px; height: fit-content; max-height: 80vh; overflow-y: auto; }
.sidebar h3 { margin-top: 0; }
.hint { color: #888; font-size: 13px; }
.vocab-item { padding: 8px 0; border-bottom: 1px solid #eee; }
.row { display: flex; align-items: center; justify-content: space-between; cursor: pointer; }
.text { font-weight: 500; }
.badge { font-size: 11px; padding: 2px 6px; border-radius: 3px; }
.badge.ready { background: #e0f3e6; color: #2a7a3a; }
.badge.pending { background: #fef3c7; color: #92400e; }
.expanded { padding: 8px 0 4px 8px; }
.ghost { background: transparent; border: 1px solid #ccc; padding: 2px 8px; border-radius: 3px; cursor: pointer; font-size: 12px; }
</style>
```

- [ ] **Step 3: Replace placeholder sidebar in LibraryArticle.vue**

```vue
<!-- 替换原 <aside> 占位 -->
<VocabSidebar
  v-if="article"
  ref="sidebarRef"
  :article-id="article.id"
/>
```

```javascript
import VocabSidebar from '@/components/library/VocabSidebar.vue'
const sidebarRef = ref(null)

// 在 runExplain 完成后调侧栏刷新（让新解读立刻可见）
// runExplain 函数末尾追加：
// if (sidebarRef.value) sidebarRef.value.refresh()
```

将 runExplain 的两个分支（流式 / 非流式）成功路径末尾加 `sidebarRef.value?.refresh()`。

- [ ] **Step 4: Manual smoke test**

1. 进文章，点几个词、选一句翻译
2. 右侧「本文沉淀」实时刷出条目（状态徽章 pending → ready）
3. 点条目 → 原地展开 ExplanationCard
4. 模拟 pending 条目（解读流式时关闭浮层）→ 列表条目仍为 pending；点条目 → 「点击拉取」→ 拉完变 ready

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/library/VocabSidebar.vue frontend/src/views/LibraryArticle.vue app/routers/vocab.py
git commit -m "$(cat <<'EOF'
feat(library/fe): 本文沉淀侧栏 + pending 重拉 + 实时刷新 (V0.8 Step 13)

vocab.py 加 source_type query；侧栏挂在文章详情；
ExplanationCard 复用 inline 渲染；pending 条目支持主动拉取.

Refs ##46

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: 移动端降级（最小可用）

**Files:**
- Modify: `frontend/src/views/Library.vue`（列表移动样式）
- Modify: `frontend/src/views/LibraryArticle.vue`（侧栏 → 底部 sheet）
- Modify: `frontend/src/components/library/MarkdownReader.vue`（移动端点词触发 touchend）

PC 优先已基本就位；本 Step 处理手机能用：

- [ ] **Step 1: Make sidebar a bottom sheet on mobile**

LibraryArticle.vue style 已包含 `@media (max-width: 1024px)` 的基础规则；
追加：底部加一个按钮"本文沉淀 (n)" 控制 sheet 显隐。

```vue
<!-- LibraryArticle.vue template 内移动端开关 -->
<button v-if="isMobile" class="sheet-toggle" @click="sheetOpen = !sheetOpen">
  本文沉淀
</button>
```

```javascript
const isMobile = ref(window.matchMedia('(max-width: 1024px)').matches)
const sheetOpen = ref(false)
window.addEventListener('resize', () => {
  isMobile.value = window.matchMedia('(max-width: 1024px)').matches
})
```

`.sidebar` 移动端样式追加：

```css
@media (max-width: 1024px) {
  .sidebar { display: none; }
  .sidebar.open { display: block; }
}
.sheet-toggle { position: fixed; bottom: 16px; right: 16px; background: var(--accent, #2563eb); color: white; border: none; padding: 10px 16px; border-radius: 20px; z-index: 50; }
```

- [ ] **Step 2: touchend support in MarkdownReader**

```javascript
// MarkdownReader.vue script setup — 追加在 onClick 之后
function onTouchEnd(e) {
  // 用 touch 末点作为 click 触发；caretRangeFromPoint 需要兼容
  if (e.changedTouches && e.changedTouches[0]) {
    const t = e.changedTouches[0]
    onClick({ clientX: t.clientX, clientY: t.clientY, target: e.target })
  }
}
```

```vue
<article ... @touchend="onTouchEnd">
```

- [ ] **Step 3: Manual smoke test on phone**

DevTools 切到 iPhone 模拟：进文章 → 点底部"本文沉淀"展开 sheet → 单击词应能弹气泡 → 选区菜单可触发。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/Library.vue frontend/src/views/LibraryArticle.vue frontend/src/components/library/MarkdownReader.vue
git commit -m "$(cat <<'EOF'
feat(library/fe): 移动端降级 — 侧栏改 sheet + touchend 点词 (V0.8 Step 14)

PC 优先已就位，移动端确保能看能查；不做独立移动布局.

Refs ##46

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: 文档同步 — CLAUDE.md / README / 架构图

**Files:**
- Modify: `.claude/CLAUDE.md`（数据表清单 + API 接口清单 + 版本状态）
- Modify: `README.md`（模块介绍 + 部署说明无变化但可补一句）
- Modify: `docs/architecture/c4-container.md`（加 /library 模块）
- Create: `docs/architecture/flows/library-explain-vocab-flow.md`

- [ ] **Step 1: Update CLAUDE.md 数据表清单**

打开 `.claude/CLAUDE.md`，在「数据表清单」表格追加：

```
| library_articles | V0.8 | 用户自带技术文档的快照（URL/粘贴），与 BBC `bbc_eaw_episodes` 并列 |
```

- [ ] **Step 2: Update CLAUDE.md API 接口清单**

在「API 接口清单」表格追加 7 行：

```
| `/library/articles` | POST | V0.8 | 导入文章（URL/粘贴二选一），201 新建 / 200 已存 |
| `/library/articles` | GET | V0.8 | 文章列表（分页），含 vocab_count |
| `/library/articles/{id}` | GET | V0.8 | 文章详情含 markdown 全文 |
| `/library/articles/{id}` | DELETE | V0.8 | 软删；vocabulary 不级联 |
| `/library/articles/{id}/refetch` | POST | V0.8 | 强制重抓（仅 URL 类） |
| `/library/articles/{id}/explain` | POST | V0.8 | 单词/句解读，入口写 vocab 占位 + 完成回填 |
| `/library/articles/{id}/explain/phonetic` | POST | V0.8 | IPA 秒出，同步入 vocab |
| `/library/articles/{id}/explain/stream` | POST | V0.8 | NDJSON 流式句解读 + 流末回填 |
```

- [ ] **Step 3: Update CLAUDE.md 版本状态**

```diff
- ### 当前版本：V0.7（已完成）
+ ### 当前版本：V0.8（开发中）
```

「已完成版本功能」追加：
```
V0.8  🚧  文章库（技术文档阅读器） · BBC 改名 + 自动入库 + 独立 /vocabulary（与本 spec 并行）
```

「下一版本预告」更新到 V0.9。

- [ ] **Step 4: Update CLAUDE.md 项目目录结构**

在 `app/routers/` 与 `app/services/` / `frontend/src/views/` 增加：

```
├── app/
│   ├── routers/
│   │   └── library.py          # /library/*（V0.8+）
│   └── services/
│       └── library_service.py  # 文章抓取入库 / 列表 / 详情 / 软删（V0.8+）
├── frontend/src/views/
│   ├── Library.vue             # 文章库列表（V0.8+）
│   └── LibraryArticle.vue      # 阅读详情 + 点词翻译（V0.8+）
```

- [ ] **Step 5: README.md 模块介绍**

打开 `README.md`，搜「翻译」段落，在其后追加一段：

```markdown
### 文章库（`/library`，V0.8+）

把任意英文技术文档（GitHub README、博客、文档站）粘贴 URL 或正文导入个人文章库；
阅读时点词秒出 IPA，选区一键翻译解读，所有解读自动沉淀到生词本，
右侧侧栏「本文沉淀」原地复习。

主要依赖：`trafilatura`（任意 URL 提正文输出 Markdown）、`marked` + `DOMPurify`（前端渲染）。
```

- [ ] **Step 6: Update c4-container.md**

```bash
cat docs/architecture/c4-container.md | head -50
```

在容器图的 Backend 部分加 `library_service`、`library_router`；
在 Frontend 部分加 `Library.vue / LibraryArticle.vue`；
在外部依赖部分加 `trafilatura` 抓取链。
（具体格式按现有 mermaid / ASCII 图风格补。）

- [ ] **Step 7: Create library-explain-vocab-flow.md**

```markdown
# `/library` 阅读 → 解读 → 入库 数据流

> V0.8 文章库技术文档阅读器的核心闭环。

\`\`\`
用户在 /library/:id 阅读 → 点词 / 选区
        │
        ▼
前端 useLibraryApi → POST /library/articles/{id}/explain*
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│ app/routers/library.py 入口                             │
│  · _auto_save_library_vocab(占位写 vocabulary)          │
│      source_type='library', source_ref=str(article_id)  │
│      explanation_json=None                              │
│  · 任何入库异常仅 logger.warning + 吞                    │
└─────────────────────────────────────────────────────────┘
        │
        ▼
app/services/explain_service.py
  · ExplanationCache 命中 → 秒返
  · 未命中 → LLM 生成 → 写 ExplanationCache
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│ 完成（同步 / 流式末尾）→ vocab_service.update_explanation │
│  · 唯一键 (user_id, source_text, source_ref) 定位        │
│  · 默认仅在 explanation_json IS NULL 时写入              │
│  · 软删条目也写（不丢历史）                              │
└─────────────────────────────────────────────────────────┘
        │
        ▼
前端 ExplanationCard 流式 / 整体渲染；
VocabSidebar 刷新读到回填结果。
\`\`\`

## 关键不变式

1. 任何入库 / 回填异常**不**影响解读返回
2. 解读永不依赖前端 keep-alive（地铁切走照样有记录）
3. 文章软删 → vocabulary 不级联（已沉淀的语言点跟文章生命周期解耦）
4. 同一 URL 同一用户**至多一条** library_articles 记录（唯一索引）
```

- [ ] **Step 8: Commit**

```bash
git add .claude/CLAUDE.md README.md docs/architecture/c4-container.md docs/architecture/flows/library-explain-vocab-flow.md
git commit -m "$(cat <<'EOF'
docs(library): CLAUDE.md / README / 架构图 / 数据流文档同步 (V0.8 Step 15)

Refs ##46

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 16: 全量回归 + 手动 E2E 验收

**Files:** 仅运行测试 + 录验收清单。

- [ ] **Step 1: 后端全量回归**

Run: `pytest tests/ -v --tb=short 2>&1 | tail -50`

Expected:
- 全 PASS（含 `test_v08_library_*` 8 个新文件）
- 无 BBC / translate / vocab 既有用例回归

如有失败：定位原因，开 micro-PR 修复，不要跳过测试。

- [ ] **Step 2: 前端 build & bundle 检查**

Run:
```bash
cd frontend && npm run build 2>&1 | tail -30
```

Expected: 构建成功；gzip 总大小 < 300KB（300KB 硬预算见 `.github/workflows/`）；新增 marked + dompurify gzip ≈ +30KB。

- [ ] **Step 3: 手动 E2E 验收清单**

按以下顺序在 dev 服务器（PC 浏览器 + 手机模拟）跑一遍：

1. 登录 → 进 `/library` 应看到「我的文章库」空状态
2. 点「+ 添加文章」→ 选 URL → 粘 `https://github.com/github/spec-kit/blob/main/spec-driven.md`
3. 抓取成功 → 跳转 `/library/<id>` 详情页 → 看到 Markdown 渲染正文（标题层级、代码块、链接）
4. 单击 `intent` → 浮气泡出现 → 显示 IPA → 「展开解读」→ 右下角浮层渲染 word 解读
5. 选中 `Spec-Driven Development is an approach` → 工具条出现「翻译」→ 点击 → 流式 sentence 解读
6. 切到 `/library` 列表 → 这篇出现在头 → `已沉淀 3 个词`
7. 进文章 → 右侧「本文沉淀 (3)」侧栏列出三条 → 点条目原地展开 ExplanationCard
8. 关闭浮层后切到 `/library` → 点删除 → 回详情 404 → 切「我的文章库」看不到 → 但 `GET /vocab?source_type=library&source_ref=<id>` 三条仍在（vocabulary 未级联）
9. 粘贴正文模式：title=「测试」, 正文=「# Banter\n\nThis is a banter test.」→ 列表新增；点词解读正常
10. 抓取失败演示：模拟 trafilatura mock raise（或粘个公司内网 URL）→ UI 弹「抓取失败，请改用粘贴正文」+ 自动切 tab
11. 手机模拟：底部「本文沉淀」按钮可展开 sheet；touch 点词可弹气泡

- [ ] **Step 4: 关闭 tracking issue**

```bash
gh issue close <tracking-issue-number> --comment "V0.8 文章库 ship 完成，所有 Step 验收通过。验收清单见 plan Task 16。"
```

- [ ] **Step 5: ROADMAP.md 与版本号**

ROADMAP.md 由 Human 维护（CLAUDE.md 已声明），不动。
`VERSION` 文件由 Human 在 ship 时升级。

- [ ] **Step 6: 终结提交（如有最终调整）**

如 Step 1-3 修了零星问题，做最后一个 commit：

```bash
git add -A
git commit -m "$(cat <<'EOF'
chore(library): V0.8 ship 验收清单完成 (Step 16)

Closes ##46

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## 完成 ✅

V0.8 文章库 · 技术文档阅读器 全部 16 Step 完成。

如后续要做的下一版（高亮 / 评论 / 阅读进度），开新 spec：
`docs/superpowers/specs/<date>-library-annotation-design.md`，引用本 plan 作为基线。
