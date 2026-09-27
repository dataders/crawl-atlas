#!/usr/bin/env python3
"""Build the public event ledger from private, source-anchored audits.

The generated file contains factual paraphrases only. It never copies EPUB
paragraph text into the public site.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CHARACTER_AUDIT = ROOT / "data/private/character-progression.json"
INVENTORY_AUDIT = ROOT / "data/private/inventory-progression.json"
OUTPUT = ROOT / "site/dist/data/series.json"
LEGACY_OUTPUT = ROOT / "site/dist/data/book-1.json"
CORPUS = ROOT / "data/private/corpus.json"
SERIES_CORPUS = ROOT / "data/private/series-corpus.json"
CHAPTER_COUNT = 47
ITEM_ALIASES = {
    "Common Fingerless Glove": "Common Fingerless Gloves",
    "Original boxers": "Boxers",
    "Goblin chopper with sidecar": "Goblin chopper with detachable sidecar",
}
INITIAL_BOXES = (
    "Bronze Pet Box",
    "Legendary Pet Box",
    "Silver Adventurer Box",
    "Bronze Adventurer Box",
    "Gold Apparel Box",
    "Bronze Weapon Box",
)
BASE_STAT_SOURCES = {
    "carl-initial-stats",
    "donut-first-stat-display",
    "donut-strength-15",
    "donut-charisma-37",
    "donut-charisma-39",
    "donut-strength-18-dodge-4",
    "donut-charisma-41",
    "donut-charisma-43",
}
TEMPORARY_STAT_SOURCES = {
    "carl-donut-buzzed-stat-modifiers",
    "donut-temporary-constitution-4",
}
EQUIPMENT_STAT_SOURCES = {
    "carl-constitution-9",
    "carl-strength-9",
    "donut-tiara-bonuses",
    "carl-constitution-10",
    "donut-light-on-feet-7",
    "donut-dexterity-plus-2-fae-armor",
    "carl-constitution-12",
    "carl-gauntlet-skill-bonuses",
    "carl-constitution-14-protective-shell-15",
    "carl-constitution-14-confirmed",
}

# Explicitly stated progression after Book 1. Each short needle is resolved
# against the private corpus so every public milestone retains a source anchor.
SERIES_LEVEL_MILESTONES = (
    (2, 1, "Princess Donut", 13, "Princess Donut the Level 13"),
    (2, 2, "Carl", 13, "Dungeon Crawler Carl, the Level 13"),
    (2, 7, "Carl", 14, "both now level 14"),
    (2, 7, "Princess Donut", 14, "both now level 14"),
    (2, 9, "Carl", 15, "gone up to level 15"),
    (2, 12, "Princess Donut", 15, "risen to level 15"),
    (2, 12, "Carl", 18, "currently level 18"),
    (2, 12, "Mongo", 10, "Now that he was level 10"),
    (2, 14, "Princess Donut", 16, "leveled up to 16"),
    (2, 14, "Mongo", 11, "Mongo hit level 11"),
    (2, 18, "Mongo", 12, "gone up to level 12"),
    (3, 3, "Carl", 27, "Carl – Primal – Compensated Anarchist – Level 27"),
    (3, 3, "Princess Donut", 26, "Donut – Cat – Former Child Actor – Level 26"),
    (3, 6, "Mongo", 14, "Mongo managed to hit level 14"),
    (3, 7, "Mongo", 15, "Mongo hit level 15"),
    (3, 11, "Carl", 29, "You are now level 29"),
    (3, 12, "Princess Donut", 28, "I hit level 28"),
    (3, 15, "Princess Donut", 30, "TWO LEVELS TO LEVEL 30"),
    (3, 25, "Carl", 34, "Carl – Primal – Compensated Anarchist – Level 34"),
    (3, 25, "Princess Donut", 32, "Donut – Cat – Former Child Actor – Level 32"),
    (3, 26, "Mongo", 23, "Mongo had recently risen to level 23"),
    (4, 2, "Carl", 41, "your level 41"),
    (4, 4, "Princess Donut", 33, "Donut – Cat – Former Child Actor – Level 33"),
    (4, 12, "Princess Donut", 34, "Level 34!"),
    (4, 17, "Carl", 44, "I was now at 44"),
    (4, 17, "Princess Donut", 37, "Donut was 37"),
    (4, 17, "Mongo", 33, "hitting level 33"),
    (4, 28, "Carl", 47, "gone up three levels to 47"),
    (4, 28, "Princess Donut", 39, "Donut was level 39"),
    (5, 6, "Carl", 54, "rocketed up to level 54"),
    (5, 6, "Princess Donut", 41, "few levels to 41"),
    (5, 51, "Princess Donut", 47, "TWO LEVELS TO 47"),
    (5, 61, "Carl", 59, "player level up to 59"),
    (5, 61, "Princess Donut", 50, "her level to 50"),
    (5, 75, "Carl", 63, "You’re 63!"),
    (5, 75, "Princess Donut", 55, "I went up to 55"),
    (6, 22, "Carl", 65, "I hit level 65"),
    (6, 22, "Princess Donut", 57, "Donut level 57"),
    (6, 39, "Carl", 68, "I was now level 68"),
    (6, 39, "Princess Donut", 59, "Donut was level 59"),
    (6, 39, "Mongo", 40, "Mongo finally hit level 40"),
    (6, 72, "Carl", 73, "You’re level 73"),
    (6, 72, "Princess Donut", 63, "I’m 63"),
)

SERIES_STAT_MILESTONES = (
    (3, 15, "Princess Donut", "CHA", 100, "base", "MY CHARISMA HIT 100"),
    (5, 1, "Carl", "INT", 17, "equipment", "intelligence sat at only 17"),
    (5, 70, "Princess Donut", "CHA", 138, "base", "base charisma currently sat at 138"),
    (5, 70, "Princess Donut", "CHA", 276, "temporary", "charisma was now a god-like 276"),
)


def confidence(value: str) -> str:
    return {"explicit": "verified", "high": "verified", "verified": "verified"}.get(value, "partial")


def event_id(*parts: object) -> str:
    return re.sub(r"[^a-z0-9]+", "-", "-".join(str(part).lower() for part in parts)).strip("-")


def base(source: dict, *, suffix: str, kind: str, subject: str, name: str, summary: str | None = None) -> dict:
    return {
        "id": event_id(source["id"], suffix),
        "book": source.get("book", 1),
        "chapter": source["chapter"],
        "position": source["position"],
        "type": kind,
        "subject": subject,
        "name": name,
        "summary": summary or source["summary"],
        "source": source.get("anchor"),
        "confidence": confidence(source.get("confidence", "verified")),
    }


def find_source(series_corpus: dict, book: int, chapter: int, needle: str) -> dict:
    book_row = next(row for row in series_corpus["books"] if row["number"] == book)
    chapter_row = next(row for row in book_row["chapters"] if row["number"] == chapter)
    matches = [paragraph for paragraph in chapter_row["paragraphs"] if needle.casefold() in paragraph["text"].casefold()]
    if len(matches) != 1:
        raise ValueError(f"Expected one source for B{book} C{chapter} {needle!r}; found {len(matches)}")
    return matches[0]


def series_progression_events(series_corpus: dict) -> list[dict]:
    events = []
    for book, chapter, subject, level, needle in SERIES_LEVEL_MILESTONES:
        source = find_source(series_corpus, book, chapter, needle)
        events.append(
            {
                "id": event_id("series", book, chapter, subject, "level", level),
                "book": book,
                "chapter": chapter,
                "position": source["position"],
                "type": "level",
                "subject": subject,
                "name": "Character level",
                "summary": f"{subject} is explicitly confirmed at level {level}.",
                "source": source["anchor"],
                "confidence": "verified",
                "action": "set",
                "level": level,
            }
        )
    for book, chapter, subject, stat, value, scope, needle in SERIES_STAT_MILESTONES:
        source = find_source(series_corpus, book, chapter, needle)
        events.append(
            {
                "id": event_id("series", book, chapter, subject, stat, value, scope),
                "book": book,
                "chapter": chapter,
                "position": source["position"],
                "type": "stat",
                "subject": subject,
                "name": f"{stat} confirmation",
                "summary": f"{subject}'s {stat} is explicitly reported as {value}.",
                "source": source["anchor"],
                "confidence": "verified",
                "action": "merge",
                "stats": {stat: value},
                "statScopes": {stat: scope},
            }
        )
    return events


def stat_name(value: str) -> str:
    return {"strength": "STR", "intelligence": "INT", "constitution": "CON", "dexterity": "DEX", "charisma": "CHA"}.get(value.lower(), value.upper())


def stat_scope(source: dict, character: str, stat: str) -> str:
    source_id = source["id"]
    if source_id in BASE_STAT_SOURCES:
        return "base"
    if source_id == "carl-donut-strength-9-18" and character == "Princess Donut":
        return "base"
    if source_id == "carl-intelligence-3-donut-dexterity-12" and character == "Carl":
        return "base"
    if source_id in TEMPORARY_STAT_SOURCES:
        return "temporary"
    if source_id in EQUIPMENT_STAT_SOURCES:
        return "equipment"
    return "reported"


def skill_event(source: dict, character: str, item: dict, suffix: str) -> dict:
    name = item.get("skill") or item.get("spell") or item.get("name") or "Unnamed ability"
    level = item.get("to_level", item.get("to", item.get("level")))
    event = base(source, suffix=suffix, kind="skill", subject=character, name=name)
    event.update({"action": "set", "level": level, "detail": source.get("summary")})
    return event


def character_events(audit: dict) -> list[dict]:
    output: list[dict] = []
    for source in audit["events"]:
        category = source["category"]
        primary = source.get("character")

        if "character_level" in category and primary and source.get("level") is not None:
            event = base(source, suffix="level", kind="level", subject=primary, name="Character level")
            event.update({"action": "set", "level": source["level"]})
            output.append(event)
        if "character_level" in category and source.get("characters") and source.get("level") is not None:
            for character in source["characters"]:
                event = base(source, suffix=f"level-{character}", kind="level", subject=character, name="Character level")
                event.update({"action": "set", "level": source["level"]})
                output.append(event)

        if primary and source.get("stats"):
            event = base(source, suffix="stats", kind="stat", subject=primary, name="Character stats")
            stats = {stat_name(k): v for k, v in source["stats"].items()}
            scopes = {stat_name(k): stat_scope(source, primary, k) for k in source["stats"]}
            event.update({"action": "merge", "stats": stats, "statScopes": scopes})
            output.append(event)
        if primary and source.get("stat") and source.get("to") is not None:
            event = base(source, suffix="stat", kind="stat", subject=primary, name=f"{source['stat'].title()} change")
            name = stat_name(source["stat"])
            event.update({"action": "merge", "stats": {name: source["to"]}, "statScopes": {name: stat_scope(source, primary, source["stat"])}})
            output.append(event)
        if primary and source.get("stat_changes"):
            event = base(source, suffix="stat-delta", kind="stat", subject=primary, name="Stat change")
            deltas = {stat_name(row["stat"]): row["delta"] for row in source["stat_changes"]}
            scopes = {stat_name(row["stat"]): stat_scope(source, primary, row["stat"]) for row in source["stat_changes"]}
            event.update({"action": "delta", "statsDelta": deltas, "statScopes": scopes})
            output.append(event)
        if source.get("stats_by_character"):
            for character, stats in source["stats_by_character"].items():
                event = base(source, suffix=f"stats-{character}", kind="stat", subject=character, name="Character stats")
                normalized = {stat_name(k): v for k, v in stats.items()}
                scopes = {stat_name(k): stat_scope(source, character, k) for k in stats}
                event.update({"action": "merge", "stats": normalized, "statScopes": scopes})
                output.append(event)

        if primary and (source.get("skill") or source.get("spell")):
            output.append(skill_event(source, primary, source, "ability"))
        if primary and source.get("skills"):
            for index, item in enumerate(source["skills"]):
                output.append(skill_event(source, primary, item, f"skill-{index}"))
        if primary and source.get("skill_changes"):
            for index, item in enumerate(source["skill_changes"]):
                output.append(skill_event(source, primary, item, f"skill-change-{index}"))
        if source.get("changes_by_character"):
            for character, changes in source["changes_by_character"].items():
                for index, item in enumerate(changes):
                    output.append(skill_event(source, character, item, f"change-{character}-{index}"))

        if not any(event["source"] == source.get("anchor") for event in output[-8:]):
            output.append(base(source, suffix="story", kind="story", subject=primary or "Party", name=category.replace("_", " ").title()))
    return output


def inventory_action(action: str, item: dict) -> str:
    state = str(item.get("state", "")).lower()
    if any(word in state for word in ("consumed", "destroyed", "no longer held", "returned", "released")):
        return "remove"
    if action in {"consume", "destroy", "transfer", "use", "craft_and_consume"}:
        if "survived" in state:
            return "add"
        return "remove"
    if action == "equip" or state == "equipped":
        return "equip"
    return "add"


def inventory_events(audit: dict) -> list[dict]:
    output: list[dict] = []
    for party in audit["party_events"]:
        if party["action"] == "form":
            for member in party["members_after"]:
                event = base(party, suffix=f"join-{member}", kind="party", subject=member, name="Party membership")
                event.update({"action": "join", "membersAfter": party["members_after"]})
                output.append(event)
        elif party["action"] == "join":
            new_member = next(member for member in party["members_after"] if member == "Mongo")
            event = base(party, suffix="join", kind="party", subject=new_member, name="Party membership")
            event.update({"action": "join", "membersAfter": party["members_after"]})
            output.append(event)
        else:
            event = base(party, suffix=party["action"], kind="party", subject="Party", name=party.get("party_name") or "Party change")
            event.update({"action": party["action"], "membersAfter": party["members_after"], "leader": party.get("leader")})
            output.append(event)

    for source in audit["inventory_events"]:
        # Temporary transfers and history-only discoveries belong in history,
        # but should not create active inventory rows.
        history_only = source["action"] in {"temporary_transfer", "history_discovery"}
        if source["id"] == "inv-004-first-ten-boxes-opened":
            for index, name in enumerate(INITIAL_BOXES):
                event = base(source, suffix=f"opened-box-{index}", kind="item", subject="Carl", name=name)
                event.update({"action": "remove", "quantity": 1, "category": "Reward box", "state": "opened"})
                output.append(event)
        for index, item in enumerate(source.get("items", [])):
            owner = item.get("owner") or source["actor"]
            split = item.get("owner_split")
            owners = list(split) if split else [owner]
            for owner_index, actual_owner in enumerate(owners):
                action = "remove" if history_only else inventory_action(source["action"], item)
                name = ITEM_ALIASES.get(item["name"], item["name"])
                event = base(source, suffix=f"item-{index}-{owner_index}", kind="item", subject=actual_owner, name=name)
                event.update(
                    {
                        "action": action,
                        "quantity": split.get(actual_owner) if split else item.get("quantity"),
                        "unit": item.get("unit"),
                        "category": item.get("category") or "Inventory",
                        "state": item.get("state", "equipped" if action == "equip" else "carried"),
                        "detail": item.get("quantity_note") or item.get("inputs") or item.get("destination"),
                        "historyOnly": history_only,
                    }
                )
                output.append(event)
        # One readable history row summarizes each inventory operation.
        output.append(base(source, suffix="summary", kind="story", subject=source["actor"], name=source["action"].replace("_", " ").title()))
    return output


def main() -> None:
    character = json.loads(CHARACTER_AUDIT.read_text(encoding="utf-8"))
    inventory = json.loads(INVENTORY_AUDIT.read_text(encoding="utf-8"))
    series_corpus = json.loads(SERIES_CORPUS.read_text(encoding="utf-8"))
    events = character_events(character) + inventory_events(inventory) + series_progression_events(series_corpus)
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    anchor_positions = {
        paragraph["anchor"]: paragraph["position"]
        for chapter in corpus["chapters"]
        for paragraph in chapter["paragraphs"]
    }
    for event in events:
        if event.get("source") in anchor_positions:
            event["position"] = anchor_positions[event["source"]]
    book_rows = []
    chapter_offset = 0
    for row in series_corpus["books"]:
        book_rows.append(
            {
                "id": row["id"],
                "number": row["number"],
                "title": row["title"],
                "chapterCount": row["chapterCount"],
                "startChapter": chapter_offset + 1,
                "endChapter": chapter_offset + row["chapterCount"],
            }
        )
        chapter_offset += row["chapterCount"]
    total_chapters = chapter_offset
    offsets = {row["number"]: row["startChapter"] - 1 for row in book_rows}
    for event in events:
        event["book"] = event.get("book", 1)
        event["progress"] = round((offsets[event["book"]] + event["chapter"] - 1 + event["position"]) / total_chapters, 8)
    events.sort(key=lambda row: (row["progress"], row["id"]))
    # A later status screen sometimes repeats the same character level. Keep
    # the first reveal so the chart marks when that level was actually reached.
    deduped_events = []
    seen_levels = set()
    for event in events:
        if event["type"] == "level":
            level_key = (event["subject"], event.get("level"))
            if level_key in seen_levels:
                continue
            seen_levels.add(level_key)
        deduped_events.append(event)
    events = deduped_events
    payload = {
        "series": {
            "id": "dcc",
            "title": "Dungeon Crawler Carl",
            "bookCount": len(book_rows),
            "chapterCount": total_chapters,
            "dataVersion": "2.0.0",
            "coverageNote": "Eight-book chapter map with source-anchored explicit progression. Detailed skills and inventory remain most complete for Book 1.",
        },
        "books": book_rows,
        "characters": [
            {"id": "carl", "name": "Carl", "role": "Royal Bodyguard", "color": "#d8ff3e"},
            {"id": "princess-donut", "name": "Princess Donut", "role": "Party leader", "color": "#4dd9d2"},
            {"id": "mongo", "name": "Mongo", "role": "Donut's bonded pet", "color": "#ff6441"},
        ],
        "events": events,
        "audit": {
            "characterEvents": len(character["events"]),
            "inventoryEvents": len(inventory["inventory_events"]),
            "knownGaps": character.get("audit_gaps", []) + inventory.get("known_gaps", []),
        },
    }
    encoded = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    OUTPUT.write_text(encoded, encoding="utf-8")
    LEGACY_OUTPUT.write_text(encoded, encoding="utf-8")
    print(f"Wrote {len(events)} public events to {OUTPUT}")


if __name__ == "__main__":
    main()
