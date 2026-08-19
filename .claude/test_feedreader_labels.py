"""
test_feedreader_labels.py — Tests voor de labellogica van de leerloop
======================================================================
Pure functies over logregels; geen netwerk, geen bestanden, kale stdlib.

Aanleiding: 1.816 van de 1.923 positieven in score_log.jsonl kwamen uit de ster,
en 1.815 daarvan lag op of boven THRESHOLD_STAR — de drempel waarop de pijplijn
zélf sterrt. Het drempeladvies bevestigde daarmee grotendeels zijn eigen oordeel.
"""

import unittest

from feedreader_labels import apply_skips, mark_auto_starred, split_positives


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


class SkipTest(unittest.TestCase):
    def test_matcht_op_identity_niet_op_url(self):
        """Podcasts delen de showpagina als link; alleen de guid onderscheidt afleveringen.

        Captivate en RedCircle geven bij élke aflevering dezelfde showpagina als
        link. Op URL matchen zou één 👎 de hele show laten raken — precies het
        defect waarvoor feedreader_identity.py is gebouwd.
        """
        entries = [
            regel(url="https://pod.test/show/", identity="uuid-afl-1"),
            regel(url="https://pod.test/show/", identity="uuid-afl-2"),
        ]
        n, ongematcht = apply_skips(entries, [{"identity": "uuid-afl-2"}])
        self.assertEqual(n, 1)
        self.assertEqual(ongematcht, [])
        self.assertNotIn("skipped", entries[0])
        self.assertTrue(entries[1]["skipped"])

    def test_valt_terug_op_url_voor_regels_zonder_identity(self):
        """Regels van vóór 16 aug 2026 dragen geen identity-veld."""
        entries = [regel(url="https://a.test/oud?utm_source=x")]
        n, ongematcht = apply_skips(entries, [{"url": "https://a.test/oud"}])
        self.assertEqual(n, 1)
        self.assertTrue(entries[0]["skipped"])

    def test_meldt_wat_niet_matchte_in_plaats_van_het_weg_te_gooien(self):
        entries = [regel(url="https://a.test/1")]
        n, ongematcht = apply_skips(entries, [{"url": "https://onbekend.test/x"}])
        self.assertEqual(n, 0)
        self.assertEqual(len(ongematcht), 1)
        self.assertEqual(ongematcht[0]["url"], "https://onbekend.test/x")

    def test_al_gemarkeerde_regel_telt_niet_dubbel(self):
        entries = [regel(url="https://a.test/1", skipped=True)]
        n, ongematcht = apply_skips(entries, [{"url": "https://a.test/1"}])
        self.assertEqual(n, 0)
        self.assertEqual(ongematcht, [], "hij matchte wél, dus hij is niet verloren")

    def test_skip_zonder_bruikbare_sleutel_wordt_genegeerd(self):
        entries = [regel(url="https://a.test/1")]
        n, ongematcht = apply_skips(entries, [{"url": "", "identity": ""}])
        self.assertEqual(n, 0)
        self.assertEqual(ongematcht, [])

    def test_een_skip_kan_meerdere_logregels_van_hetzelfde_artikel_raken(self):
        """Link-churn heeft hetzelfde artikel vaak meermaals gelogd."""
        entries = [
            regel(url="https://a.test/x?ff=111"),
            regel(url="https://a.test/x?ff=222"),
        ]
        n, ongematcht = apply_skips(entries, [{"url": "https://a.test/x"}])
        self.assertEqual(n, 2)
        self.assertEqual(ongematcht, [])


class HardeStopTest(unittest.TestCase):
    """ADR-0005: een 👎 blokkeert alle latere signalen, ook een handmatige ster."""

    def test_skipped_wint_van_een_handmatige_ster(self):
        entries = [regel(url="https://a.test/1", score=55,
                         starred_in_freshrss=True, added_to_zotero=True)]
        echt_voor, _ = split_positives(entries)
        self.assertEqual(len(echt_voor), 1, "voorwaarde: telt eerst wél als positief")

        n, ongematcht = apply_skips(entries, [{"url": "https://a.test/1"}])
        self.assertEqual(n, 1)
        self.assertEqual(ongematcht, [])

        echt_na, auto_na = split_positives(entries)
        self.assertEqual(echt_na, [], "na het 👎 telt het niet meer als positief")
        self.assertEqual(auto_na, [])

    def test_skipped_blokkeert_ook_de_auto_stermarkering(self):
        entries = [regel(url="https://a.test/1", score=75, skipped=True)]
        self.assertEqual(mark_auto_starred(entries, {"https://a.test/1"}, threshold=70), 0)
        self.assertNotIn("auto_starred", entries[0])


if __name__ == "__main__":
    unittest.main()
