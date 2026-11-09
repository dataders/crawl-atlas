"""Render fake dbt Charts checkpoints for the spoiler-free reader demo."""

import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "site/dist"
CHECKPOINTS = (0, 2500, 5000, 7500, 10000)

PROGRESSION = (
    (0, 0, "Subject 01", 2),
    (1200, 18, "Subject 01", 5),
    (2400, 0, "Subject 02", 7),
    (3600, 47, "Subject 01", 4),
    (4800, 31, "Subject 02", 6),
    (5200, 0, "Subject 03", 1),
    (6200, 64, "Subject 02", 10),
    (7000, 52, "Subject 03", 3),
    (7600, 76, "Subject 01", 9),
    (8800, 100, "Subject 02", 8),
    (9400, 100, "Subject 01", 11),
    (10000, 100, "Subject 03", 12),
)

ROSTER = (
    (0, "Subject 01", "Definitely Normal People", "snack monitor", "holder of the clipboard", "suspiciously prepared"),
    (2400, "Subject 02", "Definitely Normal People", "emergency contact", "presses mysterious buttons", "thriving, somehow"),
    (5200, "Subject 03", "Unlicensed Sidekicks", "vibes consultant", "owns one tiny trumpet", "increasingly trumpet-shaped"),
)

RELATIONSHIPS = (
    (0, "Subject 01", "Awkward nodding pact", "Checkpoint 1", "Both parties agreed to pretend that was intentional."),
    (4800, "Subject 02", "Shared umbrella treaty", "Checkpoint 3", "Valid unless the umbrella turns inside out."),
    (7600, "Subject 03", "Tiny trumpet alliance", "Checkpoint 4", "Negotiations were brief and extremely loud."),
)

SKILLS = (
    (0, "Subject 01", "Advanced Loitering", 4, "Checkpoint 1", "Can stand near a doorway with remarkable confidence."),
    (4800, "Subject 02", "Emergency Kazoo", 7, "Checkpoint 3", "Summons one inconvenient musical note."),
    (7600, "Subject 03", "Tactical Snack Folding", 9, "Checkpoint 4", "Creates a smaller, angrier sandwich."),
)

INVENTORY = (
    (0, "Subject 01", "Left Sock of Destiny", "acquired", "slightly damp", 1, "Checkpoint 1"),
    (4800, "Subject 02", "Coupon for One Free Oops", "redeemed", "regrettably expired", 1, "Checkpoint 3"),
    (7600, "Subject 03", "Pocket-Sized Traffic Cone", "equipped", "authoritative", 3, "Checkpoint 4"),
)


def revealed(rows, cutoff):
    return [list(row[1:]) for row in rows if row[0] <= cutoff]


def values(columns, rows):
    return {"type": "values", "columns": columns, "values": rows}


def board(cutoff, width, compact):
    progression = revealed(PROGRESSION, cutoff)
    subjects = len({row[1] for row in progression})
    kpis = ["points_kpi", "subjects_kpi", "spoilers_kpi"]
    kpi_layout = kpis if compact else [{"cols": kpis}]
    return {
        "title": "Crawl Atlas — Spoiler-Free Demo",
        "notes": "All labels, values, events, skills, items, and relationships are invented.",
        "extends": "neon",
        "width": width,
        "style": {
            "background": "#161c18",
            "footer": {"visible": False},
            "timestamp": {"visible": False},
            "frame": {"margin": 16, "card_gap": 12},
        },
        "queries": {
            "headline": values(
                ["totally_real_points", "mystery_silhouettes", "spoilers_leaked", "demo_status"],
                [[len(progression), subjects, 0, "Safe to share"]],
            ),
            "snack_progression": values(
                ["journey_progress", "mystery_subject", "snack_readiness"], progression
            ),
            "anonymous_roster": values(
                ["subject", "group", "relationship", "role", "latest_vibe"], revealed(ROSTER, cutoff)
            ),
            "fake_relationships": values(
                ["subject", "relationship", "changed_at", "summary"], revealed(RELATIONSHIPS, cutoff)
            ),
            "fake_skills": values(
                ["subject", "skill", "level", "confirmed_at", "detail"], revealed(SKILLS, cutoff)
            ),
            "fake_inventory": values(
                ["subject", "item", "action", "state", "quantity", "event_at"], revealed(INVENTORY, cutoff)
            ),
        },
        "charts": {
            "points_kpi": {
                "type": "kpi", "query": "headline", "label": "Invented data points",
                "value": "totally_real_points", "style": {"value": {"format": "integer"}},
            },
            "subjects_kpi": {
                "type": "kpi", "query": "headline", "label": "Mystery silhouettes",
                "value": "mystery_silhouettes", "style": {"value": {"format": "integer"}},
            },
            "spoilers_kpi": {
                "type": "kpi", "query": "headline", "label": "Spoilers leaked", "value": "spoilers_leaked",
                "support": {"value": "demo_status", "label": "Demo status"},
                "style": {"value": {"format": "integer"}},
            },
            "progression": {
                "type": "line", "query": "snack_progression",
                "title": "Fake progression" if compact else "Completely fabricated progression",
                "subtitle": "Numbers selected by a highly unqualified snack committee.",
                "x": "journey_progress", "y": "snack_readiness", "color": "mystery_subject",
                "x_label": "Made-up journey progress (%)", "y_label": "Emergency snack readiness (nachos)",
                "height": 320 if not compact else 240,
                "style": {"axis_y": {"scale": {"values": [0, 3, 6, 9, 12], "continuous": {"domain": [0, 12]}}}},
            },
            "roster": {
                "type": "table", "query": "anonymous_roster", "title": "Anonymous demo cast",
                **({"style": {"columns": {
                    "group": {"visible": False}, "relationship": {"visible": False},
                    "latest_vibe": {"visible": False},
                }}} if compact else {}),
            },
            "relationships": {
                "type": "table", "query": "fake_relationships", "title": "Entirely fictional alliances",
                **({"style": {"columns": {"summary": {"visible": False}}}} if compact else {}),
            },
            "skills": {
                "type": "table", "query": "fake_skills", "title": "Highly questionable talents",
                **({"style": {"columns": {
                    "confirmed_at": {"visible": False}, "detail": {"visible": False},
                }}} if compact else {}),
            },
            "inventory": {
                "type": "table", "query": "fake_inventory", "title": "Dubious pocket contents",
                **({"style": {"columns": {
                    "state": {"visible": False}, "event_at": {"visible": False},
                }}} if compact else {}),
            },
        },
        "rows": [
            {"text": "**Spoiler shield active.** Everything here is fake, including the nachos."},
            *kpi_layout, "progression", "roster", "relationships", "skills", "inventory",
        ],
    }


def write_demo_catalog():
    books = [
        {"number": number, "title": title, "chapterCount": 10,
         "startChapter": 1 + (number - 1) * 10, "endChapter": number * 10}
        for number, title in enumerate((
            "The Suspicious Welcome Mat", "A Completely Ordinary Tuesday",
            "The Coupon Strikes Back", "Trouble at the Snack Kiosk",
            "Return of the Tiny Trumpet", "Six Geese, No Explanation",
            "The Spreadsheet of Destiny", "Nachos at the End of Everything",
        ), start=1)
    ]
    payload = {
        "series": {"title": "The Extremely Serious Dungeon Chronicles", "bookCount": 8,
                   "chapterCount": 80, "dataVersion": "FAKE-1"},
        "books": books,
        "characters": [],
        "events": [],
        "checkpoints": [
            {"progress": value / 10000, "book": min(8, value // 1250 + 1),
             "event_id": f"spoiler-free-{value:04d}"}
            for value in CHECKPOINTS
        ],
    }
    (DIST / "data/spoiler-free.json").write_text(json.dumps(payload, indent=2) + "\n")


def main():
    write_demo_catalog()
    with tempfile.TemporaryDirectory(dir=ROOT) as scratch:
        scratch_path = Path(scratch)
        for width, compact in ((1360, False), (440, True)):
            destination = DIST / "charts" / ("compact" if compact else "")
            destination.mkdir(parents=True, exist_ok=True)
            paths = []
            for cutoff in CHECKPOINTS:
                path = scratch_path / f"spoiler-free-{cutoff:04d}.yml"
                path.write_text(json.dumps(board(cutoff, width, compact)))
                paths.append(str(path))
            subprocess.run([
                "dct", "render", *paths, "--no-cache", "--project-dir", str(ROOT),
                "--format", "html", "--output", str(destination / "{stem}.html"),
            ], check=True)


if __name__ == "__main__":
    main()
