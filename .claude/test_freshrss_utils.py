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
    STREAM_TIMEOUT,
    freshrss_fetch_stream,
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


if __name__ == "__main__":
    unittest.main()
