"""
test_feedreader_labels.py — Tests voor de labellogica van de leerloop
======================================================================
Pure functies over logregels; geen netwerk, geen bestanden, kale stdlib.

Aanleiding: 1.816 van de 1.923 positieven in score_log.jsonl kwamen uit de ster,
en 1.815 daarvan lag op of boven THRESHOLD_STAR — de drempel waarop de pijplijn
zélf sterrt. Het drempeladvies bevestigde daarmee grotendeels zijn eigen oordeel.
"""

import unittest

from feedreader_labels import (
    apply_skips,
    mark_auto_starred,
    split_positives,
    star_threshold_report,
)


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
        n = mark_auto_starred(entries, {"https://a.test/hoog"}, fallback_threshold=70)
        self.assertEqual(n, 1)
        self.assertTrue(entries[0]["auto_starred"])
        self.assertNotIn("auto_starred", entries[1])

    def test_markeert_historische_sterren_op_of_boven_de_drempel(self):
        """De star-queue van toen bestaat niet meer; score + ster is het bewijs."""
        entries = [regel(url="https://a.test/oud", score=74, starred_in_freshrss=True)]
        n = mark_auto_starred(entries, set(), fallback_threshold=70)
        self.assertEqual(n, 1)
        self.assertTrue(entries[0]["auto_starred"])

    def test_handmatige_ster_onder_de_drempel_blijft_ongemarkeerd(self):
        entries = [regel(url="https://a.test/handmatig", score=55,
                         starred_in_freshrss=True)]
        n = mark_auto_starred(entries, set(), fallback_threshold=70)
        self.assertEqual(n, 0)
        self.assertNotIn("auto_starred", entries[0])

    def test_ongesterde_regel_op_de_drempel_blijft_ongemarkeerd(self):
        """Score alleen is niet genoeg — er moet ook echt een ster staan."""
        entries = [regel(url="https://a.test/x", score=80)]
        n = mark_auto_starred(entries, set(), fallback_threshold=70)
        self.assertEqual(n, 0)

    def test_canonicaliseert_de_queue_urls(self):
        entries = [regel(url="https://a.test/hoog?utm_source=nnw", score=75)]
        n = mark_auto_starred(entries, {"https://a.test/hoog"}, fallback_threshold=70)
        self.assertEqual(n, 1)

    def test_is_idempotent(self):
        entries = [regel(url="https://a.test/hoog", score=75)]
        mark_auto_starred(entries, {"https://a.test/hoog"}, fallback_threshold=70)
        n = mark_auto_starred(entries, {"https://a.test/hoog"}, fallback_threshold=70)
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
        self.assertEqual(mark_auto_starred(entries, {"https://a.test/1"}, fallback_threshold=70), 0)
        self.assertNotIn("auto_starred", entries[0])


class DocContractTest(unittest.TestCase):
    """De signaaltabel uit docs/src/usage/phase1-sources.md, als uitvoerbare afspraak.

    Die tabel is het contract van de leerloop. Rij 5 stond er sinds jaar en dag in
    en was nooit geïmplementeerd: `process_skip_queue` zette alleen `skipped`, en
    de labellus las dat veld nergens. Dat de uitkomst tóch klopte kwam door de
    timeout na 3 dagen — toeval, geen ontwerp. Deze klasse zorgt dat de volgende
    afwijking rood wordt in plaats van onzichtbaar.
    """

    def test_rij1_geklikt_en_in_zotero_is_sterk_positief(self):
        entries = [regel(url="https://a.test/1", added_to_zotero=True)]
        echt, _ = split_positives(entries)
        self.assertEqual(len(echt), 1)

    def test_rij4_duim_omlaag_zonder_klik_markeert_direct(self):
        """"skipped: true immediately" — niet pas na de timeout van 3 dagen."""
        entries = [regel(url="https://a.test/1")]
        n, _ = apply_skips(entries, [{"url": "https://a.test/1"}])
        self.assertEqual(n, 1)
        self.assertTrue(entries[0]["skipped"])

    def test_rij5_geklikt_dan_duim_omlaag_is_het_sterkste_negatief(self):
        """De rij die vier maanden niet klopte.

        `skipped: true` + `added_to_zotero: false`, en het 👎 wint van de ster —
        ook van een ster die de pijplijn zelf zette.
        """
        entries = [regel(url="https://a.test/1", starred_in_freshrss=True, score=75)]
        apply_skips(entries, [{"url": "https://a.test/1"}])
        self.assertTrue(entries[0]["skipped"])

        mark_auto_starred(entries, {"https://a.test/1"}, fallback_threshold=70)
        echt, auto = split_positives(entries)
        self.assertEqual(echt, [], "een afgewezen item is geen menselijk positief")
        self.assertEqual(auto, [], "en ook geen auto-positief")

    def test_auto_ster_is_geen_menselijk_positief(self):
        """Niet uit de doc-tabel, maar het gevolg van ADR-0005 en taak 3."""
        entries = [
            regel(url="https://a.test/auto", score=80,
                  starred_in_freshrss=True, added_to_zotero=True),
            regel(url="https://a.test/mens", score=45, added_to_zotero=True),
        ]
        mark_auto_starred(entries, set(), fallback_threshold=70)
        echt, auto = split_positives(entries)
        self.assertEqual([e["url"] for e in echt], ["https://a.test/mens"])
        self.assertEqual([e["url"] for e in auto], ["https://a.test/auto"])


class TijdperkTest(unittest.TestCase):
    """Een logregel wordt beoordeeld met de drempel die tóén gold, niet die van nu.

    De vuistregel "gesterd én score ≥ drempel" leest sinds 19 aug 2026 het veld
    `star_threshold` van de regel zelf. Zonder dat veld zou elke verhoging van
    THRESHOLD_STAR de betekenis van bestaande regels veranderen: handmatige
    sterren in de band [oude drempel, nieuwe drempel) zouden ten onrechte als
    zelfbevestiging gelden, en dat verlies groeit met elke volgende verhoging.
    """

    def test_regel_uit_het_70_tijdperk_telt_als_auto(self):
        entries = [regel(score=72, starred_in_freshrss=True, star_threshold=70)]
        self.assertEqual(mark_auto_starred(entries, set(), fallback_threshold=70), 1)
        self.assertTrue(entries[0]["auto_starred"])

    def test_dezelfde_score_uit_het_75_tijdperk_is_handmatig(self):
        """72 lag onder de drempel van 75, dus de pijplijn kan hem niet gezet hebben."""
        entries = [regel(score=72, starred_in_freshrss=True, star_threshold=75)]
        self.assertEqual(mark_auto_starred(entries, set(), fallback_threshold=70), 0)
        self.assertNotIn("auto_starred", entries[0])

    def test_regel_zonder_veld_valt_terug_op_de_historische_drempel(self):
        """Regels zonder star_threshold dateren van vóór 19 aug 2026 — toen gold 70."""
        entries = [regel(score=72, starred_in_freshrss=True)]
        self.assertEqual(mark_auto_starred(entries, set(), fallback_threshold=70), 1)

    def test_twee_tijdperken_in_een_dataset_worden_apart_beoordeeld(self):
        entries = [
            regel(url="https://a.test/oud",    score=72, starred_in_freshrss=True, star_threshold=70),
            regel(url="https://a.test/nieuw",  score=72, starred_in_freshrss=True, star_threshold=75),
            regel(url="https://a.test/hoog",   score=78, starred_in_freshrss=True, star_threshold=75),
        ]
        self.assertEqual(mark_auto_starred(entries, set(), fallback_threshold=70), 2)
        self.assertTrue(entries[0].get("auto_starred"))
        self.assertNotIn("auto_starred", entries[1])
        self.assertTrue(entries[2].get("auto_starred"))

    def test_een_volgende_verhoging_verandert_de_historie_niet(self):
        """De vraag die dit alles uitlokte: overleeft dit een tweede verhoging?"""
        maak = lambda: [
            regel(url="https://a.test/a", score=72, starred_in_freshrss=True, star_threshold=70),
            regel(url="https://a.test/b", score=78, starred_in_freshrss=True, star_threshold=75),
            regel(url="https://a.test/c", score=82, starred_in_freshrss=True, star_threshold=80),
        ]
        # De fallback is de enige knop die met de tijd zou kunnen meebewegen; hij
        # mag de uitkomst voor regels mét een eigen veld niet raken.
        for fallback in (70, 75, 80, 85):
            entries = maak()
            self.assertEqual(mark_auto_starred(entries, set(), fallback_threshold=fallback), 3,
                             f"fallback {fallback} veranderde de historie")

    def test_star_queue_wint_altijd_van_de_vuistregel(self):
        """Hard bewijs gaat voor: de queue zegt dat wíj hem gesterd hebben."""
        entries = [regel(url="https://a.test/x", score=10, star_threshold=75)]
        self.assertEqual(
            mark_auto_starred(entries, {"https://a.test/x"}, fallback_threshold=70), 1)


def ster_rij(score, zotero_hit=False, skipped=False):
    """Eén artikel voor het drempelrapport."""
    r = {"url": f"https://a.test/{score}-{zotero_hit}-{skipped}",
         "score": score, "zotero_hit": zotero_hit}
    if skipped:
        r["skipped"] = True
    return r


class StarThresholdReportTest(unittest.TestCase):
    """Het advies voor THRESHOLD_STAR rust op de Zotero-match, niet op de ster.

    De ster mag zichzelf niet beoordelen — dat is precies de circulariteit die op
    19 aug 2026 uit de leerloop is gehaald (ADR-0005).
    """

    def test_precisie_en_dekking_per_drempel(self):
        rijen = (
            [ster_rij(80, zotero_hit=True)] * 2
            + [ster_rij(80)] * 8       # 10 items ≥80, 2 treffers → precisie 20%
            + [ster_rij(50, zotero_hit=True)] * 2
            + [ster_rij(50)] * 88      # 100 items ≥50, 4 treffers → precisie 4%
        )
        rap = star_threshold_report(rijen, candidates=[50, 80])
        per = {r["drempel"]: r for r in rap["rijen"]}
        self.assertEqual(per[80]["gesterd"], 10)
        self.assertAlmostEqual(per[80]["precisie"], 0.20)
        self.assertAlmostEqual(per[80]["dekking"], 0.50)   # 2 van de 4 treffers
        self.assertEqual(per[50]["gesterd"], 100)
        self.assertAlmostEqual(per[50]["precisie"], 0.04)
        self.assertAlmostEqual(per[50]["dekking"], 1.0)

    def test_lift_is_precisie_gedeeld_door_het_basispercentage(self):
        rijen = [ster_rij(80, zotero_hit=True)] + [ster_rij(80)] * 9 + [ster_rij(10)] * 90
        rap = star_threshold_report(rijen, candidates=[80])
        # basis: 1 van de 100 = 1%; precisie bij 80: 1 van de 10 = 10% → lift 10×
        self.assertAlmostEqual(rap["basisrate"], 0.01)
        self.assertAlmostEqual(rap["rijen"][0]["lift"], 10.0)

    def test_duim_omlaag_legt_een_harde_vloer(self):
        """Nooit een drempel adviseren die een expliciet afgewezen item zou sterren."""
        rijen = (
            [ster_rij(55, skipped=True)]
            + [ster_rij(60, zotero_hit=True)] * 40
            + [ster_rij(60)] * 40
            + [ster_rij(10)] * 400
        )
        rap = star_threshold_report(rijen, candidates=[50, 60])
        self.assertEqual(rap["vloer"], 56)
        self.assertGreaterEqual(rap["advies"], 56)
        self.assertEqual(rap["advies"], 60)

    def test_zonder_afwijzingen_is_er_geen_vloer(self):
        rijen = [ster_rij(60, zotero_hit=True)] * 40 + [ster_rij(10)] * 400
        rap = star_threshold_report(rijen, candidates=[60])
        self.assertIsNone(rap["vloer"])

    def test_kiest_de_laagste_drempel_die_de_lift_haalt(self):
        rijen = (
            [ster_rij(90, zotero_hit=True)] * 40
            + [ster_rij(70, zotero_hit=True)] * 40 + [ster_rij(70)] * 60
            + [ster_rij(10)] * 900
        )
        rap = star_threshold_report(rijen, candidates=[70, 90], lift_target=2.5)
        self.assertEqual(rap["advies"], 70, "laagste drempel die de lift haalt, niet de hoogste")

    def test_te_weinig_treffers_geeft_geen_advies(self):
        """Liever geen getal dan een getal met valse precisie."""
        rijen = [ster_rij(90, zotero_hit=True)] * 5 + [ster_rij(10)] * 500
        rap = star_threshold_report(rijen, candidates=[90], lift_target=2.5, min_hits=30)
        self.assertIsNone(rap["advies"])
        self.assertIn("treffers", rap["reden"])

    def test_geen_enkele_zotero_treffer_geeft_geen_advies(self):
        rijen = [ster_rij(s) for s in (10, 50, 90)]
        rap = star_threshold_report(rijen, candidates=[50])
        self.assertIsNone(rap["advies"])
        self.assertEqual(rap["treffers_totaal"], 0)

    def test_lege_invoer_valt_niet_om(self):
        rap = star_threshold_report([], candidates=[70])
        self.assertIsNone(rap["advies"])
        self.assertEqual(rap["totaal"], 0)

    def test_drempel_zonder_gesterde_items_deelt_niet_door_nul(self):
        rijen = [ster_rij(10, zotero_hit=True)] + [ster_rij(10)] * 99
        rap = star_threshold_report(rijen, candidates=[90])
        self.assertEqual(rap["rijen"][0]["gesterd"], 0)
        self.assertEqual(rap["rijen"][0]["precisie"], 0.0)


if __name__ == "__main__":
    unittest.main()
