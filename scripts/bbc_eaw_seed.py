"""Seed bbc_eaw_episodes from data/bbc_eaw/parsed/*.json (CLI wrapper).

Idempotent: upserts by `slug`. Re-running is safe — existing rows are updated
in place. Run after bbc_eaw_fetch.py + bbc_eaw_parse.py.

Usage:
    python3 scripts/bbc_eaw_seed.py            # default paths
    python3 scripts/bbc_eaw_seed.py --dry-run  # show what would change
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make `app` importable when running from project root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.bbc_eaw_seeder import seed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parsed", default="data/bbc_eaw/parsed")
    ap.add_argument("--raw", default="data/bbc_eaw/raw")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    result = seed(parsed_dir=Path(args.parsed),
                  raw_dir=Path(args.raw),
                  dry_run=args.dry_run)

    if result.get("missing_dir"):
        print(f"No parsed JSON in {args.parsed}", file=sys.stderr)
        return 1

    label = "[dry-run] " if args.dry_run else ""
    print(f"{label}{result['inserted']} inserted, {result['updated']} updated, "
          f"{result['total']} total.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
