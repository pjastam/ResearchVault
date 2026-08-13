"""
test_feedreader_fetch.py — Tests voor de feed-ophaallaag
=========================================================
Draait op kale stdlib: fetch_feed() krijgt een nep-parser geïnjecteerd,
zodat er geen feedparser en geen netwerk nodig is.
"""

import unittest

from feedreader_fetch import FETCH_LEEG, FETCH_MISLUKT, FETCH_OK, fetch_feed

URL = "https://www.youtube.com/feeds/videos.xml?channel_id=UCtest"


class FakeParsed:
    """Bootst het object na dat feedparser.parse() teruggeeft."""

    def __init__(self, title=None, entries=(), bozo=0, status=200):
        self.feed = {"title": title} if title else {}
        self.entries = list(entries)
        self.bozo = bozo
        self.status = status


class FakeParser:
    """Geeft achtereenvolgens de meegegeven resultaten terug.

    Een resultaat mag ook een exceptie-instantie zijn; die wordt dan geworpen.
    """

    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append(url)
        result = self.results[min(len(self.calls) - 1, len(self.results) - 1)]
        if isinstance(result, Exception):
            raise result
        return result


class FetchFeedTest(unittest.TestCase):
    def setUp(self):
        self.slept = []

    def _sleep(self, seconds):
        self.slept.append(seconds)

    def test_geslaagde_fetch_wordt_niet_herkanst(self):
        parser = FakeParser(FakeParsed(title="Anthropic", entries=[{"a": 1}] * 15))
        result = fetch_feed(URL, parser=parser, sleep=self._sleep)

        self.assertEqual(result.status, FETCH_OK)
        self.assertEqual(result.name, "Anthropic")
        self.assertEqual(len(result.entries), 15)
        self.assertEqual(len(parser.calls), 1, "geslaagde fetch mag niet herkanst worden")
        self.assertEqual(self.slept, [])

    def test_mislukte_fetch_wordt_herkanst_en_slaagt(self):
        # Eerste poging: geen titel, geen entries — het stille faalpatroon.
        parser = FakeParser(
            FakeParsed(),
            FakeParsed(title="Mistral", entries=[{"a": 1}] * 15),
        )
        result = fetch_feed(URL, parser=parser, delay=2.0, sleep=self._sleep)

        self.assertEqual(result.status, FETCH_OK)
        self.assertEqual(result.name, "Mistral")
        self.assertEqual(len(result.entries), 15)
        self.assertEqual(len(parser.calls), 2)
        self.assertEqual(self.slept, [2.0], "er hoort één pauze tussen de pogingen te zitten")

    def test_beide_pogingen_mislukt(self):
        parser = FakeParser(FakeParsed(), FakeParsed())
        result = fetch_feed(URL, parser=parser, sleep=self._sleep)

        self.assertEqual(result.status, FETCH_MISLUKT)
        self.assertEqual(result.name, URL, "bij falen blijft de URL de weergavenaam")
        self.assertEqual(result.entries, [])
        self.assertEqual(len(parser.calls), 2)

    def test_lege_maar_levende_feed_wordt_niet_herkanst(self):
        # Titel aanwezig => de XML is geparsed; de feed is echt leeg.
        parser = FakeParser(FakeParsed(title="Stille Podcast", entries=[]))
        result = fetch_feed(URL, parser=parser, sleep=self._sleep)

        self.assertEqual(result.status, FETCH_LEEG)
        self.assertEqual(result.name, "Stille Podcast")
        self.assertEqual(len(parser.calls), 1, "een echt lege feed is geen fout")

    def test_bozo_met_entries_telt_als_geslaagd(self):
        # Veel feeds in het wild zetten bozo op kleine XML-smetten en
        # leveren tóch bruikbare items. Die mogen we niet weggooien.
        parser = FakeParser(FakeParsed(title="Slordige Feed", entries=[{"a": 1}], bozo=1))
        result = fetch_feed(URL, parser=parser, sleep=self._sleep)

        self.assertEqual(result.status, FETCH_OK)
        self.assertEqual(len(parser.calls), 1)

    def test_exceptie_wordt_opgevangen_en_herkanst(self):
        parser = FakeParser(
            OSError("connection reset"),
            FakeParsed(title="Hersteld", entries=[{"a": 1}]),
        )
        result = fetch_feed(URL, parser=parser, sleep=self._sleep)

        self.assertEqual(result.status, FETCH_OK)
        self.assertEqual(result.name, "Hersteld")
        self.assertEqual(len(parser.calls), 2)

    def test_exceptie_bij_alle_pogingen_geeft_mislukt(self):
        parser = FakeParser(OSError("dns"), OSError("dns"))
        result = fetch_feed(URL, parser=parser, sleep=self._sleep)

        self.assertEqual(result.status, FETCH_MISLUKT)
        self.assertEqual(result.entries, [])

    def test_entries_worden_gecapt(self):
        parser = FakeParser(FakeParsed(title="Veel", entries=[{"a": 1}] * 80))
        result = fetch_feed(URL, parser=parser, max_entries=50, sleep=self._sleep)

        self.assertEqual(len(result.entries), 50)

    def test_retries_nul_doet_geen_herkansing(self):
        parser = FakeParser(FakeParsed(), FakeParsed(title="Te laat", entries=[{"a": 1}]))
        result = fetch_feed(URL, parser=parser, retries=0, sleep=self._sleep)

        self.assertEqual(result.status, FETCH_MISLUKT)
        self.assertEqual(len(parser.calls), 1)

    def test_user_agent_wordt_meegestuurd(self):
        captured = {}

        def parser(url, **kwargs):
            captured.update(kwargs)
            return FakeParsed(title="X", entries=[{"a": 1}])

        fetch_feed(URL, parser=parser, sleep=self._sleep)
        self.assertIn("request_headers", captured)
        self.assertIn("User-Agent", captured["request_headers"])


if __name__ == "__main__":
    unittest.main()
