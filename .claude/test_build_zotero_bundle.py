"""
test_build_zotero_bundle.py — tests voor de hint bij een lege bundle.

Draait op kale stdlib. Het bestand draagt een hyphen en is niet gewoon importeerbaar;
vandaar de importlib-omweg, net als in test_feedreader_server.py.
"""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def _laad():
    sys.path.insert(0, str(SCRIPT_DIR))
    # Gezette sleutel → zotero_api slaat de dotenv-import over. Er gaat geen verzoek uit.
    os.environ.setdefault("ZOTERO_API_KEY", "test-geen-echte-sleutel")
    pad = SCRIPT_DIR / "build-zotero-bundle.py"
    spec = importlib.util.spec_from_file_location("build_zotero_bundle", pad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bz = _laad()


class TestLeegteHint(unittest.TestCase):
    """Regressietests bij de misleidende melding van 22 aug 2026.

    De guard stamt uit het PDF-geval en gaf daarom altijd "controleer de Zotero-index,
    anders OCR" — ook voor vier blogposts met een HTML-snapshot en nergens een PDF. Een
    diagnose die naar de verkeerde plek wijst kost meer tijd dan geen diagnose.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def _bundle(self, source_type):
        f = Path(self.tmp.name) / "bundle.md"
        regels = ["---", "citekey: test2026", "title: \"Titel\""]
        if source_type is not None:
            regels.append(f"source_type: {source_type}")
        regels += ["---", "", "Wat tekst."]
        f.write_text("\n".join(regels), encoding="utf-8")
        return f

    def test_web_verwijst_niet_naar_pdf_of_ocr(self):
        hint = bz._leegte_hint(self._bundle("web"), "PPWVUYJ5")
        self.assertNotIn("OCR", hint)
        self.assertNotIn("PDF", hint)
        self.assertIn("snapshot", hint)

    def test_web_noemt_het_pad_van_de_snapshot(self):
        # Zonder de key moet je zelf gaan zoeken welk bestand erbij hoort.
        self.assertIn("PPWVUYJ5.html", bz._leegte_hint(self._bundle("web"), "PPWVUYJ5"))

    def test_paper_houdt_de_index_en_ocr_tekst(self):
        hint = bz._leegte_hint(self._bundle("paper"), "ABCD1234")
        self.assertIn("index", hint.lower())
        self.assertIn("OCR", hint)

    def test_av_verwijst_naar_attach_transcript(self):
        for st in ("youtube", "podcast"):
            with self.subTest(source_type=st):
                hint = bz._leegte_hint(self._bundle(st), "FNHK8YYX")
                self.assertIn("attach-transcript.py", hint)
                self.assertIn("FNHK8YYX", hint)

    def test_onbekend_brontype_geeft_een_neutrale_hint(self):
        hint = bz._leegte_hint(self._bundle("personal"), "K1234567")
        self.assertNotIn("OCR", hint)
        self.assertIn("bijlage", hint)

    def test_ontbrekende_frontmatter_klapt_niet(self):
        self.assertTrue(bz._leegte_hint(self._bundle(None), "K1234567"))

    def test_ontbrekend_bestand_klapt_niet(self):
        weg = Path(self.tmp.name) / "bestaat-niet.md"
        self.assertTrue(bz._leegte_hint(weg, "K1234567"))

    def test_elke_hint_zegt_niet_ingesten(self):
        # De status is een stopteken; dat mag in geen enkele variant wegvallen.
        for st in ("paper", "web", "youtube", "podcast"):
            with self.subTest(source_type=st):
                self.assertIn("Niet ingesten", bz._leegte_hint(self._bundle(st), "K1234567"))


if __name__ == "__main__":
    unittest.main()
