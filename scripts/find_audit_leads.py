"""Rank private chapter passages for manual fact checking against the public timeline."""

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re

from extract_epub import classify

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "data/private"
NUMBER = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|fifty|hundred)"
STAT = r"(?:strength|dexterity|intelligence|constitution|charisma|mana|health)"
GEAR = r"(?:ring|jacket|patch|crown|gauntlet|armor|armour|helmet|cloak|shield|boxers|necklace|charm|gear|boots?|piercing|item)"
RULES = {
    "rank or measurement": (
        "level",
        rf"\b(?:level(?:ed|led)?(?:\s+up)?\s*(?:to|of|is|was|at)?\s*{NUMBER}|{STAT}\b.{{0,22}}?\b{NUMBER}|{NUMBER}\b.{{0,16}}?\b{STAT})\b",
    ),
    "ability learned or changed": (
        "skill",
        r"\b(?:learned|learnt|unlocked|granted|ranked up|trained|leveled up|levelled up|new (?:skill|spell)|spell (?:has|is now)|skill (?:has|is now))\b",
    ),
    "equipment or modifier": (
        "item",
        rf"\b(?:equipped|unequipped|attached|affixed|wearer gains|while worn|as long as you wear)\b|\b{GEAR}\b.{{0,80}}(?:\+\d+|\b(?:bonus|grants?|adds?)\b)",
    ),
    "transfer or consumption": (
        "item",
        r"\b(?:handed|gave|gifted|passed|returned|traded|sold|offered|drank|consumed|swallowed|used up|ran out of|last of (?:my|her|his|the)|added to (?:my|her|his|your) inventory|pulled .{1,40} from .{0,12}inventory)\b",
    ),
    "box or reward": (
        "reward",
        r"\b(?:(?:bronze|silver|gold|platinum|legendary|celestial)\b.{0,45}\bbox|reward:|you (?:have )?received|achievement!|inside (?:the|my|her|his) box)",
    ),
    "party or life status": (
        "party",
        r"\b(?:joined (?:our|the|your|their) (?:party|guild)|left (?:our|the|your|their) party|party (?:leader|member)|was dead|has died|had died|was killed|confirmed dead|resurrected|revived)\b",
    ),
}
PATTERNS = {name: re.compile(pattern, re.I) for name, (_, pattern) in RULES.items()}
HYPOTHETICAL = re.compile(
    r"\b(?:could|would|might|if|planned to|supposed to|going to)\b", re.I
)


def index_events(series):
    by_anchor = defaultdict(list)
    for event in series["events"]:
        for anchor in {event["source"], *event.get("evidence", [])}:
            by_anchor[anchor].append(event)
    return by_anchor


def names_pattern(series):
    names = {c["name"] for c in series["characters"]}
    names.update(
        n.split()[0]
        for n in list(names)
        if len(n.split()[0]) > 2
        and n.split()[0] not in {"Princess", "Doctor", "Sexy", "Juice", "Dong"}
    )
    names.add("Donut")
    return re.compile(
        r"\b(?:"
        + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
        + r")\b",
        re.I,
    )


def candidates(book, by_anchor, names):
    for chapter in book["chapters"]:
        paragraphs = chapter["paragraphs"]
        for i, p in enumerate(paragraphs):
            text = p["text"]
            cues = [name for name, pattern in PATTERNS.items() if pattern.search(text)]
            if not cues:
                continue
            context = paragraphs[max(0, i - 2) : i + 3]
            named = list(
                dict.fromkeys(names.findall(" ".join(row["text"] for row in context)))
            )
            recorded = by_anchor.get(p["anchor"], [])
            types = {e["type"] for e in recorded}
            if any(e.get("acquisition") for e in recorded):
                types.add("reward")
            if "stat" in types:
                types.add("level")  # This cue covers both numeric observation types.
            # Prefer unmatched kinds. A populated paragraph may contain extra discoveries.
            score = (
                2 * len(cues)
                + bool(named)
                + bool(p["bold"])
                + any(RULES[c][0] not in types for c in cues)
            )
            score -= bool(HYPOTHETICAL.search(text))
            current = {
                e["id"]: e for row in context for e in by_anchor.get(row["anchor"], [])
            }
            context_rows = [
                {"anchor": row["anchor"], "text": row["text"]} for row in context
            ]
            key = sha256(
                json.dumps([context_rows, current], sort_keys=True).encode()
            ).hexdigest()[:20]
            yield dict(
                key=key,
                book=book["number"],
                chapter=chapter["number"],
                anchor=p["anchor"],
                cues=cues,
                score=score,
                names_in_context=named,
                original_queue_kinds=classify(text, bold=p["bold"]),
                context=context_rows,
                existing=[
                    {
                        "id": e["id"],
                        "source": e["source"],
                        "subject": e["subject"],
                        "type": e["type"],
                        "name": e["name"],
                    }
                    for e in current.values()
                ],
            )


def select(rows, limit):
    # Rotate through evidence types; select disjoint windows and spread the first pass over chapters.
    pools = {
        cue: sorted(
            [r for r in rows if cue in r["cues"]],
            key=lambda r: (
                -r["score"],
                r["chapter"],
                int(r["anchor"].rsplit("p", 1)[1]),
            ),
        )
        for cue in RULES
    }
    chosen, covered, chapter_counts = [], set(), Counter()
    while len(chosen) < limit:
        before = len(chosen)
        for cue, pool in pools.items():
            eligible = (
                r for r in pool if all(p["anchor"] not in covered for p in r["context"])
            )
            pick = min(
                eligible, key=lambda r: chapter_counts[r["chapter"]], default=None
            )
            if pick:
                chosen.append(pick)
                chapter_counts[pick["chapter"]] += 1
                covered.update(p["anchor"] for p in pick["context"])
                if len(chosen) == limit:
                    break
        if len(chosen) == before:
            break
    return chosen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--books", type=int, nargs="+", default=list(range(2, 9)))
    parser.add_argument("--limit-per-book", type=int, default=12)
    parser.add_argument(
        "--series", type=Path, default=ROOT / "site/dist/data/series.json"
    )
    parser.add_argument("--output", type=Path, default=PRIVATE / "audit-leads.jsonl")
    parser.add_argument(
        "--reviewed",
        type=Path,
        help="Private JSONL dispositions containing reviewed window keys",
    )
    args = parser.parse_args()
    if args.limit_per_book < 1 or not args.output.resolve().is_relative_to(
        PRIVATE.resolve()
    ):
        parser.error(
            "Use a positive limit and an output under data/private (contains book text)."
        )
    corpus = json.loads((PRIVATE / "series-corpus.json").read_text())["books"]
    if set(args.books) - {b["number"] for b in corpus}:
        parser.error("Unknown book number")
    series = json.loads(args.series.read_text())
    by_anchor, names = index_events(series), names_pattern(series)
    seen = (
        {
            json.loads(s)["key"]
            for s in args.reviewed.read_text().splitlines()
            if s.strip()
        }
        if args.reviewed
        else set()
    )
    result = []
    for b in corpus:
        if b["number"] in args.books:
            leads = [r for r in candidates(b, by_anchor, names) if r["key"] not in seen]
            result.extend(select(leads, args.limit_per_book))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in result)
    )
    print(f"Wrote {len(result)} review windows to {args.output}")


if __name__ == "__main__":
    main()
