"""Fetch all BBC Learning English — English at Work episode pages.

Saves raw HTML to data/bbc_eaw/raw/<slug>.html. Idempotent: skips files that
already exist unless --force is passed. Polite ~1 req/s rate limit.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

BASE = "https://www.bbc.co.uk/learningenglish/english/features/english-at-work"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

SLUGS = [
    "english-at-work-intro",
    "01-the-interview",
    "02-the-interruption",
    "03-the-crisis",
    "04-doing-lunch",
    "05-polite-requests",
    "06-how-to-offer-help",
    "07-apologising",
    "08-gving-praise",  # BBC's own typo — keep as-is
    "09-checking-information",
    "10-disagreeing",
    "11-language-working-long-hours",
    "12-opening-presentations",
    "13-making-a-pitch",
    "14-giving-feedback",
    "15-more-about-telephone-manner",
    "16-politely-refusing",
    "17-how-to-place-an-order",
    "18-writing-an-email",
    "19-explaining-a-misunderstanding",
    "20-setting-an-agenda",
    "21-asking-for-help",
    "22-making-polite-requests",
    "23-health-and-safety",
    "24-words-to-use-in-an-emergency",
    "25-booking-a-hotel",
    "26-complaining",
    "27-delivering-bad-news",
    "28-keeping-language-professional",
    "29-cold-calling",
    "30-negotiating",
    "31-project-management",
    "32-negotiating-a-deal-2",
    "33-booking-a-flight",
    "34-clinching-the-deal",
    "35-briefing-the-manager",
    "36-working-with-someone-new",
    "37-dealing-with-difficult-staff",
    "38-language-for-good-customer-relations",
    "39-disciplining-a-member-of-staff",
    "40-language-to-use-in-an-appraisal",
    "41-language-for-health-and-safety",
    "42-language-writing-a-proposal",
    "43-language-to-use-in-research",
    "44-language-to-in-dealing-with-it-support",  # BBC missing "use"
    "45-language-for-making-an-elevator-pitch",
    "46-language-for-being-in-charge",
    "47-language-to-clear-up-confusion",
    "48-language-for-networking",
    "49-language-to-use-in-an-acceptance-speech",
    "50-language-used-making-someone-redundant",
    "51-language-for-conveying-your-ideas",
    "52-language-giving-careers-advice",
    "53-language-to-use-telephone-message",
    "54-language-for-justifying-your-position",
    "55-language-telling-someone-what-to-do",
    "56-language-for-setting-priorities",
    "57-language-for-booking-a-venue",
    "58-language-for-getting-something-done-quickly",
    "59-language-for-presenting-a-new-product",
    "60-language-related-to-getting-the-sack",
    "61-language-for-offering-and-accepting-promotions",
    "62-language-to-announce-your-decision",
    "63-language-to-persuade-someone-to-change-their-mind",
    "64-language-for-getting-down-to-business",
    "65-language-to-say-youve-changed-your-mind",
    "66-language-for-a-wedding-day",
]


def fetch(slug: str, out_dir: Path, force: bool = False) -> str:
    target = out_dir / f"{slug}.html"
    if target.exists() and not force:
        return "skip"
    url = f"{BASE}/{slug}"
    cmd = [
        "curl", "-sSL", "--fail", "--max-time", "30",
        "-A", UA, "-o", str(target), "-w", "%{http_code}", url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        if target.exists():
            target.unlink()
        return f"error: curl rc={proc.returncode} {proc.stderr.strip()}"
    code = proc.stdout.strip()
    if code != "200":
        if target.exists():
            target.unlink()
        return f"error: HTTP {code}"
    return f"ok ({target.stat().st_size} bytes)"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="data/bbc_eaw/raw", help="output directory")
    ap.add_argument("--force", action="store_true", help="re-download existing files")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    ap.add_argument("--only", help="comma-separated slugs to fetch (debug)")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    slugs = args.only.split(",") if args.only else SLUGS
    total = len(slugs)
    failures: list[str] = []
    for i, slug in enumerate(slugs, 1):
        result = fetch(slug, out_dir, force=args.force)
        print(f"[{i:>3}/{total}] {slug:<55} {result}")
        if result.startswith("error"):
            failures.append(slug)
        if not result.startswith("skip") and i < total:
            time.sleep(args.delay)

    print(f"\nDone. {total - len(failures)}/{total} ok, {len(failures)} failed.")
    if failures:
        print("Failed slugs:", ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
