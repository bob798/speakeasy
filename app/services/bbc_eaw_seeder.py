"""Seed article_episodes from data/bbc_eaw/parsed/*.json.

Idempotent upsert by `slug`. Used by:
  - scripts/bbc_eaw_seed.py (CLI / one-shot)
  - main.py lifespan startup (auto-seed on container boot)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session as OrmSession

from app.models.db import ArticleEpisode, engine

log = logging.getLogger(__name__)

DEFAULT_PARSED_DIR = Path("data/bbc_eaw/parsed")
DEFAULT_RAW_DIR = Path("data/bbc_eaw/raw")


def _row_fields(parsed: dict, raw_dir: Path) -> dict:
    slug = parsed["slug"]
    raw_path = raw_dir / f"{slug}.html"
    return dict(
        slug=slug,
        url=parsed["url"],
        title=parsed.get("title"),
        episode_id=parsed.get("episode_id"),
        air_date=parsed.get("air_date"),
        topic=parsed.get("topic"),
        description=parsed.get("description") or "",
        phrases_json=json.dumps(parsed.get("phrases") or [], ensure_ascii=False),
        listening_question=(parsed.get("listening_challenge") or {}).get("question"),
        listening_answer=(parsed.get("listening_challenge") or {}).get("answer"),
        transcript_json=json.dumps(parsed.get("transcript") or [], ensure_ascii=False),
        transcript_turns=int(parsed.get("transcript_turns") or 0),
        source_html_path=str(raw_path) if raw_path.exists() else None,
    )


def seed(parsed_dir: Path = DEFAULT_PARSED_DIR,
         raw_dir: Path = DEFAULT_RAW_DIR,
         dry_run: bool = False) -> dict:
    """Upsert all parsed episodes. Returns counts."""
    files = sorted(Path(parsed_dir).glob("*.json"))
    if not files:
        return {"inserted": 0, "updated": 0, "total": 0, "missing_dir": True}

    inserted = updated = 0
    with OrmSession(engine) as sess:
        for f in files:
            parsed = json.loads(f.read_text(encoding="utf-8"))
            slug = parsed["slug"]
            row = sess.query(ArticleEpisode).filter_by(slug=slug).one_or_none()
            fields = _row_fields(parsed, Path(raw_dir))
            if row is None:
                inserted += 1
                if not dry_run:
                    sess.add(ArticleEpisode(**fields))
            else:
                updated += 1
                if not dry_run:
                    for k, v in fields.items():
                        setattr(row, k, v)
                    row.updated_at = datetime.utcnow()
        if not dry_run:
            sess.commit()
    return {"inserted": inserted, "updated": updated, "total": len(files)}


def seed_at_startup() -> None:
    """Best-effort seed run during app startup. Never raises."""
    try:
        if not DEFAULT_PARSED_DIR.is_dir():
            log.info("bbc_eaw seeder: %s missing, skipping", DEFAULT_PARSED_DIR)
            return
        result = seed()
        log.info(
            "bbc_eaw seeder: inserted=%d updated=%d total=%d",
            result["inserted"], result["updated"], result["total"],
        )
    except Exception as exc:  # noqa: BLE001 - never crash startup
        log.warning("bbc_eaw seeder failed (non-fatal): %s", exc)
