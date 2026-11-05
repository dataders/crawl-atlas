"""Build the static dbt Charts snapshots selected by the reader's spoiler boundary."""
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "site/dist"
out = DIST / "charts"
out.mkdir(exist_ok=True)
compact = out / "compact"
compact.mkdir(exist_ok=True)
rows = json.loads((DIST / "data/progression.json").read_text())
with tempfile.TemporaryDirectory(dir=ROOT) as scratch:
    boards = {}
    metrics = {"Level": "Level", "STR": "Strength", "INT": "Intelligence",
               "CON": "Constitution", "DEX": "Dexterity", "CHA": "Charisma"}
    for row in rows:
        if row["kind"] not in ("level", "stat") or row["event_id"] in boards:
            continue
        visible = [r for r in rows if r["kind"] in ("level", "stat") and r["progress"] <= row["progress"]]
        spec = {"extends": "neon", "source": "crawl_atlas", "rows": [],
                "queries": {}, "charts": {}}
        for metric, title in metrics.items():
            points = [r for r in visible if r["metric"] == metric]
            if not any(r["value"] is not None for r in points):
                spec["rows"].append({"title": title, "text": "No value recorded yet."})
                continue
            spec["queries"][metric] = f"""SELECT progress * 100 AS series_percent, value,
                CASE WHEN kind = 'level' OR scope = 'base' THEN character
                     ELSE character || ' · ' || scope END AS crawler
                FROM progression WHERE metric = '{metric}'
                AND kind IN ('level','stat') AND value IS NOT NULL AND progress <= {row["progress"]}
                ORDER BY progress, character"""
            chart = {"title": title, "color": "crawler", "type": "line", "query": metric,
                     "x": "series_percent", "x_label": "Series read (%)", "y": "value",
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
            "title": "Latest level observations", "warnings_ignore": ["WARN-QUERY-RETURNED-ZERO-ROWS"],
            "style": {"pagination": {"page_rows": 20}}}
        boards[row["event_id"]] = spec
    for columns, width, destination in [(1, 440, compact), (3, 1360, out)]:
        paths = []
        for event_id, spec in boards.items():
            items = spec["rows"]
            layout = items if columns == 1 else [{"cols": items[i:i+3]} for i in (0, 3)]
            board = Path(scratch) / f"{event_id}.yml"
            board.write_text(json.dumps({**spec, "rows": [*layout, "levels"], "style": {"frame": {"width": width}}}))
            paths.append(str(board))
        subprocess.run(["dct", "render", *paths, "--no-cache", "--project-dir", str(ROOT),
                        "--format", "html", "--output", str(destination / "{stem}.html")], check=True)
        for board in paths:
            html = destination / (Path(board).stem + ".html")
            link = '<link rel="stylesheet" href="/chart-sizing.css">'
            html.write_text(html.read_text().replace("</head>", link + "</head>", 1))
