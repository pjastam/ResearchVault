"""
feedreader_fetch.py — Robuuste feed-ophaallaag
===============================================
Eén functie, `fetch_feed()`, die een RSS/Atom-feed ophaalt en onderscheid maakt
tussen vier uitkomsten: geslaagd, echt leeg, mislukt en time-out.

Waarom deze laag bestaat — twee onafhankelijke gebreken in de naïeve aanpak:

1. `feedparser.parse()` werpt geen exceptie bij een transiënte netwerkfout; het
   geeft stil een leeg object terug. Een mislukte fetch was daardoor niet te
   onderscheiden van een feed die toevallig niets publiceerde: beide logden als
   "0 items". Analyse van de batch-logs (jul–aug 2026) toonde verstrooide uitval
   over 3–16 van de 16 YouTube-feeds per run — onafhankelijke faalkansen per
   verzoek, waar één herkansing tegen helpt.

2. De ingebouwde downloader van feedparser krijgt geen time-out mee, dus een
   server die de verbinding openhoudt zonder te antwoorden laat de hele run
   hangen tot de batch-wrapper (`run_timeout 600`) het scoring-proces afschiet —
   waarmee niet één feed maar alle feeds verloren gaan. Bovendien struikelt die
   downloader over servers die gzip sturen zonder correcte `Content-Encoding`
   (vastgesteld bij piratenpartij.nl): de XML-parser krijgt dan ingepakte bytes
   en geeft `bozo=1` met nul items.

Daarom doen we het HTTP-verzoek zelf: met expliciete time-out, en met een
gzip-controle op de *inhoud* (magic bytes) in plaats van op de header — want
precies de servers die het misdoen, liegen in hun headers.

Downloader en parser zijn injecteerbaar en `feedparser` wordt lazy geïmporteerd,
zodat de tests op kale stdlib draaien zonder netwerk.
"""

import gzip
import time
import urllib.error
import urllib.request
import zlib

FETCH_OK = "ok"            # feed opgehaald, er zijn items
FETCH_LEEG = "leeg"        # feed opgehaald en geparsed, maar zonder items
FETCH_MISLUKT = "mislukt"  # feed niet op te halen of niet te parsen
FETCH_TIMEOUT = "timeout"  # server antwoordde niet binnen de tijdslimiet

FETCH_RETRIES = 1        # aantal herkansingen ná de eerste poging
FETCH_RETRY_DELAY = 2.0  # seconden pauze vóór een herkansing
FETCH_TIMEOUT_SECONDS = 15
MAX_ENTRIES = 50
USER_AGENT = "Mozilla/5.0"

GZIP_MAGIC = b"\x1f\x8b"
_ZLIB_GZIP_WBITS = 31  # zlib-vlag voor "verwacht een gzip-header"


class FetchResult:
    """Uitkomst van één feed-ophaalpoging.

    name    — feed-titel, of de URL als die niet te achterhalen was
    entries — de items (afgekapt op max_entries)
    status  — FETCH_OK | FETCH_LEEG | FETCH_MISLUKT | FETCH_TIMEOUT
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

    @property
    def failed(self):
        return self.status in (FETCH_MISLUKT, FETCH_TIMEOUT)

    def __repr__(self):
        return f"FetchResult({self.name!r}, {len(self.entries)} entries, {self.status})"


def _maybe_gunzip(raw):
    """Pakt uit als de inhoud met gzip-magic begint, ongeacht de header.

    urllib decomprimeert niet automatisch, dus dit moeten we zelf doen. Kijken
    naar de eerste twee bytes in plaats van naar `Content-Encoding` dekt ook de
    servers die gzip sturen zonder dat correct aan te kondigen.

    Twee trappen, in deze volgorde:

    1. `gzip.decompress()` — de correcte weg, die ook aaneengeschakelde
       gzip-leden volledig uitpakt.
    2. Redding via `zlib.decompressobj(31)` wanneer stap 1 weigert omdat er ná
       de gzip-stroom nog bytes staan. Python eist daar dat *alle* invoer uit
       gzip-leden bestaat, terwijl servers in het wild er rommel achter plakken
       (vastgesteld bij piratenpartij.nl: een caching-plugin voegt 220 bytes
       platte HTML toe). De decompressor pakt uit wat geldig is en laat de rest
       in `unused_data` achter.

    Lukt geen van beide, dan geven we de ruwe bytes terug en laat de XML-parser
    erover oordelen.
    """
    if not raw.startswith(GZIP_MAGIC):
        return raw
    try:
        return gzip.decompress(raw)
    except (OSError, EOFError):
        pass
    try:
        salvaged = zlib.decompressobj(_ZLIB_GZIP_WBITS).decompress(raw)
    except zlib.error:
        return raw
    return salvaged or raw


def _default_downloader(url, timeout):
    """Haalt de ruwe feed-bytes op met een expliciete tijdslimiet."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return _maybe_gunzip(raw)


def fetch_feed(
    url,
    *,
    retries=FETCH_RETRIES,
    delay=FETCH_RETRY_DELAY,
    timeout=FETCH_TIMEOUT_SECONDS,
    max_entries=MAX_ENTRIES,
    parser=None,
    downloader=None,
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
    if downloader is None:
        downloader = _default_downloader
    if sleep is None:
        sleep = time.sleep

    last_error = None
    timed_out = False

    for attempt in range(retries + 1):
        if attempt:
            sleep(delay)

        try:
            raw = downloader(url, timeout)
        except TimeoutError as exc:
            last_error, timed_out = exc, True
            continue
        except Exception as exc:  # netwerk, DNS, TLS, HTTP-fout, kapotte redirect
            last_error = exc
            if isinstance(exc, urllib.error.URLError) and isinstance(
                getattr(exc, "reason", None), TimeoutError
            ):
                timed_out = True
            continue

        try:
            parsed = parser(raw)
        except Exception as exc:
            last_error = exc
            continue

        feed = getattr(parsed, "feed", None) or {}
        title = feed.get("title") if hasattr(feed, "get") else None
        entries = list(getattr(parsed, "entries", None) or [])

        if entries:
            return FetchResult(title or url, entries[:max_entries], FETCH_OK, attempt + 1)
        if title:
            return FetchResult(title, [], FETCH_LEEG, attempt + 1)

    status = FETCH_TIMEOUT if timed_out else FETCH_MISLUKT
    return FetchResult(url, [], status, retries + 1, last_error)
