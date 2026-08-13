"""
feedreader_fetch.py — Robuuste feed-ophaallaag
===============================================
Eén functie, `fetch_feed()`, die een RSS/Atom-feed ophaalt en onderscheid maakt
tussen drie uitkomsten: geslaagd, echt leeg, en mislukt.

Aanleiding: `feedparser.parse()` werpt geen exceptie bij een transiënte
netwerkfout — het geeft stil een leeg object terug. In de oude fetch-lus was een
mislukte fetch daardoor niet te onderscheiden van een feed die toevallig niets
publiceerde; beide logden als "0 items". Analyse van de batch-logs (juli–aug
2026) liet verstrooide uitval zien over 3–16 van de 16 YouTube-feeds per run,
op willekeurige posities — het profiel van onafhankelijke faalkansen per
verzoek, niet van een blokkade. Eén herkansing volstaat daarvoor.

`feedparser` wordt lazy geïmporteerd en de parser is injecteerbaar, zodat de
tests draaien op kale stdlib zonder netwerk.
"""

import time

FETCH_OK = "ok"           # feed opgehaald, er zijn items
FETCH_LEEG = "leeg"       # feed opgehaald en geparsed, maar zonder items
FETCH_MISLUKT = "mislukt"  # feed niet op te halen of niet te parsen

FETCH_RETRIES = 1        # aantal herkansingen ná de eerste poging
FETCH_RETRY_DELAY = 2.0  # seconden pauze vóór een herkansing
MAX_ENTRIES = 50
USER_AGENT = "Mozilla/5.0"


class FetchResult:
    """Uitkomst van één feed-ophaalpoging.

    name    — feed-titel, of de URL als die niet te achterhalen was
    entries — de items (afgekapt op max_entries)
    status  — FETCH_OK | FETCH_LEEG | FETCH_MISLUKT
    """

    __slots__ = ("name", "entries", "status", "attempts", "error")

    def __init__(self, name, entries, status, attempts=1, error=None):
        self.name = name
        self.entries = entries
        self.status = status
        self.attempts = attempts
        self.error = error

    @property
    def ok(self):
        return self.status == FETCH_OK

    def __repr__(self):
        return f"FetchResult({self.name!r}, {len(self.entries)} entries, {self.status})"


def _parse_once(parser, url):
    """Eén poging. Geeft (titel_of_None, entries, fout_of_None) terug."""
    try:
        parsed = parser(url, request_headers={"User-Agent": USER_AGENT})
    except Exception as exc:  # netwerk, DNS, TLS, malformed redirect...
        return None, [], exc

    feed = getattr(parsed, "feed", None) or {}
    title = feed.get("title") if hasattr(feed, "get") else None
    entries = list(getattr(parsed, "entries", None) or [])
    return title, entries, None


def fetch_feed(
    url,
    *,
    retries=FETCH_RETRIES,
    delay=FETCH_RETRY_DELAY,
    max_entries=MAX_ENTRIES,
    parser=None,
    sleep=None,
):
    """Haalt één feed op, met herkansing bij een verdachte fetch.

    Een fetch geldt als verdacht wanneer er géén items zijn én géén feed-titel:
    dan is de XML niet geparsed en is er dus iets misgegaan. Een feed mét titel
    maar zonder items is echt leeg — die herkansen we niet, dat zou alleen
    onnodig verkeer opleveren. Items in combinatie met een gezette bozo-vlag
    gelden als geslaagd: veel feeds in het wild hebben kleine XML-smetten en
    leveren tóch bruikbare items.
    """
    if parser is None:
        import feedparser  # lazy: houdt de tests vrij van deze afhankelijkheid

        parser = feedparser.parse
    if sleep is None:
        sleep = time.sleep

    last_error = None
    for attempt in range(retries + 1):
        if attempt:
            sleep(delay)

        title, entries, error = _parse_once(parser, url)
        if error is not None:
            last_error = error
        elif entries:
            return FetchResult(title or url, entries[:max_entries], FETCH_OK, attempt + 1)
        elif title:
            return FetchResult(title, [], FETCH_LEEG, attempt + 1)

    return FetchResult(url, [], FETCH_MISLUKT, retries + 1, last_error)
