"""文章库服务 — 用户自带技术文档的导入、管理与列表

支持两种导入方式：
  - URL 模式：trafilatura 提取正文 Markdown + meta
  - Markdown 模式：直接粘贴正文
"""
import json
import logging
from typing import Dict, List, Optional

from sqlalchemy import func as sql_func
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.exc import IntegrityError

from app.models.db import engine, LibraryArticle, Vocabulary
from app.logger import get_logger

logger = get_logger("library_service")

MAX_MARKDOWN_LEN = 100_000


def _extract_from_url(url: str):
    """Extract markdown + meta from URL using trafilatura.

    Returns (markdown: str, meta: dict).
    Raises ValueError("fetch_failed") on any failure.
    """
    try:
        import trafilatura
    except ImportError:
        raise ValueError("trafilatura not installed")

    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise ValueError("fetch_failed")

    result = trafilatura.extract(
        downloaded,
        output_format="markdown",
        include_links=True,
        include_tables=True,
        with_metadata=True,
    )
    if not result:
        raise ValueError("fetch_failed")

    meta = {}
    try:
        meta_obj = trafilatura.extract_metadata(downloaded)
        if meta_obj:
            meta = {
                "author": meta_obj.author,
                "site_name": meta_obj.sitename,
                "title": meta_obj.title,
            }
    except Exception:
        pass

    return result, meta


def _title_from_markdown(markdown: str) -> Optional[str]:
    """Extract first # heading from markdown as title fallback."""
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None


def _article_to_dict(article: LibraryArticle, vocab_count: int = 0) -> Dict:
    return {
        "id": article.id,
        "user_id": article.user_id,
        "source_url": article.source_url,
        "title": article.title,
        "markdown": article.markdown,
        "word_count": article.word_count,
        "source_meta": json.loads(article.source_meta) if article.source_meta else {},
        "status": article.status,
        "vocab_count": vocab_count,
        "created_at": article.created_at.isoformat() if article.created_at else None,
        "updated_at": article.updated_at.isoformat() if article.updated_at else None,
    }


def import_article(
    user_id: str,
    url: Optional[str] = None,
    markdown: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict:
    """Import an article (URL or paste-markdown mode).

    URL dedup: if (user_id, source_url) already exists, return existing with existing=True.
    Returns dict with extra key 'existing' (bool).
    """
    if not url and not markdown:
        raise ValueError("url 或 markdown 必须提供其一")

    source_meta: Dict = {}

    if url:
        # Check dedup first (before fetching)
        with OrmSession(engine) as s:
            existing = (
                s.query(LibraryArticle)
                .filter_by(user_id=user_id, source_url=url)
                .first()
            )
            if existing:
                logger.info(
                    "library_article_dedup_hit user_id=%s url=%s id=%d",
                    user_id, url, existing.id,
                )
                result = _article_to_dict(existing, _count_vocab(s, user_id, existing.id))
                result["existing"] = True
                return result

        # Fetch URL
        try:
            markdown, source_meta = _extract_from_url(url)
        except ValueError as e:
            logger.warning("library_article_fetch_failed user_id=%s url=%s reason=%s", user_id, url, e)
            raise

        # Title: meta > first # heading > Untitled
        if not title:
            title = source_meta.get("title") or _title_from_markdown(markdown) or "Untitled"
    else:
        # Paste mode: title required by caller, but provide fallback
        if not title:
            title = _title_from_markdown(markdown) or "Untitled"

    # Truncate if too long
    truncated = False
    if len(markdown) > MAX_MARKDOWN_LEN:
        markdown = markdown[:MAX_MARKDOWN_LEN]
        truncated = True
        logger.warning(
            "library_article_truncated user_id=%s url=%s char_count=%d",
            user_id, url, MAX_MARKDOWN_LEN,
        )
        source_meta["truncated"] = True

    word_count = len(markdown.split())

    with OrmSession(engine) as s:
        article = LibraryArticle(
            user_id=user_id,
            source_url=url or None,
            title=title,
            markdown=markdown,
            word_count=word_count,
            source_meta=json.dumps(source_meta, ensure_ascii=False) if source_meta else None,
            status="active",
        )
        s.add(article)
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            # Race condition: another request inserted the same URL
            existing = (
                s.query(LibraryArticle)
                .filter_by(user_id=user_id, source_url=url)
                .first()
            )
            if existing:
                result = _article_to_dict(existing, _count_vocab(s, user_id, existing.id))
                result["existing"] = True
                return result
            raise
        s.refresh(article)
        logger.info(
            "library_article_imported user_id=%s id=%d mode=%s char_count=%d",
            user_id, article.id, "url" if url else "markdown", len(markdown),
        )
        result = _article_to_dict(article, 0)
        result["existing"] = False
        return result


def _count_vocab(session: OrmSession, user_id: str, article_id: int) -> int:
    """Count vocabulary items for this article."""
    count = (
        session.query(sql_func.count(Vocabulary.id))
        .filter_by(user_id=user_id, source_type="library", source_ref=str(article_id))
        .scalar()
    )
    return count or 0


def list_articles(
    user_id: str,
    page: int = 1,
    page_size: int = 20,
) -> List[Dict]:
    """List active articles for user, ordered by created_at DESC, with vocab_count."""
    offset = (page - 1) * page_size
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
        for article in rows:
            d = _article_to_dict(article, _count_vocab(s, user_id, article.id))
            # Don't include full markdown in list (bandwidth)
            d.pop("markdown", None)
            result.append(d)
        return result


def get_article(article_id: int, user_id: str) -> Optional[Dict]:
    """Get article detail (including full markdown) with vocab_count."""
    with OrmSession(engine) as s:
        article = (
            s.query(LibraryArticle)
            .filter_by(id=article_id, user_id=user_id, status="active")
            .first()
        )
        if not article:
            return None
        return _article_to_dict(article, _count_vocab(s, user_id, article.id))


def delete_article(article_id: int, user_id: str) -> bool:
    """Soft delete article. vocabulary items are NOT cascade-deleted."""
    with OrmSession(engine) as s:
        article = (
            s.query(LibraryArticle)
            .filter_by(id=article_id, user_id=user_id, status="active")
            .first()
        )
        if not article:
            return False
        article.status = "deleted"
        s.commit()
        return True


def refetch_article(article_id: int, user_id: str) -> Dict:
    """Re-extract content from URL. Only valid for URL-based articles."""
    with OrmSession(engine) as s:
        article = (
            s.query(LibraryArticle)
            .filter_by(id=article_id, user_id=user_id, status="active")
            .first()
        )
        if not article:
            raise LookupError("文章不存在或已删除")
        if not article.source_url:
            raise ValueError("paste_mode_no_url")

        try:
            markdown, source_meta = _extract_from_url(article.source_url)
        except ValueError as e:
            logger.warning(
                "library_article_fetch_failed user_id=%s url=%s reason=%s",
                user_id, article.source_url, e,
            )
            raise

        truncated = False
        if len(markdown) > MAX_MARKDOWN_LEN:
            markdown = markdown[:MAX_MARKDOWN_LEN]
            source_meta["truncated"] = True
            logger.warning(
                "library_article_truncated user_id=%s url=%s",
                user_id, article.source_url,
            )

        article.markdown = markdown
        article.word_count = len(markdown.split())
        if source_meta:
            article.source_meta = json.dumps(source_meta, ensure_ascii=False)
        s.commit()
        s.refresh(article)
        return _article_to_dict(article, _count_vocab(s, user_id, article.id))
