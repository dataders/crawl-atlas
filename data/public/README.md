This directory contains **source data for the build**. The website does not fetch these files; GitHub Pages serves the exported reader from `site/dist/`.

- **Timeline inputs:** The audit and sweep batches listed in `scripts/build_public_timeline.py` contribute events, corrections, and character records. Dated filenames describe when someone reviewed the books. The build still uses their contents.
- **Rewards:** `reward-provenance.json` reconciles rewards and their sources in `scripts/reward_provenance.py`.
- **Character stats:** `stat-breakdown-audit.json` supplies additional readings to the dossier charts.

When reorganizing the timeline inputs, preserve each event ID: the builder uses the batch prefix to generate IDs, and corrections refer to those IDs. Compare the resulting events, corrections, and reading positions before regenerating the site. Draft leads and book text belong in the private data directory.
