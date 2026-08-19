"""
test_freshrss_utils.py — Tests voor de FreshRSS GReader-laag
=============================================================
Draait op kale stdlib: de opener wordt geïnjecteerd, dus geen netwerk en geen
FreshRSS nodig. Zelfde opzet als test_feedreader_fetch.py.

Aanleiding: `freshrss_fetch_stream` deed `except Exception: return {}`, waardoor
HTTP 400, netwerkfouten, verlopen auth en een echt lege stream ononderscheidbaar
waren. Signaal 3 uit de leerloop (NNW-gelezen) stond daardoor maandenlang droog
zonder dat iets het meldde.
"""

import json
import unittest
import urllib.error

from freshrss_utils import (
    STREAM_LEEG,
    STREAM_MISLUKT,
    STREAM_OK,
    STREAM_AFGEKAPT,
    STREAM_TIMEOUT,
    freshrss_fetch_stream,
    freshrss_read_stream,
)

BASE = "http://freshrss.test/api"
AUTH = "token123"
STREAM = "user/-/state/com.google/starred"


class FakeOpener:
    """Geeft een JSON-body terug, of werpt een meegegeven exceptie."""

    def __init__(self, result):
        self.result = result
        self.calls = []

    def __call__(self, url, timeout):
        self.calls.append((url, timeout))
        if isinstance(self.result, Exception):
            raise self.result
        return json.dumps(self.result).encode("utf-8")


class FakePager:
    """Geeft achtereenvolgens de meegegeven pagina's terug.

    Elke pagina is een dict zoals GReader hem levert: {"items": [...],
    "continuation": "<token>"} — zonder `continuation` is de stroom op.
    Een Exception in de lijst wordt geworpen op die pagina.
    """

    def __init__(self, *pages):
        self.pages = list(pages)
        self.calls = []

    def __call__(self, url, timeout):
        self.calls.append(url)
        page = self.pages[min(len(self.calls) - 1, len(self.pages) - 1)]
        if isinstance(page, Exception):
            raise page
        return json.dumps(page).encode("utf-8")


def pagina(start, aantal, continuation=None, gelezen=False):
    """Bouwt een GReader-pagina met `aantal` items, genummerd vanaf `start`."""
    cats = ["user/-/state/com.google/reading-list"]
    if gelezen:
        cats.append("user/-/state/com.google/read")
    page = {"items": [
        {"id": f"g{i}", "categories": list(cats),
         "alternate": [{"href": f"https://a.test/{i}"}]}
        for i in range(start, start + aantal)
    ]}
    if continuation:
        page["continuation"] = continuation
    return page


class FetchStreamTest(unittest.TestCase):
    def test_items_geven_status_ok(self):
        body = {"items": [{"id": "g1", "alternate": [{"href": "https://a.test/1"}]}]}
        res = freshrss_fetch_stream(BASE, AUTH, STREAM, opener=FakeOpener(body))
        self.assertEqual(res.status, STREAM_OK)
        self.assertTrue(res.ok)
        self.assertFalse(res.failed)
        self.assertEqual(res.items, {"https://a.test/1": "g1"})

    def test_lege_stream_is_leeg_niet_mislukt(self):
        res = freshrss_fetch_stream(BASE, AUTH, STREAM, opener=FakeOpener({"items": []}))
        self.assertEqual(res.status, STREAM_LEEG)
        self.assertFalse(res.failed)
        self.assertEqual(res.items, {})

    def test_http_400_is_mislukt(self):
        exc = urllib.error.HTTPError(BASE, 400, "Bad Request", {}, None)
        res = freshrss_fetch_stream(BASE, AUTH, STREAM, opener=FakeOpener(exc))
        self.assertEqual(res.status, STREAM_MISLUKT)
        self.assertTrue(res.failed)
        self.assertIn("400", str(res.error))

    def test_timeout_is_eigen_status(self):
        res = freshrss_fetch_stream(BASE, AUTH, STREAM, opener=FakeOpener(TimeoutError()))
        self.assertEqual(res.status, STREAM_TIMEOUT)
        self.assertTrue(res.failed)

    def test_urlerror_met_timeout_reden_telt_als_timeout(self):
        exc = urllib.error.URLError(TimeoutError("timed out"))
        res = freshrss_fetch_stream(BASE, AUTH, STREAM, opener=FakeOpener(exc))
        self.assertEqual(res.status, STREAM_TIMEOUT)

    def test_kapotte_json_is_mislukt(self):
        class BadOpener:
            def __call__(self, url, timeout):
                return b"<html>niet eens json</html>"

        res = freshrss_fetch_stream(BASE, AUTH, STREAM, opener=BadOpener())
        self.assertEqual(res.status, STREAM_MISLUKT)

    def test_item_zonder_bruikbare_alternate_wordt_overgeslagen(self):
        body = {"items": [
            {"id": "g1", "alternate": [{"type": "text/html"}]},
            {"id": "g2", "alternate": [{"href": "https://a.test/2"}]},
        ]}
        res = freshrss_fetch_stream(BASE, AUTH, STREAM, opener=FakeOpener(body))
        self.assertEqual(res.items, {"https://a.test/2": "g2"})


class ReadStreamRouteTest(unittest.TestCase):
    """De read-state komt uit de reading-list, niet uit een eigen read-stream.

    FreshRSS antwoordt op stream/contents/user/-/state/com.google/read met
    HTTP 400 (vastgesteld 17 aug 2026, live gereproduceerd 19 aug). De
    reading-list levert dezelfde items mét hun categorieën, en die dragen de
    read-state — één call, en de URL zit erbij.
    """

    def test_leest_read_state_uit_categories(self):
        body = {"items": [
            {"id": "g1",
             "categories": ["user/-/state/com.google/reading-list",
                            "user/-/state/com.google/read"],
             "alternate": [{"href": "https://a.test/gelezen"}]},
            {"id": "g2",
             "categories": ["user/-/state/com.google/reading-list"],
             "alternate": [{"href": "https://a.test/ongelezen"}]},
        ]}
        res = freshrss_read_stream(BASE, AUTH, opener=FakeOpener(body))
        self.assertEqual(res.status, STREAM_OK)
        self.assertEqual(res.items, {"https://a.test/gelezen": "g1"})

    def test_vraagt_de_reading_list_op_niet_de_read_stream(self):
        opener = FakeOpener({"items": []})
        freshrss_read_stream(BASE, AUTH, opener=opener)
        gevraagde_url = opener.calls[0][0]
        self.assertIn("reading-list", gevraagde_url)
        # De oude route eindigde op .../com.google/read?… — die geeft bij FreshRSS 400.
        self.assertNotIn("com.google/read?", gevraagde_url)

    def test_geen_gelezen_items_is_leeg_niet_mislukt(self):
        body = {"items": [
            {"id": "g2",
             "categories": ["user/-/state/com.google/reading-list"],
             "alternate": [{"href": "https://a.test/ongelezen"}]},
        ]}
        res = freshrss_read_stream(BASE, AUTH, opener=FakeOpener(body))
        self.assertEqual(res.status, STREAM_LEEG)
        self.assertFalse(res.failed)

    def test_mislukte_fetch_blijft_mislukt(self):
        exc = urllib.error.HTTPError(BASE, 500, "Server Error", {}, None)
        res = freshrss_read_stream(BASE, AUTH, opener=FakeOpener(exc))
        self.assertTrue(res.failed)
        self.assertEqual(res.status, STREAM_MISLUKT)

    def test_item_zonder_categories_telt_niet_als_gelezen(self):
        body = {"items": [{"id": "g3", "alternate": [{"href": "https://a.test/x"}]}]}
        res = freshrss_read_stream(BASE, AUTH, opener=FakeOpener(body))
        self.assertEqual(res.items, {})


class PagineringTest(unittest.TestCase):
    """Een stream mag nooit stil bij de paginagrens ophouden.

    `n=1000` gaf op 19 aug 2026 999 gesterde items terug terwijl er 1.797 waren,
    997 van de 2.476 reading-list-items, en 57 van de 218 gelezen items. Een
    verzoeklimiet die zich voordoet als een compleet antwoord — dezelfde
    vermomming als "0 items" bij een mislukte fetch.
    """

    def test_leest_door_tot_de_stream_op_is(self):
        opener = FakePager(
            pagina(0, 3, continuation="tok1"),
            pagina(3, 3, continuation="tok2"),
            pagina(6, 2),  # geen continuation → klaar
        )
        res = freshrss_fetch_stream(BASE, AUTH, STREAM, page_size=3, opener=opener)
        self.assertEqual(res.status, STREAM_OK)
        self.assertEqual(len(res.items), 8)
        self.assertEqual(len(opener.calls), 3)

    def test_geeft_het_continuation_token_mee(self):
        opener = FakePager(pagina(0, 2, continuation="tok1"), pagina(2, 1))
        freshrss_fetch_stream(BASE, AUTH, STREAM, page_size=2, opener=opener)
        self.assertNotIn("c=", opener.calls[0])
        self.assertIn("c=tok1", opener.calls[1])

    def test_eerste_pagina_zonder_continuation_doet_een_ronde(self):
        opener = FakePager(pagina(0, 2))
        res = freshrss_fetch_stream(BASE, AUTH, STREAM, page_size=1000, opener=opener)
        self.assertEqual(len(opener.calls), 1)
        self.assertEqual(len(res.items), 2)

    def test_veiligheidsgrens_geeft_een_eigen_status(self):
        """Bij de bovengrens stoppen we — maar dan mag het geen 'ok' heten."""
        opener = FakePager(
            pagina(0, 3, continuation="tok1"),
            pagina(3, 3, continuation="tok2"),
            pagina(6, 3, continuation="tok3"),
        )
        res = freshrss_fetch_stream(BASE, AUTH, STREAM, page_size=3,
                                    max_items=6, opener=opener)
        self.assertEqual(res.status, STREAM_AFGEKAPT)
        self.assertTrue(res.failed, "afgekapt telt als onbetrouwbaar")

    def test_storing_op_een_latere_pagina_is_mislukt_niet_gedeeltelijk(self):
        """Een half gelezen stream is niet te onderscheiden van een hele.

        Downstream labelt er negatieven mee, dus gedeeltelijke data stil
        doorgeven zou items als 'niet gelezen' wegzetten die dat wel zijn.
        """
        opener = FakePager(
            pagina(0, 3, continuation="tok1"),
            urllib.error.HTTPError(BASE, 500, "boom", {}, None),
        )
        res = freshrss_fetch_stream(BASE, AUTH, STREAM, page_size=3, opener=opener)
        self.assertEqual(res.status, STREAM_MISLUKT)
        self.assertTrue(res.failed)

    def test_read_stream_pagineert_ook(self):
        opener = FakePager(
            pagina(0, 2, continuation="tok1", gelezen=True),
            pagina(2, 2, gelezen=True),
        )
        res = freshrss_read_stream(BASE, AUTH, page_size=2, opener=opener)
        self.assertEqual(len(res.items), 4)
        self.assertEqual(len(opener.calls), 2)


if __name__ == "__main__":
    unittest.main()
