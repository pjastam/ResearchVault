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

**Waarom deze tests hun invoer via `fetch_feed()` bouwen.** De eerste versie van
dit bestand gaf met de hand strings mee als fouttekst. Alle negen tests waren
groen terwijl het productiepad geen enkele feed goed kon indelen: `FetchResult`
draagt in `error` het *exception-object*, niet zijn tekst. De test was
`"404" in fout`, en een `urllib.error.HTTPError` is file-achtig en dus
itereerbaar — die uitdrukking gaf geen TypeError maar stil `False`, na het
aflopen van de HTML-body. Zichtbaar werd dat pas in het batchlog van 13 sep
2026. Tests die hun invoer zelf verzinnen, toetsen de aanname van de schrijver;
daarom laat `uitval_van()` de echte ophaallaag de tuple opleveren.

Draait op kale stdlib: feedreader_core importeert numpy op modulehoogte maar
gebruikt het alleen binnen functies, dus een stub volstaat. De CI-runner heeft
geen pip-install-stap.
"""
import io
import sys
import types
import unittest
import urllib.error
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
from feedreader_fetch import fetch_feed  # noqa: E402

YT = "https://www.youtube.com/feeds/videos.xml?channel_id=UCrDwWp7EBBv4NwvScIpBDOA"
WEB = "https://www.nrc.nl/rss/"

VROEG = datetime(2026, 9, 12, 7, 15, 0)   # in het venster
LAAT = datetime(2026, 9, 12, 14, 0, 0)    # ruim erbuiten
RAND = datetime(2026, 9, 12, 9, 0, 0)     # precies op de grens

# De 404-pagina die YouTube in het venster teruggeeft: 1613 bytes Google-HTML.
# De body hoort erbij — juist die maakt het HTTPError-object itereerbaar en liet
# de oude `"404" in fout` stil falen in plaats van luid.
BODY_404 = b"<!DOCTYPE html>\n<html lang=en>\n  <title>Error 404 (Not Found)!!1</title>\n"


def http_fout(code=404, msg="Not Found", url=YT, body=BODY_404):
    """Een verse `HTTPError` zoals urllib hem werpt.

    Vers per aanroep: het object draagt een fp die na één keer lezen leeg is.
    """
    return urllib.error.HTTPError(url, code, msg, {}, io.BytesIO(body))


def _werper(exc):
    """Downloader die altijd `exc` werpt — de vorm die fetch_feed injecteert."""

    def downloader(url, timeout):
        raise exc

    return downloader


def uitval_van(url, exc):
    """Bouwt de uitval-tuple langs het échte productiepad.

    `feedreader-score.py` doet `failed_feeds.append((feed_url, result.status,
    result.error))`. Door hier `fetch_feed()` te gebruiken in plaats van een
    handgeschreven tuple, toetsen deze tests het contract van FetchResult en
    niet de aanname van de schrijver over dat contract.
    """
    result = fetch_feed(
        url,
        parser=lambda raw: None,       # wordt niet bereikt: de downloader werpt
        downloader=_werper(exc),
        sleep=lambda seconden: None,   # geen echte pauze tussen de pogingen
    )
    return (url, result.status, result.error)


class TestSplitsUitval(unittest.TestCase):

    def test_youtube_404_in_het_venster_is_bekend(self):
        """De hoofdzaak, langs het productiepad: fout is een HTTPError, geen string."""
        uitval = uitval_van(YT, http_fout())
        bekend, onverwacht = splits_uitval([uitval], VROEG)
        self.assertEqual(len(bekend), 1)
        self.assertEqual(onverwacht, [])

    def test_kaal_httperror_object_wordt_herkend(self):
        """Regressie op 13 sep 2026: `"404" in <HTTPError>` gaf stil False.

        Het object is file-achtig en dus itereerbaar, dus de `in`-operator liep
        de body af in plaats van een TypeError te werpen. Deze test faalt zodra
        iemand het predicaat weer op tekst-in-tekst baseert.
        """
        fout = http_fout()
        self.assertFalse("404" in fout, "aanname van deze test: de `in`-val bestaat nog")
        bekend, onverwacht = splits_uitval([(YT, "mislukt", fout)], VROEG)
        self.assertEqual(len(bekend), 1)
        self.assertEqual(onverwacht, [])

    def test_statuscode_telt_ook_zonder_404_in_de_tekst(self):
        """Het gestructureerde signaal is `.code`, niet de rendering ervan."""

        class KaleFout(Exception):
            code = 404

            def __str__(self):
                return "endpoint weigerde het verzoek"

        bekend, onverwacht = splits_uitval([(YT, "mislukt", KaleFout())], VROEG)
        self.assertEqual(len(bekend), 1)
        self.assertEqual(onverwacht, [])

    def test_fouttekst_als_string_blijft_werken(self):
        """Andere aanroepers mogen een tekst meegeven; die weg blijft open."""
        bekend, onverwacht = splits_uitval(
            [(YT, "mislukt", "HTTP Error 404: Not Found")], VROEG)
        self.assertEqual(len(bekend), 1)
        self.assertEqual(onverwacht, [])

    def test_youtube_404_buiten_het_venster_is_onverwacht(self):
        """Een 404 om 14:00 is geen venster maar een storing."""
        uitval = uitval_van(YT, http_fout())
        bekend, onverwacht = splits_uitval([uitval], LAAT)
        self.assertEqual(bekend, [])
        self.assertEqual(len(onverwacht), 1)

    def test_grens_van_negen_uur_valt_buiten_het_venster(self):
        """Het venster loopt tót 09:00; de dagrun van 09:00 hoort te slagen."""
        uitval = uitval_van(YT, http_fout())
        bekend, onverwacht = splits_uitval([uitval], RAND)
        self.assertEqual(bekend, [])
        self.assertEqual(len(onverwacht), 1)

    def test_vijfhonderd_op_youtube_blijft_onverwacht(self):
        """Het venster is aan 404 gemeten. Een 500 is een andere storing."""
        uitval = uitval_van(YT, http_fout(code=500, msg="Internal Server Error"))
        bekend, onverwacht = splits_uitval([uitval], VROEG)
        self.assertEqual(bekend, [])
        self.assertEqual(len(onverwacht), 1)

    def test_timeout_blijft_onverwacht(self):
        """Een time-out is iets anders dan een weigering, ook op YouTube."""
        uitval = uitval_van(YT, TimeoutError("timed out"))
        self.assertEqual(uitval[1], "timeout", "de ophaallaag hoort dit als timeout te merken")
        bekend, onverwacht = splits_uitval([uitval], VROEG)
        self.assertEqual(bekend, [])
        self.assertEqual(len(onverwacht), 1)

    def test_dns_fout_blijft_onverwacht(self):
        """Een DNS-storing om 07:00 is ook 'mislukt' en moet wél alarmeren."""
        uitval = uitval_van(
            YT, urllib.error.URLError("[Errno 8] nodename nor servname provided"))
        bekend, onverwacht = splits_uitval([uitval], VROEG)
        self.assertEqual(bekend, [])
        self.assertEqual(len(onverwacht), 1)

    def test_zonder_fout_blijft_onverwacht(self):
        """Geen aantoonbare 404 → geen vrijbrief."""
        bekend, onverwacht = splits_uitval([(YT, "mislukt", None)], VROEG)
        self.assertEqual(bekend, [])
        self.assertEqual(len(onverwacht), 1)

    def test_niet_youtube_blijft_onverwacht(self):
        """Het venster is aan YouTube's endpoint gemeten, niet aan het web."""
        uitval = uitval_van(WEB, http_fout(url=WEB))
        bekend, onverwacht = splits_uitval([uitval], VROEG)
        self.assertEqual(bekend, [])
        self.assertEqual(len(onverwacht), 1)

    def test_lege_lijst(self):
        self.assertEqual(splits_uitval([], VROEG), ([], []))

    def test_gemengde_lijst_behoudt_volgorde_en_inhoud(self):
        uitval = [
            uitval_van(YT, http_fout()),
            uitval_van(WEB, urllib.error.URLError("dns")),
            uitval_van(YT, http_fout()),
            uitval_van(YT, TimeoutError("timed out")),
        ]
        bekend, onverwacht = splits_uitval(uitval, VROEG)
        self.assertEqual(bekend, [uitval[0], uitval[2]])
        self.assertEqual(onverwacht, [uitval[1], uitval[3]])


if __name__ == "__main__":
    unittest.main()
