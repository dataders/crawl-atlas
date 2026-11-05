"""Build the static dbt Charts snapshots selected by the reader's spoiler boundary."""
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "site/dist"
out = DIST / "reader-charts"
out.mkdir(exist_ok=True)
rows = json.loads((DIST / "data/progression.json").read_text())
with tempfile.TemporaryDirectory(dir=ROOT) as scratch:
    boards = {}
    metrics = {"Level": "Level", "STR": "Strength", "INT": "Intelligence",
               "CON": "Constitution", "DEX": "Dexterity", "CHA": "Charisma"}
    for row in rows:
        if row["kind"] not in ("level", "stat") or row["event_id"] in boards:
            continue
        visible = [r for r in rows if r["character"] == row["character"]
                   and r["kind"] in ("level", "stat") and r["progress"] <= row["progress"]]
        spec = {"extends": "neon", "source": "crawl_atlas", "rows": [],
                "queries": {}, "charts": {}}
        name = row["character"].replace("'", "''")
        for metric, title in metrics.items():
            points = [r for r in visible if r["metric"] == metric]
            if not any(r["value"] is not None for r in points):
                spec["rows"].append({"title": title, "text": "No value recorded yet."})
                continue
            spec["queries"][metric] = f"""SELECT progress * 100 AS series_percent, value, scope
                FROM progression WHERE character = '{name}' AND metric = '{metric}'
                AND kind IN ('level','stat') AND value IS NOT NULL AND progress <= {row["progress"]}
                ORDER BY progress"""
            last = points[-1]
            subtitle = (f"Book {last['book']}, Chapter {last['chapter']} · "
                        + (f"Recorded value: {last['value']}" if last["value"] is not None
                           else "Later change has no recorded total."))
            chart = {"title": title, "subtitle": subtitle, "type": "line", "query": metric,
                     "x": "series_percent", "x_label": "Series read (%)", "y": "value",
                     "height": 240, "layers": [{"type": "scatter", "y": "value"}]}
            if metric != "Level":
                chart["color"] = "scope"
                chart["layers"][0]["color"] = "scope"
            spec["charts"][metric] = chart
            spec["rows"].append(metric)
        board = Path(scratch) / f'{row["event_id"]}.yml'
        board.write_text(json.dumps(spec))
        boards[row["event_id"]] = str(board)
    subprocess.run(["dct", "render", *boards.values(), "--no-cache", "--project-dir", str(ROOT),
                    "--format", "svg", "--output", str(out / "{stem}.svg")], check=True)
