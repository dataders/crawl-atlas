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
    (1, 3, "Mordecai", 50, "Mordecai – Rat Hooligan. Level 50"),
    (1, 23, "Imani C.", 10, "She was level 10"),
    (1, 37, "Imani C.", 11, "Imani was still level 11"),
    (2, 21, "Katia Grim", 9, "anchor:b2-c21-p31"),
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
    (3, 3, "Prepotente", 27, "Prepotente – Caprid – Forsaken Aerialist – Level 27"),
    (3, 3, "Elle McGib", 17, "Elle McGib – Frost Maiden – Blizzardmancer – Level 17"),
    (3, 6, "Mongo", 14, "Mongo managed to hit level 14"),
    (3, 6, "Katia Grim", 22, "Katia hit 22"),
    (3, 7, "Mongo", 15, "Mongo hit level 15"),
    (3, 11, "Carl", 29, "You are now level 29"),
    (3, 14, "Carl", 32, "I was now level 32"),
    (3, 12, "Princess Donut", 28, "I hit level 28"),
    (3, 12, "Katia Grim", 24, "gone up a level to 24"),
    (3, 15, "Princess Donut", 30, "TWO LEVELS TO LEVEL 30"),
    (3, 25, "Carl", 34, "Carl – Primal – Compensated Anarchist – Level 34"),
    (3, 25, "Princess Donut", 32, "Donut – Cat – Former Child Actor – Level 32"),
    (3, 23, "Katia Grim", 37, "she was now level 37"),
    (3, 25, "Prepotente", 34, "Prepotente – Caprid – Forsaken Aerialist – Level 34"),
    (3, 26, "Mongo", 23, "Mongo had recently risen to level 23"),
    (3, 27, "Carl", 35, "I hit level 35"),
    (3, 34, "Carl", 41, "I just hit 41"),
    (4, 2, "Carl", 41, "your level 41"),
    (4, 4, "Princess Donut", 33, "Donut – Cat – Former Child Actor – Level 33"),
    (4, 3, "Louis Santiago", 22, "level-22 Pest Exterminator named Louis Santiago 2"),
    (4, 4, "Prepotente", 35, "Prepotente – Caprid – Forsaken Aerialist – Level 35"),
    (4, 4, "Elle McGib", 33, "Elle McGib – Frost Maiden – Blizzardmancer – Level 33"),
    (4, 6, "Louis Santiago", 24, "also gone up to level 24"),
    (4, 12, "Princess Donut", 34, "Level 34!"),
    (4, 17, "Carl", 44, "I was now at 44"),
    (4, 17, "Princess Donut", 37, "Donut was 37"),
    (4, 17, "Mongo", 33, "hitting level 33"),
    (4, 17, "Prepotente", 38, "Prepotente – Caprid – Forsaken Aerialist – Level 38"),
    (4, 17, "Elle McGib", 35, "Elle McGib – Frost Maiden – Blizzardmancer – Level 35"),
    (4, 19, "Katia Grim", 41, "now level 41"),
    (4, 20, "Louis Santiago", 30, "leveled up to 30"),
    (4, 28, "Carl", 47, "gone up three levels to 47"),
    (4, 28, "Princess Donut", 39, "Donut was level 39"),
    (4, 28, "Katia Grim", 44, "taking her to 44"),
    (4, 33, "Prepotente", 55, "bringing him up to 55"),
    (5, 3, "Katia Grim", 52, "She was now level 52"),
    (5, 6, "Carl", 54, "rocketed up to level 54"),
    (5, 6, "Princess Donut", 41, "few levels to 41"),
    (5, 51, "Princess Donut", 47, "TWO LEVELS TO 47"),
    (5, 49, "Prepotente", 57, "Prepotente was currently level 57"),
    (5, 57, "Prepotente", 70, "you made it to level 70"),
    (5, 39, "Carl", 56, "I remained at 56"),
    (5, 61, "Carl", 59, "player level up to 59"),
    (5, 61, "Princess Donut", 50, "her level to 50"),
    (5, 65, "Katia Grim", 55, "equal with Katia"),
    (5, 75, "Carl", 63, "You’re 63!"),
    (5, 75, "Princess Donut", 55, "I went up to 55"),
    (5, 75, "Katia Grim", 60, "Katia is 60"),
    (5, 75, "Prepotente", 71, "Prepotente went to 71"),
    (6, 22, "Carl", 65, "I hit level 65"),
    (6, 22, "Princess Donut", 57, "Donut level 57"),
    (6, 39, "Carl", 68, "I was now level 68"),
    (6, 39, "Princess Donut", 59, "Donut was level 59"),
    (6, 39, "Mongo", 40, "Mongo finally hit level 40"),
    (6, 72, "Carl", 73, "You’re level 73"),
    (6, 72, "Princess Donut", 63, "I’m 63"),
    (6, 65, "Elle McGib", 72, "settling her onto level 72"),
    (7, 48, "Prepotente", 99, "he was now level 99"),
    (7, 56, "Li Na", 84, "recently just shot up to level 84"),
    (7, 51, "Carl", 75, "I was only level 75"),
    (7, 77, "Carl", 81, "up to level 81"),
    (7, 77, "Prepotente", 100, "Prepotente at level 100"),
    (7, 79, "Elle McGib", 135, "now level 135"),
)

SERIES_STAT_MILESTONES = (
    (3, 1, "Katia Grim", "CON", 102, "temporary", "My constitution is double what it normally is. I’m at 102"),
    (3, 1, "Katia Grim", "STR", 11, "reported", "Katia’s strength of 11"),
    (3, 13, "Katia Grim", "STR", 49, "equipment", "she was now at 49 after all her enhancements"),
    # The Book 2 selection screen explicitly separates Carl's unmodified
    # values from equipment arithmetic, so both series can be plotted without
    # treating an item-enhanced total as a base stat.
    (2, 2, "Carl", "STR", 10, "base", "Strength: 10 + 3"),
    (2, 2, "Carl", "STR", 16, "equipment", "Strength: 10 + 3"),
    (2, 2, "Carl", "INT", 5, "base", "Intelligence: 5"),
    (2, 2, "Carl", "CON", 10, "base", "Constitution: 10 + 4"),
    (2, 2, "Carl", "CON", 19, "equipment", "Constitution: 10 + 4"),
    (2, 2, "Carl", "DEX", 10, "base", "Dexterity: 10 + 1"),
    (2, 2, "Carl", "DEX", 11, "equipment", "Dexterity: 10 + 1"),
    (2, 2, "Carl", "CHA", 25, "base", "Charisma: 25"),
    # The later Book 3 display is explicit, but not every number is cleanly
    # separable from persistent gear, so it remains a reported total.
    (3, 2, "Carl", "STR", 41, "reported", "Strength: 41 +3"),
    (3, 2, "Carl", "INT", 15, "reported", "Intelligence: 15"),
    (3, 2, "Carl", "CON", 34, "reported", "Constitution: 34"),
    (3, 2, "Carl", "DEX", 23, "reported", "Dexterity: 23"),
    (3, 2, "Carl", "CHA", 25, "reported", "Charisma: 25"),
    (3, 15, "Princess Donut", "CHA", 100, "base", "MY CHARISMA HIT 100"),
    (5, 1, "Carl", "INT", 17, "equipment", "intelligence sat at only 17"),
    (5, 70, "Princess Donut", "CHA", 138, "base", "base charisma currently sat at 138"),
    (5, 70, "Princess Donut", "CHA", 276, "temporary", "charisma was now a god-like 276"),
)

SERIES_ROSTER_MILESTONES = (
    (1, 2, "Mordecai", "Registered game guide", "Nobody tells old Mordecai anything", "Carl meets Mordecai, who becomes the party's registered guide."),
    (1, 22, "Imani C.", "Meadow Lark ally", "her name was Imani C.", "Imani becomes known as a capable allied crawler from Meadow Lark."),
    (1, 31, "Elle McGib", "Meadow Lark ally", "her name was Elle McGibbons", "Elle becomes known as a surviving Meadow Lark crawler."),
    (1, 42, "Li Na", "Allied crawler", "my sister, Li Na", "Li Na becomes known through the surviving crawler network."),
    (2, 1, "Mordecai", "Party manager", "I’m the manager", "Mordecai becomes Donut's manager and permanent support specialist."),
    (2, 21, "Katia Grim", "Temporary party member", "let her join your party", "Katia temporarily joins Donut's party to train and share experience."),
    (3, 3, "Prepotente", "Independent allied crawler", "His name was Prepotente", "Prepotente becomes known as a powerful independent crawler allied with Miriam Dom."),
    (3, 25, "Katia Grim", "Core party member", "now and forever a part of the team", "Katia is accepted as a permanent member of Carl and Donut's core team."),
    (4, 3, "Louis Santiago", "Allied crawler and pilot", "named Louis Santiago 2", "Louis becomes known as an allied crawler and vehicle specialist."),
    (4, 24, "Samantha", "Companion", "Samantha as her friends used to call her", "Samantha becomes known to the group as a dangerous but recurring companion."),
    (5, 1, "Katia Grim", "Allied team leader", "Katia was leaving the party", "Katia leaves the formal party while remaining a close ally and team leader."),
    (5, 20, "Imani C.", "Princess Posse guildmaster", "talked Imani into being the guildmaster", "Imani becomes guildmaster of the broader allied crawler network."),
)

SERIES_SKILL_MILESTONES = (
    (2, 25, "Katia Grim", "Rush", None, "active skill called Rush"),
    (3, 1, "Katia Grim", "Pathfinder", None, "You have the Pathfinder skill"),
    (3, 3, "Katia Grim", "Catcher", None, "Katia was to train her Catcher skill"),
    (3, 25, "Katia Grim", "Find Crawler", 3, "skill potion that gave her the Find Crawler skill"),
    (3, 29, "Katia Grim", "Crowd Blast", None, "same battering ram skill Katia had used"),
    (4, 2, "Katia Grim", "Catcher", 11, "raised her Catcher skill"),
    (4, 32, "Katia Grim", "Hanzo", None, "Katia also received a spell called Hanzo"),
    (5, 47, "Prepotente", "Community Pool", None, "Community Pool spell"),
    (5, 62, "Katia Grim", "I Need My Personal Space", None, "spell called I Need My Personal Space"),
    (5, 55, "Imani C.", "Smart Juice", None, "aura I can cast called Smart Juice"),
    (7, 51, "Li Na", "Dark Purpose", 15, "It hit level 15"),
    (7, 52, "Li Na", "Blood Horror", 15, "My Blood Horror is now level 15"),
    (7, 56, "Prepotente", "Iron Stomach", None, "Apparently, Prepotente already had this skill"),
    (7, 64, "Prepotente", "Group psionic protection", None, "Prepotente could protect groups from their long-range psionic abilities"),
    (4, 5, "Louis Santiago", "Cloud of Exhaust", 11, "Cloud spell is Level 11"),
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
    if needle.startswith("anchor:"):
        anchor = needle.removeprefix("anchor:")
        return next(paragraph for paragraph in chapter_row["paragraphs"] if paragraph["anchor"] == anchor)
    matches = [paragraph for paragraph in chapter_row["paragraphs"] if needle.casefold() in paragraph["text"].casefold()]
    if len(matches) != 1:
        raise ValueError(f"Expected one source for B{book} C{chapter} {needle!r}; found {len(matches)}")
    return matches[0]


def series_progression_events(series_corpus: dict) -> list[dict]:
    events = []
    for book, chapter, subject, relationship, needle, summary in SERIES_ROSTER_MILESTONES:
        source = find_source(series_corpus, book, chapter, needle)
        events.append(
            {
                "id": event_id("series", book, chapter, subject, "roster", relationship),
                "book": book,
                "chapter": chapter,
                "position": source["position"],
                "type": "party",
                "subject": subject,
                "name": "Roster relationship",
                "summary": summary,
                "source": source["anchor"],
                "confidence": "verified",
                "action": "join",
                "relationship": relationship,
            }
        )
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
    for book, chapter, subject, skill, level, needle in SERIES_SKILL_MILESTONES:
        source = find_source(series_corpus, book, chapter, needle)
        events.append(
            {
                "id": event_id("series", book, chapter, subject, "skill", skill, level),
                "book": book,
                "chapter": chapter,
                "position": source["position"],
                "type": "skill",
                "subject": subject,
                "name": skill,
                "summary": f"{subject}'s {skill}{f' is explicitly confirmed at level {level}' if level is not None else ' is explicitly confirmed'}.",
                "detail": f"Explicitly confirmed in Book {book}, Chapter {chapter}.",
                "source": source["anchor"],
                "confidence": "verified",
                "action": "set",
                "level": level,
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
            "dataVersion": "2.2.0",
            "coverageNote": "Eight-book chapter map with source-anchored progression for the core party and major recurring allies. Skills and inventory appear only when explicitly confirmed.",
        },
        "books": book_rows,
        "characters": [
            {"id": "carl", "name": "Carl", "role": "Royal Bodyguard", "group": "core", "color": "#d8ff3e"},
            {"id": "princess-donut", "name": "Princess Donut", "role": "Party leader", "group": "core", "color": "#4dd9d2"},
            {"id": "mongo", "name": "Mongo", "role": "Donut's bonded pet", "group": "core", "color": "#ff6441"},
            {"id": "katia-grim", "name": "Katia Grim", "role": "Doppelganger tank", "group": "core", "color": "#ff9f43"},
            {"id": "mordecai", "name": "Mordecai", "role": "Guide, manager, and alchemist", "group": "support", "color": "#f28c67"},
            {"id": "samantha", "name": "Samantha", "role": "Disembodied minor deity", "group": "support", "color": "#ff78c4"},
            {"id": "prepotente", "name": "Prepotente", "role": "Caprid support specialist", "group": "ally", "color": "#c9a66b"},
            {"id": "imani-c", "name": "Imani C.", "role": "Healer and battlefield coordinator", "group": "ally", "color": "#b388ff"},
            {"id": "elle-mcgib", "name": "Elle McGib", "role": "Frost mage", "group": "ally", "color": "#73a7ff"},
            {"id": "li-na", "name": "Li Na", "role": "Dread fighter", "group": "ally", "color": "#e45f9d"},
            {"id": "louis-santiago", "name": "Louis Santiago", "role": "Pest Exterminator and pilot", "group": "ally", "color": "#ffd166"},
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
