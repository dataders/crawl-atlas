"""Compile the editable book ledgers into the existing reader data contract."""
import json
from pathlib import Path

from reward_provenance import acquisition_rows

ROOT = Path(__file__).resolve().parents[1]


def compile_books(public):
    books, events, characters, readings, catalogs = [], [], [], [], []
    for path in sorted(public.glob("book-*.jsonl")):
        book = int(path.stem.split("-")[1])
        for n, line in enumerate(path.read_text().splitlines(), 1):
            row = json.loads(line)
            kind = row.pop("recordType")
            meta = row.pop("metadata", {})
            if row.get("book", book) != book:
                raise ValueError(f"{path}:{n}: wrong book")
            if kind == "event":
                events.append(row)
            elif kind == "book" and row["number"] == book:
                books.append(row)
            elif kind == "catalog":
                catalogs.append(row)
            elif kind == "character":
                characters.append((meta["order"], row))
            elif kind == "statReading":
                readings.append((meta["order"], row))
            else:
                raise ValueError(f"{path}:{n}: unexpected {kind}")
    catalog, = catalogs
    if [b["number"] for b in books] != list(range(1, catalog["series"]["bookCount"] + 1)):
        raise ValueError("Missing or duplicated book")
    events.sort(key=lambda e: (e["progress"], e["id"]))
    if len({e["id"] for e in events}) != len(events):
        raise ValueError("Duplicate event ID")
    acquisition_rows(events)
    return (dict(series=catalog["series"], books=books, characters=[v for _, v in sorted(characters)],
                 events=events, audit=catalog["audit"]),
            dict(scope=catalog["statScope"], observations=[v for _, v in sorted(readings)]))


if __name__ == "__main__":
    public = ROOT / "data/public"
    series, stats = compile_books(public)
    def write(path, value):
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    for name in ("series.json", "book-1.json"):
        write(ROOT / "site/dist/data" / name, series)
    write(public / "stat-breakdown-audit.json", stats)
