"""
test_fetch_fulltext.py — tests voor de keuze tussen trafilatura en de naïeve strip.

Draait op kale stdlib (de CI heeft geen pip-install-stap en dus geen trafilatura); de
beslissing zit daarom in `_kies_tekst()`, los van de extractie zelf. Het bestand draagt
een hyphen en is niet gewoon importeerbaar; vandaar de importlib-omweg.
"""
import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def _laad():
    sys.path.insert(0, str(SCRIPT_DIR))
    pad = SCRIPT_DIR / "fetch-fulltext.py"
    spec = importlib.util.spec_from_file_location("fetch_fulltext", pad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ff = _laad()


def woorden(n):
    return " ".join(["woord"] * n)


class TestKiesTekst(unittest.TestCase):
    """Regressietests bij de vier gestrande artikelen van 22 aug 2026.

    De oude toets was `if extracted and extracted.strip()` — bestáát er output. Een
    degeneratieve extractie is niet leeg en glipte daar dus doorheen.
    """

    # De gemeten woordentellingen: (item, trafilatura, naïeve strip)
    GEMETEN = [("PPWVUYJ5", 58, 498), ("GXAHWB4K", 183, 587),
               ("R259SKCH", 52, 966), ("6STPYA4B", 239, 717)]

    def test_de_vier_gemeten_gevallen_vallen_terug(self):
        for naam, n_traf, n_naief in self.GEMETEN:
            with self.subTest(item=naam):
                gekozen = ff._kies_tekst(woorden(n_traf), woorden(n_naief))
                self.assertEqual(len(gekozen.split()), n_naief,
                                 f"{naam} had de naïeve strip moeten krijgen")

    def test_de_vier_halen_daarna_de_bundeldrempel(self):
        # Anders is de terugval zinloos: de bundle wordt dan alsnog afgewezen.
        for naam, n_traf, n_naief in self.GEMETEN:
            with self.subTest(item=naam):
                gekozen = ff._kies_tekst(woorden(n_traf), woorden(n_naief))
                self.assertGreaterEqual(len(gekozen.split()), ff.MIN_ARTIKEL_WOORDEN)

    def test_geslaagde_extractie_wint_ook_al_is_naief_veel_groter(self):
        # Dít is waar trafilatura voor bestaat (Tweakers: ~170 KB → ~5 KB). Een kleinere
        # uitkomst is normaal en mag nooit als faalsignaal gelden.
        gekozen = ff._kies_tekst(woorden(1200), woorden(30000))
        self.assertEqual(len(gekozen.split()), 1200)

    def test_precies_op_de_drempel_wint_de_extractie(self):
        gekozen = ff._kies_tekst(woorden(ff.MIN_ARTIKEL_WOORDEN), woorden(9000))
        self.assertEqual(len(gekozen.split()), ff.MIN_ARTIKEL_WOORDEN)

    def test_een_woord_onder_de_drempel_valt_terug(self):
        gekozen = ff._kies_tekst(woorden(ff.MIN_ARTIKEL_WOORDEN - 1), woorden(9000))
        self.assertEqual(len(gekozen.split()), 9000)

    def test_naief_kleiner_dan_extractie_verandert_niets(self):
        # Beide te kort; de naïeve strip levert minder op → geen reden om te wisselen.
        gekozen = ff._kies_tekst(woorden(120), woorden(40))
        self.assertEqual(len(gekozen.split()), 120)

    def test_lege_extractie_pakt_de_naieve_strip(self):
        # Het oorspronkelijke geval waar de terugval voor bedoeld was; blijft werken.
        self.assertEqual(len(ff._kies_tekst("", woorden(500)).split()), 500)

    def test_allebei_leeg(self):
        self.assertEqual(ff._kies_tekst("", ""), "")

    def test_drempel_gelijk_aan_de_bundelguard(self):
        # Loopt die uit de pas, dan redt de terugval bundles die alsnog worden afgewezen.
        self.assertEqual(ff.MIN_ARTIKEL_WOORDEN, 300)


if __name__ == "__main__":
    unittest.main()
