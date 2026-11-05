"""Render reusable native dbt table rows for the two locally filtered reader sections."""
import json
import subprocess
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "site/dist"
SVG = "{http://www.w3.org/2000/svg}"
ET.register_namespace("", SVG[1:-1])
records = json.loads(subprocess.check_output(["node", "scripts/detail_rows.cjs"], cwd=ROOT))
result = {}
with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
    for name, rows in records.items():
        board = Path(tmp) / f"{name}.yml"
        spec = {"extends": "neon", "width": 740 if name == "inventory" else 480, "rows": [name],
                "queries": {"records": {"type": "values", "rows": rows}},
                "charts": {name: {"type": "table", "query": "records",
                                   "style": {"pagination": {"enabled": False}}}}}
        board.write_text(json.dumps(spec))
        out = board.with_suffix(".svg")
        subprocess.run(["dct", "render", str(board), "--format", "svg", "--no-cache", "--output", str(out)], check=True, cwd=ROOT)
        group = ET.parse(out).find(f'.//*[@data-chart-id="{name}"]')
        body = group.find(f'{SVG}g')
        rendered = body.findall(f'{SVG}g[@class="dbt-table-row"]')
        if len(rows) != len(rendered):
            raise ValueError(f"{name}: expected {len(rows)} rows, got {len(rendered)}")
        library = {}
        for row, node in zip(rows, rendered):
            body.remove(node)
            baseline = float(node.find(f'{SVG}text').get("y"))
            key = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            library[key] = [baseline, ET.tostring(node, encoding="unicode")]
        result[name] = {"header": ET.tostring(body, encoding="unicode"), "rows": library,
                        "width": float(group.get("data-chart-width"))}
(DIST / "data/detail-tables.json").write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
