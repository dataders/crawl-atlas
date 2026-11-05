"""Build the static dbt Charts snapshots selected by the reader's spoiler boundary."""
import json
import subprocess
import tempfile
from pathlib import Path
from check_reader_exports import record
from reader_book_axis import finish_book_axes

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "site/dist"
out = DIST / "charts"
out.mkdir(exist_ok=True)
compact = out / "compact"
compact.mkdir(exist_ok=True)
rows = json.loads((DIST / "data/progression.json").read_text())
series = json.loads((DIST / "data/series.json").read_text())
cast_colors = {c["name"]: c["color"] for c in series["characters"]}


def book_axis(n):
    # dct's static label pass can present numeric ticks as dates from the epoch.
    v = "(isDate(datum.value) ? toNumber(datum.value)/86400000 : toNumber(datum.value))"
    step = 25 if n == 1 else 50
    prefix = "Book " if n <= 3 else "B"
    minor = f"({v}%100) + '%'" if n <= 3 else "''"
    expr = (f"{v} === {100*n} ? " + ("'100%'" if n <= 3 else "''") +
            f" : {v}%100 === 0 ? '{prefix}' + (1+{v}/100) : {minor}")
    return {"scale": {"nice": False, "values": list(range(0, n*100+1, step)),
                      "continuous": {"domain": [0, n*100]}},
            "ticks": {"step": step}, "labels": {"expr": expr}}


boundaries = [{"book": b["number"], "event_id": f"book-start-{b['number']}",
               "kind": "level", "progress": (b["startChapter"]-1)/series["series"]["chapterCount"]}
              for b in series["books"][1:]]
with tempfile.TemporaryDirectory(dir=ROOT) as scratch:
    boards = {}
    book_counts = {}
    metrics = {"Level": "Level", "STR": "Strength", "INT": "Intelligence",
               "CON": "Constitution", "DEX": "Dexterity", "CHA": "Charisma"}
    for row in [*rows, *boundaries]:
        if row["kind"] not in ("level", "stat") or row["event_id"] in boards:
            continue
        visible = [r for r in rows if r["kind"] in ("level", "stat") and r["progress"] <= row["progress"]]
        spec = {"extends": "neon", "source": "crawl_atlas", "rows": [],
                "style": {"background": "#161c18", "charts": {
                    "category_colors": {"crawler": {"values": {
                        r["character"]: cast_colors[r["character"]] for r in visible if r["character"] in cast_colors}}},
                    "axis_x": {"grid": {"visible": False}},
                    "axis_y": {"grid": {"opacity": 0.2}}}},
                "queries": {}, "charts": {}}
        for metric, title in metrics.items():
            points = [r for r in visible if r["metric"] == metric and (metric == "Level" or r["scope"] == "base")]
            title = title if metric == "Level" else f"Base {title.lower()}"
            if not any(r["value"] is not None for r in points):
                spec["rows"].append({"title": title, "text": "No value recorded yet."})
                continue
            spec["queries"][metric] = f"""SELECT (book-1)*100 + 100.0*(chapter-1+position)/chapter_count AS book_position, value, character AS crawler
                FROM progression JOIN books ON books.number = progression.book WHERE metric = '{metric}'
                AND (kind = 'level' OR (kind = 'stat' AND scope = 'base'))
                AND value IS NOT NULL AND progress <= {row["progress"]}
                ORDER BY progress, character"""
            chart = {"title": title, "color": "crawler", "type": "line", "query": metric,
                     "x": "book_position", "x_label": ("Progress within book" if row["book"] <= 3 else "Book start · minor ticks mark 50%"), "y": "value",
                     "y_label": title, "style": {"axis_x": book_axis(row["book"])},
                     "height": 240, "layers": [{"type": "scatter", "y": "value", "color": "crawler"}]}
            spec["charts"][metric] = chart
            spec["rows"].append(metric)
        spec["queries"]["levels"] = f"""
            WITH ranked AS (
                SELECT character, value, book, chapter,
                       ROW_NUMBER() OVER (PARTITION BY character ORDER BY progress DESC, event_id DESC) AS rank
                FROM progression WHERE kind = 'level' AND progress <= {row["progress"]}
            )
            SELECT character, COALESCE(CAST(CAST(value AS INTEGER) AS TEXT), 'Unknown') AS level,
                   'B' || book || ' · Ch ' || chapter AS observed_at
            FROM ranked WHERE rank = 1 ORDER BY character"""
        spec["charts"]["levels"] = {"type": "table", "query": "levels",
            "title": "Latest level observations", "warnings_ignore": ["WARN-QUERY-RETURNED-ZERO-ROWS"]}
        boards[row["event_id"]] = spec
        book_counts[row["event_id"]] = row["book"]
    for columns, width, destination in [(1, 440, compact), (3, 1360, out)]:
        paths = []
        for event_id, spec in boards.items():
            items = spec["rows"]
            layout = items if columns == 1 else [{"cols": items[i:i+3]} for i in (0, 3)]
            board = Path(scratch) / f"{event_id}.yml"
            board.write_text(json.dumps({**spec, "width": width, "rows": [*layout, "levels"],
                "style": {**spec["style"], "frame": {"margin": 16, "card_gap": 12}}}))
            paths.append(str(board))
        subprocess.run(["dct", "render", *paths, "--no-cache", "--project-dir", str(ROOT),
                        "--format", "html", "--output", str(destination / "{stem}.html")], check=True)
        for board in paths:
            html = destination / (Path(board).stem + ".html")
            link = '<link rel="stylesheet" href="/chart-sizing.css">'
            html.write_text(finish_book_axes(html.read_text(), book_counts[Path(board).stem]).replace("</head>", link + "</head>", 1))
record()
