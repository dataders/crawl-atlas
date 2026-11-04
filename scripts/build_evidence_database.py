"""Private, reproducible sentence evidence and Parquet exports. Never deploy these files.

Run: uv run --with duckdb python scripts/build_evidence_database.py
Sentence boundaries are heuristic; original paragraph text and character offsets
remain authoritative. Paragraph-level links are not claimed as sentence attribution.
"""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPLITTER_VERSION = "punctuation-v1"


def sentence_spans(text):
    start = 0
    for match in re.finditer(r'[.!?]+[\u201d\u2019\"\')\]]*(?:\s+|$)', text):
        end = match.end()
        piece = text[start:end].rstrip()
        # Preserve initials and common titles, including the character name Imani C.
        if re.search(r'\b(?:Mr|Mrs|Ms|Dr|St|[A-Z])\.[\u201d\u2019\"\')\]]*$', piece):
            continue
        if piece.strip():
            left = start + len(text[start:end]) - len(text[start:end].lstrip())
            yield left, start + len(text[start:end].rstrip())
        start = end
    if text[start:].strip():
        left = start + len(text[start:]) - len(text[start:].lstrip())
        yield left, len(text.rstrip())


def corpus_sentences(corpus):
    rows = []
    for book in corpus['books']:
        for chapter in book['chapters']:
            ordinal = 0
            for paragraph in chapter['paragraphs']:
                for number, (start, end) in enumerate(sentence_spans(paragraph['text']), 1):
                    ordinal += 1
                    rows.append(dict(sentence_id=f"{paragraph['anchor']}-s{number}",
                        book=book['number'], chapter=chapter['number'],
                        paragraph=int(paragraph['anchor'].split('-p')[-1]),
                        sentence=ordinal, sentence_in_paragraph=number,
                        source=paragraph['anchor'], position=paragraph['position'],
                        char_start=start, char_end=end, source_sentence=paragraph['text'][start:end],
                        paragraph_text=paragraph['text'], splitter_version=SPLITTER_VERSION))
    return rows


def evidence_links(events, sentences):
    by_source = {}
    for row in sentences:
        by_source.setdefault(row['source'], []).append(row)
    links = []
    for event in events:
        anchors = list(dict.fromkeys([event['source'], *event.get('evidence', [])]))
        selected = event.get('evidenceSentences', {})
        for anchor in anchors:
            if anchor not in by_source:
                raise ValueError(f"Unknown evidence anchor: {anchor}")
            for row in by_source[anchor]:
                if anchor in selected and row['sentence_in_paragraph'] not in selected[anchor]:
                    continue
                links.append(dict(event_id=event['id'], sentence_id=row['sentence_id'],
                    evidence_role='primary' if anchor == event['source'] else 'context',
                    evidence_precision='sentence' if anchor in selected else 'paragraph'))
    return links


def observation_rows(events):
    try:
        from .build_database import progression_rows
    except ImportError:
        from build_database import progression_rows
    progression = {}
    for row in progression_rows(events):
        progression.setdefault(row['event_id'], []).append(row)
    rows = []
    for event in events:
        metrics = progression.get(event['id'], [dict(metric=event['name'], value=None,
                    delta=None, scope='reported')])
        for metric in metrics:
            rows.append(dict(observation_id=f"{event['id']}:{metric['metric']}",
                event_id=event['id'], character=event['subject'], attribute=event['type'],
                attribute_name=metric['metric'], value=metric['value'], delta=metric['delta'],
                scope=metric['scope'], action=event.get('action', 'note'),
                confidence=event['confidence'], summary=event.get('summary', ''),
                reveal_progress=event['progress'], reveal_book=event['book'],
                reveal_chapter=event['chapter'], source=event['source']))
    return rows


def build():
    import duckdb
    from reward_provenance import acquisition_rows
    private = ROOT / 'data/private'
    corpus_path = private / 'series-corpus.json'
    timeline_path = ROOT / 'site/dist/data/series.json'
    corpus = json.loads(corpus_path.read_text())
    timeline = json.loads(timeline_path.read_text())
    sentences = corpus_sentences(corpus)
    tables = dict(sentences=sentences, observations=observation_rows(timeline['events']),
                  observation_evidence=evidence_links(timeline['events'], sentences))
    acquisitions, links = acquisition_rows(timeline['events'])
    tables.update(acquisitions=acquisitions, acquisition_links=links)
    output = private / 'evidence'
    output.mkdir(exist_ok=True)
    db = duckdb.connect(str(output / 'crawl-atlas.duckdb'))
    try:
        for name, rows in tables.items():
            source = output / f'{name}.jsonl'
            source.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))
            db.execute(f'CREATE OR REPLACE TABLE {name} AS SELECT * FROM read_json_auto(?, maximum_object_size=16777216)', [str(source)])
            db.execute(f'COPY {name} TO ? (FORMAT PARQUET, COMPRESSION ZSTD)', [str(output / f'{name}.parquet')])
            source.unlink()
        db.execute('''CREATE OR REPLACE VIEW character_evidence AS
            SELECT o.*, s.book, s.chapter, s.paragraph, s.sentence,
                s.sentence_in_paragraph, s.sentence_id, s.source_sentence,
                s.char_start, s.char_end, e.evidence_role, e.evidence_precision,
                a.stage AS acquisition_stage, a.source_type, a.box_id, a.box_tier,
                a.box_kind, a.outcome_type, a.reason_type, a.reason_detail,
                a.occurrence_detail, a.attribution AS acquisition_attribution
            FROM observations o JOIN observation_evidence e USING (event_id)
            JOIN sentences s USING (sentence_id)
            LEFT JOIN acquisitions a ON a.event_id = o.event_id''')
        db.execute('COPY character_evidence TO ? (FORMAT PARQUET, COMPRESSION ZSTD)',
                   [str(output / 'character-evidence.parquet')])
        db.execute('''CREATE OR REPLACE VIEW acquisition_evidence AS
            SELECT a.*, s.sentence_id, s.sentence, s.source_sentence, e.evidence_precision
            FROM acquisitions a JOIN observation_evidence e USING(event_id)
            JOIN sentences s USING(sentence_id)''')
        db.execute('COPY acquisition_evidence TO ? (FORMAT PARQUET, COMPRESSION ZSTD)',
                   [str(output / 'acquisition-evidence.parquet')])
        # Raw mention search is deliberately distinct from attributed observations.
        db.execute("CREATE OR REPLACE VIEW imani_mentions AS SELECT * FROM sentences WHERE regexp_matches(source_sentence, '(?i)\\bImani\\b|Obsidian Butterfly|Fire Spiritualist')")
        counts = {name: db.execute(f'SELECT count(*) FROM {name}').fetchone()[0]
                  for name in [*tables, 'character_evidence', 'imani_mentions']}
    finally:
        db.close()
    manifest = dict(counts=counts, splitter_version=SPLITTER_VERSION,
        corpus_sha256=hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
        timeline_sha256=hashlib.sha256(timeline_path.read_bytes()).hexdigest(),
        privacy='Local private EPUB text. Excluded from Git and site deployment.',
        evidence='Sentence links are explicit where curated; legacy links include all sentences of the cited paragraph and are labeled paragraph precision.')
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(counts))


if __name__ == '__main__':
    build()
