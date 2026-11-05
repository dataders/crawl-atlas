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
    boards = []
    for row in rows:
        if row["kind"] not in ("level", "stat") or row["value"] is None:
            continue
        metric = row["metric"]
        name = row["character"].replace("'", "''")
        query = f"""SELECT ROUND(progress * 100, 4) AS series_percent, value, scope
            FROM progression WHERE character = '{name}' AND metric = '{metric}'
            AND kind = '{row["kind"]}' AND value IS NOT NULL AND progress <= {row["progress"]}
            ORDER BY progress"""
        board = Path(scratch) / f'{row["event_id"]}-{metric}.yml'
        board.write_text(json.dumps({
            "extends": "neon", "source": "crawl_atlas",
            "queries": {"observations": query},
            "charts": {"history": {"type": "scatter", "query": "observations",
                "x": "series_percent", "x_label": "Series read (%)",
                "y": "value", "y_label": metric, "color": "scope"}},
            "rows": ["history"],
        }))
        boards.append(str(board))
    subprocess.run(["dct", "render", *boards, "--no-cache", "--project-dir", str(ROOT),
                    "--format", "svg", "--output", str(out / "{stem}.svg")], check=True)
