"""
test_feedreader_core.py — Tests voor de rekenkern van de feedreader
====================================================================
Voorlopig alleen `splits_uitval()`: de regel die een mislukte feed indeelt als
"bekend 404-venster" of als echte storing.

Achtergrond: YouTube's RSS-endpoint weigert dagelijks tussen ruwweg 04:00 en
09:00 lokale tijd met een 404, ongeacht welk IP het verzoek doet (gemeten op
12 sep 2026 vanaf drie hosts, waarvan één buiten ons netwerk — zie ADR-0012 in
ResearchVault-plans en Faalpatroon 34 in ~/bin/RUNBOOK.md). De dagrun van 09:00
haalt die items alsnog op, dus het is uitstel en geen verlies. Een waarschuwing
die elke ochtend onterecht afgaat leert je hem te negeren — precies waarom deze
storing van 16 aug tot 8 sep 2026 onopgemerkt bleef.

Draait op kale stdlib: feedreader_core importeert numpy op modulehoogte maar
gebruikt het alleen binnen functies, dus een stub volstaat. De CI-runner heeft
geen pip-install-stap.
"""
import sys
import types
import unittest
from datetime import datetime
from pathlib import Path

# Alleen stubben als numpy er echt niet is. `sys.modules.setdefault` volstaat niet:
# numpy staat pas in sys.modules nádat iets het importeerde, dus die vorm zet de stub
# ook op een machine waar de echte numpy beschikbaar is — en dan krijgt elk testbestand
# dat ná dit bestand draait de lege module. Zo brak `unittest discover` op
# test_feedreader_embed, dat wél met echte arrays rekent.
try:  # pragma: no cover — hangt van de omgeving af, niet van de code
    import numpy  # noqa: F401
except ImportError:
    sys.modules["numpy"] = types.ModuleType("numpy")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from feedreader_core import splits_uitval  # noqa: E402

YT = "https://www.youtube.com/feeds/videos.xml?channel_id=UCrDwWp7EBBv4NwvScIpBDOA"
WEB = "https://www.nrc.nl/rss/"

VROEG = datetime(2026, 9, 12, 7, 15, 0)   # in het venster
LAAT = datetime(2026, 9, 12, 14, 0, 0)    # ruim erbuiten
RAND = datetime(2026, 9, 12, 9, 0, 0)     # precies op de grens

FOUT_404 = "HTTP Error 404: Not Found"
FOUT_DNS = "<urlopen error [Errno 8] nodename nor servname provided>"


class TestSplitsUitval(unittest.TestCase):

    def test_youtube_404_in_het_venster_is_bekend(self):
        bekend, onverwacht = splits_uitval([(YT, "mislukt", FOUT_404)], VROEG)
        self.assertEqual(len(bekend), 1)
        self.assertEqual(onverwacht, [])

    def test_youtube_404_buiten_het_venster_is_onverwacht(self):
        """Een 404 om 14:00 is geen venster maar een storing."""
        bekend, onverwacht = splits_uitval([(YT, "mislukt", FOUT_404)], LAAT)
        self.assertEqual(bekend, [])
        self.assertEqual(len(onverwacht), 1)

    def test_grens_van_negen_uur_valt_buiten_het_venster(self):
        """Het venster loopt tót 09:00; de dagrun van 09:00 hoort te slagen."""
        bekend, onverwacht = splits_uitval([(YT, "mislukt", FOUT_404)], RAND)
        self.assertEqual(bekend, [])
        self.assertEqual(len(onverwacht), 1)

    def test_timeout_blijft_onverwacht(self):
        """Een time-out is iets anders dan een weigering, ook op YouTube."""
        bekend, onverwacht = splits_uitval([(YT, "timeout", None)], VROEG)
        self.assertEqual(bekend, [])
        self.assertEqual(len(onverwacht), 1)

    def test_andere_fout_dan_404_blijft_onverwacht(self):
        """Een DNS-storing om 07:00 is ook 'mislukt' en moet wél alarmeren."""
        bekend, onverwacht = splits_uitval([(YT, "mislukt", FOUT_DNS)], VROEG)
        self.assertEqual(bekend, [])
        self.assertEqual(len(onverwacht), 1)

    def test_zonder_fouttekst_blijft_onverwacht(self):
        """Geen aantoonbare 404 → geen vrijbrief."""
        bekend, onverwacht = splits_uitval([(YT, "mislukt", None)], VROEG)
        self.assertEqual(bekend, [])
        self.assertEqual(len(onverwacht), 1)

    def test_niet_youtube_blijft_onverwacht(self):
        """Het venster is aan YouTube's endpoint gemeten, niet aan het web."""
        bekend, onverwacht = splits_uitval([(WEB, "mislukt", FOUT_404)], VROEG)
        self.assertEqual(bekend, [])
        self.assertEqual(len(onverwacht), 1)

    def test_lege_lijst(self):
        self.assertEqual(splits_uitval([], VROEG), ([], []))

    def test_gemengde_lijst_behoudt_volgorde_en_inhoud(self):
        uitval = [
            (YT, "mislukt", FOUT_404),
            (WEB, "mislukt", FOUT_DNS),
            (YT, "mislukt", FOUT_404),
            (YT, "timeout", None),
        ]
        bekend, onverwacht = splits_uitval(uitval, VROEG)
        self.assertEqual(bekend, [uitval[0], uitval[2]])
        self.assertEqual(onverwacht, [uitval[1], uitval[3]])


if __name__ == "__main__":
    unittest.main()
