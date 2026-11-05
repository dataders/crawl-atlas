"""Confirm the deployed HTML matches the reader inputs that generated it."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "charts/reader-exports.json"
INPUTS = ("scripts/render_reader_charts.py", "scripts/reader_book_axis.py", "dbt_charts.yml", "site/dist/data/series.json",
          "site/dist/data/progression.json", "site/dist/data/crawl-atlas.sqlite")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot():
    rows = json.loads((ROOT / "site/dist/data/progression.json").read_text())
    ids = {row["event_id"] for row in rows}
    books = json.loads((ROOT / "site/dist/data/series.json").read_text())["books"]
    ids.update(f"book-start-{b['number']}" for b in books[1:])
    return {
        "inputs": {name: digest(ROOT / name) for name in INPUTS},
        "exports": {name: digest(ROOT / "site/dist/charts" / name)
                    for prefix in ("", "compact/") for event in sorted(ids)
                    for name in [f"{prefix}{event}.html"]},
    }


def record():
    MANIFEST.write_text(json.dumps(snapshot(), indent=2) + "\n")


if __name__ == "__main__":
    if json.loads(MANIFEST.read_text()) != snapshot():
        raise SystemExit("Reader exports are stale. Run uv run python scripts/render_reader_charts.py.")
    print("Verified desktop and compact HTML for every reader checkpoint.")
