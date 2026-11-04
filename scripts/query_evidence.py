"""Query the private evidence database: uv run --with duckdb python scripts/query_evidence.py 'SELECT ...'."""
import argparse
from pathlib import Path
import duckdb

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('sql', help='SQL query against sentences, observations, character_evidence, or imani_mentions')
args = parser.parse_args()
path = Path(__file__).resolve().parents[1] / 'data/private/evidence/crawl-atlas.duckdb'
if not path.exists():
    parser.error('Run scripts/build_evidence_database.py first.')
with duckdb.connect(str(path), read_only=True) as db:
    db.sql(args.sql).show(max_rows=100)
