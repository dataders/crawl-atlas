# Crawl Atlas

For board work, follow `.agents/skills/dct/SKILL.md` and run `dct skills chart`.
For layout, typography, axes, or table styling, also run `dct skills styling`.
Use the installed CLI's grammar and diagnostics.

- **Production reader:** `scripts/render_reader_charts.py` builds the desktop and
  compact static HTML boards published under `site/dist/charts/`. Change the
  generator and regenerate with `uv run python scripts/render_reader_charts.py`.
- **Interactive local board:** `charts/crawl-atlas.yml` uses the public SQLite
  source declared in `dbt_charts.yml`. Validate this board with
  `dct validate charts/crawl-atlas.yml --strict` and render a populated checkpoint.
- **Spoiler boundary:** the shared reading slider starts at zero. Apply the exact
  reveal position before deriving plots, table rows, options, or exports. Check
  both advancing and rewinding. A missing measurement stays unknown.
- **Public data:** publish curated observations only. EPUBs and private sentence
  evidence stay outside `site/dist/`. See `docs/dashboard-data-model.md` for
  the relation contracts.
