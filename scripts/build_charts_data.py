#!/usr/bin/env python
"""Flatten the public Crawl Atlas timeline for dbt Charts.

Only public, source-anchored facts are exported. EPUB prose and private corpus
content never enter these files.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "site" / "dist" / "data" / "series.json"
OUTPUT = ROOT / "charts" / "data"


def write_csv(name: str, fieldnames: list[str], rows: list[dict]) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / name).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    characters = {character["name"]: character for character in data["characters"]}
    events = sorted(data["events"], key=lambda event: (event["progress"], event["id"]))

    metrics: list[dict] = []
    skills: list[dict] = []
    inventory: list[dict] = []
    relationships: list[dict] = []
    latest_relationship: dict[str, str] = {}
    latest_level: dict[str, int] = {}

    for event in events:
        common = {
            "series_progress": round(event["progress"] * 100, 6),
            "book": event["book"],
            "chapter": event["chapter"],
            "chapter_position": round(event["position"] * 100, 2),
            "character": event["subject"],
            "summary": event["summary"],
            "source": event["source"],
        }
        if event["type"] == "level":
            latest_level[event["subject"]] = event["level"]
            metrics.append({**common, "metric": "Level", "value": event["level"], "scope": "confirmed"})
        elif event["type"] == "stat":
            for metric, value in event.get("stats", {}).items():
                metrics.append(
                    {
                        **common,
                        "metric": metric,
                        "value": value,
                        "scope": event.get("statScopes", {}).get(metric, "reported"),
                    }
                )
        elif event["type"] == "skill":
            skills.append(
                {
                    **common,
                    "skill": event["name"],
                    "level": event.get("level") or "",
                    "detail": event.get("detail") or "",
                }
            )
        elif event["type"] == "item":
            inventory.append(
                {
                    **common,
                    "item": event["name"],
                    "action": event.get("action", ""),
                    "state": event.get("state") or "",
                    "quantity": event.get("quantity") or "",
                    "category": event.get("category") or "",
                }
            )
        elif event["type"] == "party" and event.get("relationship"):
            latest_relationship[event["subject"]] = event["relationship"]
            relationships.append({**common, "relationship": event["relationship"]})

    roster = []
    for name, character in characters.items():
        roster.append(
            {
                "character": name,
                "group_name": character["group"],
                "role": character["role"],
                "relationship": latest_relationship.get(name, character["role"]),
                "latest_confirmed_level": latest_level.get(name, ""),
            }
        )

    write_csv(
        "metrics.csv",
        ["series_progress", "book", "chapter", "chapter_position", "character", "metric", "value", "scope", "summary", "source"],
        metrics,
    )
    write_csv(
        "skills.csv",
        ["series_progress", "book", "chapter", "chapter_position", "character", "skill", "level", "detail", "summary", "source"],
        skills,
    )
    write_csv(
        "inventory.csv",
        ["series_progress", "book", "chapter", "chapter_position", "character", "item", "action", "state", "quantity", "category", "summary", "source"],
        inventory,
    )
    write_csv(
        "relationships.csv",
        ["series_progress", "book", "chapter", "chapter_position", "character", "relationship", "summary", "source"],
        relationships,
    )
    write_csv(
        "roster.csv",
        ["character", "group_name", "role", "relationship", "latest_confirmed_level"],
        roster,
    )
    print(
        f"Wrote {len(metrics)} metrics, {len(skills)} skills, "
        f"{len(inventory)} inventory events, and {len(relationships)} relationship events"
    )


if __name__ == "__main__":
    main()
