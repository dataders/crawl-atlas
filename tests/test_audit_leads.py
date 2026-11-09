import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from extract_leaderboard_readings import reading, reconcile
from find_audit_leads import candidates, index_events, names_pattern, select


class LeaderboardTests(unittest.TestCase):
    def test_rank_prize_and_level_remain_distinct(self):
        row = reading("3. Donut – Cat – Reader – Level 18 – 400,000 (x2)")
        self.assertEqual(
            (row["board_rank"], row["subject"], row["level"]), (3, "Princess Donut", 18)
        )
        self.assertEqual(
            reading("9. Tester – Human – Level 40 – Artist – 100,000")["level"], 40
        )
        self.assertIsNone(reading("1. Carl said the monster was level 25."))

    def test_stale_printed_level_is_flagged_for_review(self):
        events = [
            dict(
                type="level",
                subject="Princess Donut",
                level=12,
                book=3,
                chapter=1,
                position=0.1,
                source="b3-c1-p1",
            )
        ]
        corpus = {
            "books": [
                dict(
                    number=3,
                    chapters=[
                        dict(
                            number=1,
                            paragraphs=[
                                dict(
                                    position=0.2,
                                    anchor="b3-c1-p2",
                                    text="7. Donut – Cat – Reader – Level 11 – 100",
                                )
                            ],
                        )
                    ],
                )
            ]
        }
        rows = list(
            reconcile(
                corpus, dict(events=events, characters=[{"name": "Princess Donut"}])
            )
        )
        self.assertEqual(rows[0]["status"], "below earlier reading")


class LeadTests(unittest.TestCase):
    def test_a_recorded_level_can_share_a_passage_with_an_unrecorded_transfer(self):
        p = dict(
            text="Carl reached level 8 and handed the ring to Donut.",
            anchor="b1-c2-p1",
            bold=False,
        )
        event = dict(
            id="level-known",
            source=p["anchor"],
            type="level",
            subject="Carl",
            name="Character level",
        )
        series = dict(events=[event], characters=[{"name": "Carl"}])
        book = dict(number=1, chapters=[dict(number=2, paragraphs=[p])])
        rows = list(candidates(book, index_events(series), names_pattern(series)))
        picked = select(rows, 12)
        self.assertEqual(len(picked), 1)
        self.assertIn("transfer or consumption", picked[0]["cues"])
        self.assertEqual(picked[0]["existing"][0]["id"], "level-known")
