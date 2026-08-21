"""
test_feedreader_server.py — tests voor de padbeveiliging van de feedreader-server.

Draait op kale stdlib (de CI heeft geen pip-install-stap). Het bestand draagt een
hyphen en is dus niet gewoon importeerbaar; vandaar de importlib-omweg, net als in
backfill-scout.py.
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path


def _laad():
    pad = Path(__file__).resolve().parent / "feedreader-server.py"
    spec = importlib.util.spec_from_file_location("feedreader_server", pad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


srv = _laad()


class TestVeiligPad(unittest.TestCase):
    """Regressietests bij de padtraversal van 21 aug 2026.

    Toen gaf `GET /../buiten.xml` een HTTP 200 op een bestand buiten de serveermap,
    ook via de publieke Tailscale-Funnel.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.basis = Path(self.tmp.name) / "serve"
        self.basis.mkdir()
        (self.basis / "filtered-tv.xml").write_text("<feed/>")
        (self.basis / "sub").mkdir()
        (self.basis / "sub" / "diep.xml").write_text("<feed/>")
        # het bestand dat destijds lekte: één niveau boven de serveermap
        (Path(self.tmp.name) / "buiten.xml").write_text("<geheim/>")

    def tearDown(self):
        self.tmp.cleanup()

    # ── wat er door moet ──────────────────────────────────────────────────────

    def test_gewoon_bestand(self):
        self.assertEqual(srv.veilig_pad(self.basis, "/filtered-tv.xml"),
                         (self.basis / "filtered-tv.xml").resolve())

    def test_submap(self):
        self.assertEqual(srv.veilig_pad(self.basis, "/sub/diep.xml"),
                         (self.basis / "sub" / "diep.xml").resolve())

    def test_dubbele_slash_blijft_binnen(self):
        # lstrip("/") maakt hier een relatief pad van; blijft dus in de serveermap
        self.assertIsNotNone(srv.veilig_pad(self.basis, "//filtered-tv.xml"))

    def test_niet_bestaand_pad_binnen_de_map_is_toegestaan(self):
        # bestaan is de zorg van de aanroeper; deze functie oordeelt alleen over ligging
        self.assertIsNotNone(srv.veilig_pad(self.basis, "/bestaat-niet.xml"))

    # ── wat er tegen moet worden gehouden ─────────────────────────────────────

    def test_traversal_wordt_geweigerd(self):
        self.assertIsNone(srv.veilig_pad(self.basis, "/../buiten.xml"))

    def test_diepe_traversal_wordt_geweigerd(self):
        self.assertIsNone(srv.veilig_pad(self.basis, "/../../../../etc/passwd.xml"))

    def test_percent_gecodeerde_traversal_wordt_geweigerd(self):
        # zonder unquote glipt deze vorm erlangs
        self.assertIsNone(srv.veilig_pad(self.basis, "/%2e%2e/buiten.xml"))
        self.assertIsNone(srv.veilig_pad(self.basis, "/..%2fbuiten.xml"))

    def test_traversal_die_terugkomt_is_toegestaan(self):
        # /sub/../filtered-tv.xml wijst nog steeds naar binnen
        self.assertIsNotNone(srv.veilig_pad(self.basis, "/sub/../filtered-tv.xml"))

    def test_symlink_naar_buiten_wordt_geweigerd(self):
        link = self.basis / "ontsnapping.xml"
        link.symlink_to(Path(self.tmp.name) / "buiten.xml")
        self.assertIsNone(srv.veilig_pad(self.basis, "/ontsnapping.xml"))

    def test_serveermap_zelf_is_geen_bestand(self):
        self.assertIsNone(srv.veilig_pad(self.basis, "/"))

    def test_nulbyte_wordt_geweigerd(self):
        self.assertIsNone(srv.veilig_pad(self.basis, "/filtered%00.xml"))


if __name__ == "__main__":
    unittest.main()
