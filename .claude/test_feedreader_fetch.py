"""
test_feedreader_fetch.py — Tests voor de feed-ophaallaag
=========================================================
Draait op kale stdlib: downloader en parser worden geïnjecteerd, zodat er
geen feedparser en geen netwerk nodig zijn.
"""

import gzip
import unittest

from feedreader_fetch import (
    FETCH_LEEG,
    FETCH_MISLUKT,
    FETCH_OK,
    FETCH_TIMEOUT,
    USER_AGENT,
    _maybe_gunzip,
    fetch_feed,
)

URL = "https://www.youtube.com/feeds/videos.xml?channel_id=UCtest"
RAW = b"<feed/>"


class FakeParsed:
    """Bootst het object na dat feedparser.parse() teruggeeft."""

    def __init__(self, title=None, entries=(), bozo=0):
        self.feed = {"title": title} if title else {}
        self.entries = list(entries)
        self.bozo = bozo


class FakeParser:
    """Geeft achtereenvolgens de meegegeven resultaten terug."""

    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def __call__(self, data):
        self.calls.append(data)
        return self.results[min(len(self.calls) - 1, len(self.results) - 1)]


class FakeDownloader:
    """Geeft bytes terug, of werpt een meegegeven exceptie."""

    def __init__(self, *results):
        self.results = list(results) or [RAW]
        self.calls = []

    def __call__(self, url, timeout):
        self.calls.append((url, timeout))
        result = self.results[min(len(self.calls) - 1, len(self.results) - 1)]
        if isinstance(result, Exception):
            raise result
        return result


class GunzipTest(unittest.TestCase):
    def test_gzip_wordt_uitgepakt(self):
        packed = gzip.compress(b"<feed>hallo</feed>")
        self.assertEqual(_maybe_gunzip(packed), b"<feed>hallo</feed>")

    def test_platte_bytes_blijven_ongemoeid(self):
        self.assertEqual(_maybe_gunzip(b"<feed/>"), b"<feed/>")

    def test_gzip_met_rommel_erachter(self):
        # Vastgesteld bij piratenpartij.nl: een caching-plugin plakt platte HTML
        # achter de gzip-stroom. gzip.decompress() weigert dat volledig, want die
        # eist dat álle bytes gzip-leden zijn — de feed leek daardoor kapot.
        packed = gzip.compress(b"<feed>echt</feed>") + b"\n<!-- plugin-handtekening -->"
        self.assertEqual(_maybe_gunzip(packed), b"<feed>echt</feed>")

    def test_meerdere_gzip_leden_blijven_volledig(self):
        # Aaneengeschakelde gzip-leden zijn legitiem en horen állemaal uitgepakt
        # te worden — de redding-route voor trailing rommel mag dit niet breken.
        packed = gzip.compress(b"<a/>") + gzip.compress(b"<b/>")
        self.assertEqual(_maybe_gunzip(packed), b"<a/><b/>")

    def test_kapotte_gzip_geeft_ruwe_bytes_terug(self):
        # Begint met gzip-magic maar is afgekapt: niet crashen, ruw teruggeven
        broken = b"\x1f\x8b" + b"rommel"
        self.assertEqual(_maybe_gunzip(broken), broken)

    def test_lege_invoer(self):
        self.assertEqual(_maybe_gunzip(b""), b"")


class FetchFeedTest(unittest.TestCase):
    def setUp(self):
        self.slept = []

    def _sleep(self, seconds):
        self.slept.append(seconds)

    def _fetch(self, parser, downloader=None, **kw):
        return fetch_feed(
            URL,
            parser=parser,
            downloader=downloader or FakeDownloader(),
            sleep=self._sleep,
            **kw,
        )

    def test_geslaagde_fetch_wordt_niet_herkanst(self):
        parser = FakeParser(FakeParsed(title="Anthropic", entries=[{"a": 1}] * 15))
        dl = FakeDownloader()
        result = self._fetch(parser, dl)

        self.assertEqual(result.status, FETCH_OK)
        self.assertEqual(result.name, "Anthropic")
        self.assertEqual(len(result.entries), 15)
        self.assertEqual(len(dl.calls), 1, "geslaagde fetch mag niet herkanst worden")
        self.assertEqual(self.slept, [])

    def test_mislukte_fetch_wordt_herkanst_en_slaagt(self):
        parser = FakeParser(
            FakeParsed(),  # geen titel, geen entries — het stille faalpatroon
            FakeParsed(title="Mistral", entries=[{"a": 1}] * 15),
        )
        dl = FakeDownloader()
        result = self._fetch(parser, dl, delay=2.0)

        self.assertEqual(result.status, FETCH_OK)
        self.assertEqual(result.name, "Mistral")
        self.assertEqual(len(dl.calls), 2)
        self.assertEqual(self.slept, [2.0])

    def test_beide_pogingen_mislukt(self):
        parser = FakeParser(FakeParsed(), FakeParsed())
        result = self._fetch(parser)

        self.assertEqual(result.status, FETCH_MISLUKT)
        self.assertEqual(result.name, URL)
        self.assertEqual(result.entries, [])

    def test_lege_maar_levende_feed_wordt_niet_herkanst(self):
        parser = FakeParser(FakeParsed(title="Stille Podcast", entries=[]))
        dl = FakeDownloader()
        result = self._fetch(parser, dl)

        self.assertEqual(result.status, FETCH_LEEG)
        self.assertEqual(len(dl.calls), 1, "een echt lege feed is geen fout")

    def test_bozo_met_entries_telt_als_geslaagd(self):
        parser = FakeParser(FakeParsed(title="Slordige Feed", entries=[{"a": 1}], bozo=1))
        dl = FakeDownloader()
        result = self._fetch(parser, dl)

        self.assertEqual(result.status, FETCH_OK)
        self.assertEqual(len(dl.calls), 1)

    def test_netwerkfout_wordt_herkanst(self):
        parser = FakeParser(FakeParsed(title="Hersteld", entries=[{"a": 1}]))
        dl = FakeDownloader(OSError("connection reset"), RAW)
        result = self._fetch(parser, dl)

        self.assertEqual(result.status, FETCH_OK)
        self.assertEqual(len(dl.calls), 2)

    def test_netwerkfout_bij_alle_pogingen(self):
        parser = FakeParser(FakeParsed())
        dl = FakeDownloader(OSError("dns"), OSError("dns"))
        result = self._fetch(parser, dl)

        self.assertEqual(result.status, FETCH_MISLUKT)
        self.assertIsNotNone(result.error)

    def test_timeout_krijgt_eigen_status(self):
        parser = FakeParser(FakeParsed())
        dl = FakeDownloader(TimeoutError("timed out"), TimeoutError("timed out"))
        result = self._fetch(parser, dl)

        self.assertEqual(result.status, FETCH_TIMEOUT)
        self.assertEqual(result.entries, [])

    def test_timeout_wordt_doorgegeven_aan_downloader(self):
        parser = FakeParser(FakeParsed(title="X", entries=[{"a": 1}]))
        dl = FakeDownloader()
        self._fetch(parser, dl, timeout=7)

        self.assertEqual(dl.calls[0][1], 7, "de tijdslimiet hoort bij de downloader te komen")

    def test_gzip_wordt_uitgepakt_voor_de_parser(self):
        # De downloader-default pakt uit; hier controleren we dat fetch_feed
        # de bytes onaangeroerd doorgeeft aan de parser.
        parser = FakeParser(FakeParsed(title="X", entries=[{"a": 1}]))
        dl = FakeDownloader(b"<feed>plat</feed>")
        self._fetch(parser, dl)

        self.assertEqual(parser.calls[0], b"<feed>plat</feed>")

    def test_entries_worden_gecapt(self):
        parser = FakeParser(FakeParsed(title="Veel", entries=[{"a": 1}] * 80))
        result = self._fetch(parser, max_entries=50)

        self.assertEqual(len(result.entries), 50)

    def test_retries_nul_doet_geen_herkansing(self):
        parser = FakeParser(FakeParsed(), FakeParsed(title="Te laat", entries=[{"a": 1}]))
        dl = FakeDownloader()
        result = self._fetch(parser, dl, retries=0)

        self.assertEqual(result.status, FETCH_MISLUKT)
        self.assertEqual(len(dl.calls), 1)

    def test_parserfout_wordt_opgevangen(self):
        # Een parser die zelf ontploft mag de hele run niet vellen.
        def exploding(data):
            raise ValueError("kapot")

        result = self._fetch(exploding)
        self.assertEqual(result.status, FETCH_MISLUKT)


class DefaultDownloaderTest(unittest.TestCase):
    def test_user_agent_en_gzip_worden_gevraagd(self):
        import feedreader_fetch

        captured = {}

        class FakeResponse:
            def read(self):
                return b"<feed/>"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=None):
            captured["headers"] = dict(req.header_items())
            captured["timeout"] = timeout
            return FakeResponse()

        original = feedreader_fetch.urllib.request.urlopen
        feedreader_fetch.urllib.request.urlopen = fake_urlopen
        try:
            data = feedreader_fetch._default_downloader(URL, timeout=9)
        finally:
            feedreader_fetch.urllib.request.urlopen = original

        self.assertEqual(data, b"<feed/>")
        self.assertEqual(captured["timeout"], 9)
        headers = {k.lower(): v for k, v in captured["headers"].items()}
        self.assertEqual(headers.get("User-agent".lower()), USER_AGENT)
        self.assertIn("gzip", headers.get("Accept-encoding".lower(), ""))


if __name__ == "__main__":
    unittest.main()
