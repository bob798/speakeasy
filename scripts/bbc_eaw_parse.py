"""Parse BBC English at Work raw HTML pages into structured JSON.

Reads each file in data/bbc_eaw/raw/, extracts:
  - episode metadata (slug, url, title, episode_id, air_date, topic, description)
  - phrases (list of strings, may be empty)
  - listening_challenge { question, answer }
  - transcript: list of { speaker, text } turns

Writes one JSON per episode to data/bbc_eaw/parsed/<slug>.json
plus an aggregate data/bbc_eaw/index.json.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

BASE_URL = "https://www.bbc.co.uk/learningenglish/english/features/english-at-work"


def strip_tags(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r"\n[ \t]+", "\n", s)
    return s.strip()


def find_h3s(raw: str) -> list[tuple[int, int, str]]:
    """Return list of (start, end, text) for all <h3> in document order."""
    out = []
    for m in re.finditer(r"<h3[^>]*>(.*?)</h3>", raw, re.S):
        out.append((m.start(), m.end(), strip_tags(m.group(1))))
    return out


def parse_episode_id(s: str) -> tuple[str | None, str | None]:
    # e.g. "Episode 160706 \n\n  / 06 Jul 2016"
    m = re.search(r"Episode\s+(\d+)\s*/\s*([0-9]+\s+\w+\s+\d{4})", re.sub(r"\s+", " ", s))
    if m:
        return m.group(1), m.group(2)
    m = re.search(r"Episode\s+(\d+)", s)
    return (m.group(1) if m else None), None


def extract_block(raw: str, start: int, end: int) -> str:
    """Return inner HTML between two offsets."""
    return raw[start:end]


def parse_phrases(block: str) -> list[str]:
    """Find phrases list. Try a labelled marker first, otherwise fall back to
    the first <ul> in the description block (BBC sometimes omits the label)."""
    m = re.search(r"Phrases\s+from\s+the\s+programme[^<]*<[^>]+>\s*<ul[^>]*>(.*?)</ul>", block, re.S | re.I)
    if not m:
        m = re.search(r"Phrases?\s+to\s+(?:learn|use)[^<]*<[^>]+>\s*<ul[^>]*>(.*?)</ul>", block, re.S | re.I)
    if not m:
        m = re.search(r"<ul[^>]*>(.*?)</ul>", block, re.S | re.I)
    if not m:
        return []
    items = re.findall(r"<li[^>]*>(.*?)</li>", m.group(1), re.S)
    return [strip_tags(x) for x in items if strip_tags(x)]


def parse_description(block: str) -> str:
    """Concatenate <p> paragraphs that appear before any phrases / listening challenge / transcript."""
    chunks: list[str] = []
    # Stop at the first occurrence of one of these markers.
    cutoff = len(block)
    for marker in ("Phrases from the programme", "Listening Challenge", "<h3>Transcript"):
        i = block.find(marker)
        if i != -1:
            cutoff = min(cutoff, i)
    head = block[:cutoff]
    for m in re.finditer(r"<p[^>]*>(.*?)</p>", head, re.S):
        text = strip_tags(m.group(1))
        if text:
            chunks.append(text)
    return "\n".join(chunks)


def parse_listening_challenge(block: str) -> tuple[str | None, str | None]:
    """Question between 'Listening Challenge' and the transcript header.
    Answer between 'Listening Challenge - Answer' (or 'Listening Challenge Answer') and end.
    """
    q = None
    a = None
    qm = re.search(r"Listening\s+Challenge\s*</strong>\s*</p>\s*<p[^>]*>(.*?)</p>", block, re.S | re.I)
    if not qm:
        qm = re.search(r"Listening\s+Challenge[^<]*</[^>]+>\s*<p[^>]*>(.*?)</p>", block, re.S | re.I)
    if qm:
        q = strip_tags(qm.group(1))

    am = re.search(
        r"Listening\s+Challenge\s*[-–]?\s*Answer.*?</[^>]+>\s*(?:<p[^>]*>(.*?)</p>)?(?:\s*<p[^>]*>(.*?)</p>)?",
        block, re.S | re.I)
    if am:
        # Repeat-q line then answer line; take the second non-empty if available.
        candidates = [strip_tags(x) for x in am.groups() if x]
        candidates = [c for c in candidates if c]
        if candidates:
            a = candidates[-1]
    return q, a


_BR_RX = re.compile(r"<br\s*/?>", re.I)


def split_speaker_turn(p_inner: str) -> tuple[str, str]:
    """Split a <p> inner HTML into (speaker, text) by the first <br />.

    BBC pages use shapes like:
      <strong>Anna<br /></strong>line text
      <strong>Tom&nbsp; &nbsp;<br /></strong>line text
      <strong><span>Tom<br /></span></strong>line text
      <strong>Anna</strong><strong><span><br /></span></strong>line text
    Splitting on the first <br /> and stripping all tags/entities reliably
    isolates the speaker name from the line, regardless of nested spans.
    """
    parts = _BR_RX.split(p_inner, maxsplit=1)
    if len(parts) != 2:
        return "", strip_tags(p_inner)
    head, body = parts
    speaker = strip_tags(head).rstrip(":：").strip()
    text = strip_tags(body).lstrip(":：").strip()
    return speaker, text


def parse_transcript(raw: str) -> list[dict]:
    """Parse turns between <h3>Transcript</h3> and 'Listening Challenge - Answer' / next <h3>."""
    t_match = re.search(r"<h3[^>]*>\s*Transcript\s*</h3>", raw)
    if not t_match:
        return []
    start = t_match.end()
    end_candidates = []
    for pat in (r"Listening\s+Challenge\s*[-–]?\s*Answer", r"<h3[^>]*>", r"<div[^>]+id=\"orb-footer\""):
        m = re.search(pat, raw[start:])
        if m:
            end_candidates.append(start + m.start())
    end = min(end_candidates) if end_candidates else len(raw)
    section = raw[start:end]

    turns: list[dict] = []
    for m in re.finditer(r"<p[^>]*>(.*?)</p>", section, re.S):
        speaker, text = split_speaker_turn(m.group(1))
        if not text:
            continue
        # Some <p> blocks are pure narration with no speaker prefix; keep them with empty speaker.
        turns.append({"speaker": speaker, "text": text})
    return turns


def parse_one(slug: str, raw: str) -> dict:
    h3s = find_h3s(raw)

    title = None
    episode_id = None
    air_date = None
    topic = None

    for i, (_, _, text) in enumerate(h3s):
        if text == "English at Work" and title is None:
            # The next h3 is the episode title.
            if i + 1 < len(h3s):
                title = h3s[i + 1][2]
            if i + 2 < len(h3s):
                episode_id, air_date = parse_episode_id(h3s[i + 2][2])
            # Topic = next h3 after episode-id, unless it's "Transcript"/"Listening Challenge".
            if i + 3 < len(h3s):
                t = h3s[i + 3][2]
                if t.lower() not in {"transcript", "listening challenge"}:
                    topic = t
            break

    # Pull the page <title> as backup.
    title_tag = re.search(r"<title>(.*?)</title>", raw, re.S)
    page_title = strip_tags(title_tag.group(1)) if title_tag else ""

    description = ""
    phrases: list[str] = []
    if h3s:
        # Description block between 3rd h3 (episode-id) and the Transcript h3.
        ep_h3 = next((h for h in h3s if h[2].startswith("Episode ")), None)
        tr_h3 = next((h for h in h3s if h[2].lower() == "transcript"), None)
        if ep_h3 and tr_h3:
            block = raw[ep_h3[1]:tr_h3[0]]
            description = parse_description(block)
            phrases = parse_phrases(block)

    # Listening challenge extraction over a wider block (covers cases without a preceding topic h3).
    if h3s:
        ep_h3 = next((h for h in h3s if h[2].startswith("Episode ")), None)
        if ep_h3:
            tail = raw[ep_h3[1]:]
            q, a = parse_listening_challenge(tail)
        else:
            q, a = parse_listening_challenge(raw)
    else:
        q, a = parse_listening_challenge(raw)

    transcript = parse_transcript(raw)

    # Drop the duplicated question prefix from the answer (BBC repeats it).
    if q and a and a.startswith(q):
        a = a[len(q):].lstrip("\n :：").strip() or a

    return {
        "slug": slug,
        "url": f"{BASE_URL}/{slug}",
        "page_title": page_title,
        "title": title,
        "episode_id": episode_id,
        "air_date": air_date,
        "topic": topic,
        "description": description,
        "phrases": phrases,
        "listening_challenge": {"question": q, "answer": a},
        "transcript": transcript,
        "transcript_turns": len(transcript),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", default="data/bbc_eaw/raw")
    ap.add_argument("--out", default="data/bbc_eaw/parsed")
    ap.add_argument("--index", default="data/bbc_eaw/index.json")
    args = ap.parse_args()

    raw_dir = Path(args.raw)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    index = []
    files = sorted(raw_dir.glob("*.html"))
    if not files:
        print(f"No HTML found in {raw_dir}", file=sys.stderr)
        return 1

    for path in files:
        slug = path.stem
        raw = path.read_text(encoding="utf-8")
        parsed = parse_one(slug, raw)
        out_path = out_dir / f"{slug}.json"
        out_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
        index.append({
            "slug": slug,
            "title": parsed["title"],
            "episode_id": parsed["episode_id"],
            "air_date": parsed["air_date"],
            "topic": parsed["topic"],
            "phrases_count": len(parsed["phrases"]),
            "transcript_turns": parsed["transcript_turns"],
            "url": parsed["url"],
        })
        print(f"  parsed {slug:<55} turns={parsed['transcript_turns']:>3}  phrases={len(parsed['phrases'])}")

    Path(args.index).write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDone. {len(index)} episodes parsed → {out_dir}")
    print(f"Index: {args.index}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
