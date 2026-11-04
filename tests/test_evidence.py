import unittest
from scripts.build_evidence_database import corpus_sentences, evidence_links, sentence_spans


class EvidenceTests(unittest.TestCase):
    def test_sentences_preserve_exact_text_offsets_and_initials(self):
        text = '  Dr. Bones met Imani C. in town. “Level 24.” Next one!  '
        spans = list(sentence_spans(text))
        self.assertEqual([text[a:b] for a, b in spans],
                         ['Dr. Bones met Imani C. in town.', '“Level 24.”', 'Next one!'])

    def test_chapter_sentence_numbers_and_paragraph_context(self):
        corpus = {'books': [{'number': 1, 'chapters': [{'number': 1, 'paragraphs': [
            {'anchor': 'b1-c1-p1', 'position': .1, 'text': 'She arrived. She gained a level.'},
            {'anchor': 'b1-c1-p2', 'position': .2, 'text': 'Her total is unknown.'}]}]}]}
        rows = corpus_sentences(corpus)
        self.assertEqual([r['sentence'] for r in rows], [1, 2, 3])
        events = [{'id': 'a', 'source': 'b1-c1-p1'},
                  {'id': 'b', 'source': 'b1-c1-p2', 'evidence': ['b1-c1-p1'],
                   'evidenceSentences': {'b1-c1-p1': [2], 'b1-c1-p2': [1]}}]
        links = evidence_links(events, rows)
        self.assertEqual(len(links), 4)
        self.assertEqual([r['evidence_precision'] for r in links],
                         ['paragraph', 'paragraph', 'sentence', 'sentence'])
        self.assertEqual(links[-1]['sentence_id'], 'b1-c1-p1-s2')

    def test_missing_source_fails_instead_of_silently_dropping_evidence(self):
        with self.assertRaises(ValueError):
            evidence_links([{'id': 'missing', 'source': 'b1-c1-p1'}], [])
