"""Extract character levels explicitly printed on numbered dungeon leaderboards."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
RANK = re.compile(r"^(\d+)\.\s+(.+)$")
LEVEL = re.compile(r"Level\s+(\d+)", re.I)
PRIZE = re.compile(r"[\d,]+(?:\s*\(x\d+\))?", re.I)
ALIASES = {"Donut": "Princess Donut"}


def reading(text):
    rank = RANK.fullmatch(text.strip())
    if not rank:
        return None
    fields = re.split(r"\s+[–—-]\s+", rank[2])
    if len(fields) != 5 or not PRIZE.fullmatch(fields[-1]):
        return None
    name, race, class_name, level_text, _ = fields
    if LEVEL.fullmatch(class_name):
        class_name, level_text = level_text, class_name
    level = LEVEL.fullmatch(level_text)
    if not level:
        return None
    return dict(
        subject=ALIASES.get(name, name),
        printed_name=name,
        level=int(level[1]),
        race=race,
        character_class=class_name,
        board_rank=int(rank[1]),
    )


def reconcile(corpus, series):
    known = {c["name"] for c in series["characters"]}
    levels = defaultdict(list)
    for e in series["events"]:
        if e["type"] == "level" and isinstance(e.get("level"), int):
            levels[ALIASES.get(e["subject"], e["subject"])].append(e)
    for rows in levels.values():
        rows.sort(key=lambda e: (e["book"], e["chapter"], e["position"]))
    for b in corpus["books"]:
        for ch in b["chapters"]:
            for p in ch["paragraphs"]:
                row = reading(p["text"])
                if row is None:
                    continue
                loc = (b["number"], ch["number"], p["position"])
                history = levels[row["subject"]]
                previous = next(
                    (
                        e
                        for e in reversed(history)
                        if (e["book"], e["chapter"], e["position"]) < loc
                    ),
                    None,
                )
                current = [
                    e
                    for e in history
                    if e["source"] == p["anchor"]
                    or p["anchor"] in e.get("evidence", [])
                ]
                if current:
                    status = (
                        "recorded here"
                        if any(e["level"] == row["level"] for e in current)
                        else "conflict at source"
                    )
                elif row["subject"] not in known:
                    status = "review printed name"
                elif previous and previous["level"] == row["level"]:
                    status = "repeat of last recorded level"
                elif previous and previous["level"] > row["level"]:
                    status = "below earlier reading"
                elif any(e["level"] == row["level"] for e in history):
                    status = "value recorded elsewhere"
                else:
                    status = "value missing from timeline"
                yield dict(
                    book=b["number"],
                    chapter=ch["number"],
                    source=p["anchor"],
                    **row,
                    status=status,
                )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--series", type=Path, default=ROOT / "site/dist/data/series.json"
    )
    args = parser.parse_args()
    private = ROOT / "data/private"
    rows = list(
        reconcile(
            json.loads((private / "series-corpus.json").read_text()),
            json.loads(args.series.read_text()),
        )
    )
    path = private / "leaderboard-readings.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    # Only propose the earliest missing reading for a named crawler at each level.
    # Preserve every printed row (including stale values) in the reconciliation file.
    proposed = {}
    for row in rows:
        if row["status"] == "value missing from timeline":
            key = (row["subject"], row["level"])
            proposed.setdefault(
                key,
                {
                    "source": row["source"],
                    "subject": row["subject"],
                    "type": "level",
                    "name": "Character level",
                    "action": "set",
                    "level": row["level"],
                    "summary": f"The leaderboard lists {row['subject']} at level {row['level']}.",
                },
            )
    draft = private / "leaderboard-proposals.json"
    draft.write_text(
        json.dumps({"events": list(proposed.values())}, indent=2, ensure_ascii=False)
        + "\n"
    )
    print(f"{len(rows)} leaderboard entries → {path}")
    print(f"{len(proposed)} proposed observations → {draft}")
    for status, count in Counter(r["status"] for r in rows).most_common():
        print(count, status)


if __name__ == "__main__":
    main()
