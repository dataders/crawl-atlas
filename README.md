# Dungeon Crawler’s Lookbook

Track the characters in Matt Dinniman’s *Dungeon Crawler Carl* up to the chapter you’ve read. Pick your place across eight books to see who has leveled up, which spells they know, and what they’ve picked up along the way.

**[Open the Lookbook](https://crawl-atlas.anders.omg.lol/)** · [Report a bug, suggest a feature, or correct an entry](https://github.com/dataders/crawl-atlas/issues/new?template=reader-feedback.yml)

The level chart follows the cast. Choose a character to explore their stats, skills, equipped gear, inventory, rewards, and history. Moving the slider back hides later discoveries. A shared reader link remembers your position and selected dossier.

## Where the numbers come from

Each observation points to the place in the books where a reader can learn it. Coverage is selective. A gap between two levels means we have two readings and may be missing the steps between them. An item can grant a known bonus even when the character’s total is unknown.

The public repository contains observations and short summaries. The EPUBs and extracted prose stay on the contributor’s machine. The [data model](docs/dashboard-data-model.md) describes the records and their relationships.

## Run the reader locally

From the repository root, serve the included site and open [localhost:4173](http://localhost:4173/). The preview works with the checked-in board exports.

```sh
uv run python -m http.server 4173 --bind 127.0.0.1 --directory site/dist
```

## How the site works

The dashboard is made with [dbt Charts](https://dbtcharts.com/). Its production layout lives in [charts/reader.yml](charts/reader.yml). The [board builder](scripts/build_single_board.py) limits observations to the selected reading position. The [exporter](scripts/export_single_board.py) renders the boards ahead of time. On GitHub Pages, the [reader](site/dist/static-reader.js) loads the matching export when you move the slider or switch characters or tabs.

To validate the checked-in exports:

```sh
uv run python scripts/check_single_board.py
```

For a new observation, start with the [contribution guide](CONTRIBUTING.md). Include the book and chapter where the detail first becomes known. The [wiki corroboration notes](docs/wiki-corroboration.md) explain how community references inform the audit.

## Credits

[Quartermaester’s interactive Game of Thrones map](https://quartermaester.info/) inspired the chapter slider. Thanks to the editors of the [Dungeon Crawler Carl Wiki](https://dungeon-crawler-carl.fandom.com/wiki/Dungeon_Crawler_Carl_Wiki) for the reference work behind so many cross-checks.

An unofficial fan project celebrating Matt Dinniman’s books. Project code is [MIT licensed](LICENSE).
