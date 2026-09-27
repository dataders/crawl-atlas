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
OUTPUT = ROOT / "site/dist/data/book-1.json"
CORPUS = ROOT / "data/private/corpus.json"
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


def confidence(value: str) -> str:
    return {"explicit": "verified", "high": "verified", "verified": "verified"}.get(value, "partial")


def event_id(*parts: object) -> str:
    return re.sub(r"[^a-z0-9]+", "-", "-".join(str(part).lower() for part in parts)).strip("-")


def base(source: dict, *, suffix: str, kind: str, subject: str, name: str, summary: str | None = None) -> dict:
    return {
        "id": event_id(source["id"], suffix),
        "chapter": source["chapter"],
        "position": source["position"],
        "type": kind,
        "subject": subject,
        "name": name,
        "summary": summary or source["summary"],
        "source": source.get("anchor"),
        "confidence": confidence(source.get("confidence", "verified")),
    }


def stat_name(value: str) -> str:
    return {"strength": "STR", "intelligence": "INT", "constitution": "CON", "dexterity": "DEX", "charisma": "CHA"}.get(value.lower(), value.upper())


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
            event.update({"action": "merge", "stats": {stat_name(k): v for k, v in source["stats"].items()}})
            output.append(event)
        if primary and source.get("stat") and source.get("to") is not None:
            event = base(source, suffix="stat", kind="stat", subject=primary, name=f"{source['stat'].title()} change")
            event.update({"action": "merge", "stats": {stat_name(source["stat"]): source["to"]}})
            output.append(event)
        if primary and source.get("stat_changes"):
            event = base(source, suffix="stat-delta", kind="stat", subject=primary, name="Stat change")
            event.update({"action": "delta", "statsDelta": {stat_name(row["stat"]): row["delta"] for row in source["stat_changes"]}})
            output.append(event)
        if source.get("stats_by_character"):
            for character, stats in source["stats_by_character"].items():
                event = base(source, suffix=f"stats-{character}", kind="stat", subject=character, name="Character stats")
                event.update({"action": "merge", "stats": {stat_name(k): v for k, v in stats.items()}})
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
    events = character_events(character) + inventory_events(inventory)
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    anchor_positions = {
        paragraph["anchor"]: paragraph["position"]
        for chapter in corpus["chapters"]
        for paragraph in chapter["paragraphs"]
    }
    for event in events:
        if event.get("source") in anchor_positions:
            event["position"] = anchor_positions[event["source"]]
    events.sort(key=lambda row: (row["chapter"], row["position"], row["id"]))
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
        "book": {
            "id": "dcc-1",
            "title": "Dungeon Crawler Carl",
            "subtitle": "Book 1",
            "chapterCount": CHAPTER_COUNT,
            "dataVersion": "1.0.0",
            "coverageNote": "Source-anchored audit of named levels, stats, skills, spells, party changes, and inventory events.",
        },
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
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(events)} public events to {OUTPUT}")


if __name__ == "__main__":
    main()
