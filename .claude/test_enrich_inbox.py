"""
test_enrich_inbox.py — tests voor de systematische-foutdetectie van enrich-inbox.

Draait op kale stdlib (de CI heeft geen pip-install-stap). Het bestand draagt een
hyphen en is dus niet gewoon importeerbaar; vandaar de importlib-omweg, net als in
test_feedreader_server.py.
"""
import importlib.util
import os
import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def _laad():
    # `zotero_api` staat naast dit bestand, niet op sys.path bij een importlib-load.
    sys.path.insert(0, str(SCRIPT_DIR))
    # Een gezette sleutel laat zotero_api de dotenv-import overslaan, zodat de test
    # ook zonder python-dotenv draait (CI installeert niets). De waarde wordt hier
    # nooit gebruikt: er gaat geen enkel verzoek uit.
    os.environ.setdefault("ZOTERO_API_KEY", "test-geen-echte-sleutel")
    pad = SCRIPT_DIR / "enrich-inbox.py"
    spec = importlib.util.spec_from_file_location("enrich_inbox", pad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ei = _laad()


def fouten(*meldingen):
    return [{"key": f"K{i:04d}", "error": m} for i, m in enumerate(meldingen)]


class TestFoutsignatuur(unittest.TestCase):
    def test_http_status_wordt_de_signatuur(self):
        self.assertEqual(
            ei._foutsignatuur("HTTP 501 Not Implemented: Method not implemented\n"),
            "HTTP 501")

    def test_verschillende_statussen_vallen_niet_samen(self):
        self.assertNotEqual(ei._foutsignatuur("HTTP 501 x"), ei._foutsignatuur("HTTP 404 x"))

    def test_zonder_http_status_de_eerste_regel(self):
        self.assertEqual(ei._foutsignatuur("timeout na 30s\nstack…"), "timeout na 30s")

    def test_lege_melding_klapt_niet(self):
        self.assertEqual(ei._foutsignatuur(""), "?")


class TestSystematischeFout(unittest.TestCase):
    """Het gemeten geval van 22 aug 2026 en de randen eromheen."""

    def test_het_gemeten_geval_501(self):
        # De 09:00-overdagrun: alle vijf schrijfacties 501, niets verrijkt, exit 0.
        storing = ei.systematische_fout(0, fouten(*["HTTP 501 Not Implemented"] * 5))
        self.assertIsNotNone(storing)
        self.assertIn("HTTP 501", storing)

    def test_incidentele_ruis_is_geen_storing(self):
        # 20 items verrijkt, 3 losse en verschillende fouten → normaal.
        storing = ei.systematische_fout(
            20, fouten("HTTP 404 niet gevonden", "timeout na 30s", "geen DOI"))
        self.assertIsNone(storing)

    def test_dominante_oorzaak_ondanks_successen(self):
        # 4 geslaagd, 5x dezelfde oorzaak → 5 van 9, dus meer dan de helft.
        storing = ei.systematische_fout(4, fouten(*["HTTP 429 Too Many Requests"] * 5))
        self.assertIsNotNone(storing)
        self.assertIn("HTTP 429", storing)

    def test_dominant_maar_minderheid_is_geen_storing(self):
        # 20 geslaagd, 3x dezelfde oorzaak → 3 van 23; te weinig om een storing te heten.
        self.assertIsNone(ei.systematische_fout(20, fouten(*["HTTP 429"] * 3)))

    def test_onder_de_ondergrens_geen_alarm(self):
        # Twee fouten en niets geslaagd: te weinig bewijs voor "de weg is dicht".
        self.assertIsNone(ei.systematische_fout(0, fouten("HTTP 501", "HTTP 501")))

    def test_niets_te_doen_is_geen_storing(self):
        # Alles al verrijkt → geen pogingen, geen fouten.
        self.assertIsNone(ei.systematische_fout(0, []))

    def test_alles_geslaagd_is_geen_storing(self):
        self.assertIsNone(ei.systematische_fout(12, []))


if __name__ == "__main__":
    unittest.main()
