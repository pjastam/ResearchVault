"""
test_feedreader_labels.py — Tests voor de labellogica van de leerloop
======================================================================
Pure functies over logregels; geen netwerk, geen bestanden, kale stdlib.

Aanleiding: 1.816 van de 1.923 positieven in score_log.jsonl kwamen uit de ster,
en 1.815 daarvan lag op of boven THRESHOLD_STAR — de drempel waarop de pijplijn
zélf sterrt. Het drempeladvies bevestigde daarmee grotendeels zijn eigen oordeel.
"""

import unittest

from feedreader_labels import mark_auto_starred, split_positives


def regel(**kw):
    """Een logregel met bruikbare standaardwaarden; overschrijf wat de test nodig heeft."""
    basis = {
        "url": "https://a.test/1",
        "score": 50,
        "timestamp": "2026-08-01T00:00:00+00:00",
    }
    basis.update(kw)
    return basis


class AutoStarTest(unittest.TestCase):
    def test_markeert_wat_in_de_star_queue_van_deze_run_stond(self):
        entries = [
            regel(url="https://a.test/hoog", score=75),
            regel(url="https://a.test/laag", score=42),
        ]
        n = mark_auto_starred(entries, {"https://a.test/hoog"}, threshold=70)
        self.assertEqual(n, 1)
        self.assertTrue(entries[0]["auto_starred"])
        self.assertNotIn("auto_starred", entries[1])

    def test_markeert_historische_sterren_op_of_boven_de_drempel(self):
        """De star-queue van toen bestaat niet meer; score + ster is het bewijs."""
        entries = [regel(url="https://a.test/oud", score=74, starred_in_freshrss=True)]
        n = mark_auto_starred(entries, set(), threshold=70)
        self.assertEqual(n, 1)
        self.assertTrue(entries[0]["auto_starred"])

    def test_handmatige_ster_onder_de_drempel_blijft_ongemarkeerd(self):
        entries = [regel(url="https://a.test/handmatig", score=55,
                         starred_in_freshrss=True)]
        n = mark_auto_starred(entries, set(), threshold=70)
        self.assertEqual(n, 0)
        self.assertNotIn("auto_starred", entries[0])

    def test_ongesterde_regel_op_de_drempel_blijft_ongemarkeerd(self):
        """Score alleen is niet genoeg — er moet ook echt een ster staan."""
        entries = [regel(url="https://a.test/x", score=80)]
        n = mark_auto_starred(entries, set(), threshold=70)
        self.assertEqual(n, 0)

    def test_canonicaliseert_de_queue_urls(self):
        entries = [regel(url="https://a.test/hoog?utm_source=nnw", score=75)]
        n = mark_auto_starred(entries, {"https://a.test/hoog"}, threshold=70)
        self.assertEqual(n, 1)

    def test_is_idempotent(self):
        entries = [regel(url="https://a.test/hoog", score=75)]
        mark_auto_starred(entries, {"https://a.test/hoog"}, threshold=70)
        n = mark_auto_starred(entries, {"https://a.test/hoog"}, threshold=70)
        self.assertEqual(n, 0)


class SplitPositivesTest(unittest.TestCase):
    def test_scheidt_echte_van_auto_positieven(self):
        entries = [
            regel(url="https://a.test/1", added_to_zotero=True, auto_starred=True),
            regel(url="https://a.test/2", added_to_zotero=True),
            regel(url="https://a.test/3", added_to_zotero=False),
        ]
        echt, auto = split_positives(entries)
        self.assertEqual([e["url"] for e in echt], ["https://a.test/2"])
        self.assertEqual([e["url"] for e in auto], ["https://a.test/1"])

    def test_ongelabelde_regels_tellen_nergens_mee(self):
        entries = [regel(url="https://a.test/1")]
        echt, auto = split_positives(entries)
        self.assertEqual(echt, [])
        self.assertEqual(auto, [])


if __name__ == "__main__":
    unittest.main()
