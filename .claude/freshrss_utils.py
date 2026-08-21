"""
freshrss_utils.py — FreshRSS GReader API helpers
=================================================
Gedeelde functies voor authenticatie en item-beheer via het GReader-protocol
van FreshRSS. Gebruikt door feedreader-score.py (auto-sterren) en
feedreader-learn.py (leerloop: gestefd = positief, gelezen = negatief).

Benodigde variabelen in ~/.bin/.researchvault-env of als omgevingsvariabele:
  FRESHRSS_HA_URL         — basis-URL van FreshRSS (bijv. http://192.168.x.x:PORT)
  FRESHRSS_USER           — gebruikersnaam
  FRESHRSS_API_WACHTWOORD — API-wachtwoord (ingesteld via FreshRSS Profiel → API-wachtwoord)
"""

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

STREAM_OK = "ok"              # stream volledig opgehaald, er zijn items
STREAM_LEEG = "leeg"          # stream volledig opgehaald, maar zonder items
STREAM_MISLUKT = "mislukt"    # niet op te halen of niet te parsen
STREAM_TIMEOUT = "timeout"    # server antwoordde niet binnen de tijdslimiet
STREAM_AFGEKAPT = "afgekapt"  # veiligheidsgrens geraakt; er is méér dan we hebben

STREAM_TIMEOUT_SECONDS = 30

# Paginagrootte per verzoek. GReader honoreert `n` letterlijk, dus zonder
# doorlezen krijg je precies zoveel items als je vraagt — en dat ziet eruit als
# een compleet antwoord. Gemeten 19 aug 2026: n=1000 gaf 999 gesterde items
# terwijl er 1.797 waren, en 57 van de 218 gelezen items.
STREAM_PAGE_SIZE = 1000

# Bovengrens over alle pagina's samen. Puur een noodrem tegen een server die
# oneindig blijft doorpagineren; bij ~2.500 items is er ruimte zat. Wordt hij
# geraakt, dan is de uitkomst STREAM_AFGEKAPT — nooit stilzwijgend "ok".
MAX_STREAM_ITEMS = 50_000

READING_LIST = "user/-/state/com.google/reading-list"
READ_STATE = "user/-/state/com.google/read"


_GEHEIM_PATRONEN = (
    # GReader-auth uit ClientLogin: "gebruiker/<40 hex>". Dit is de vorm die op
    # 21 aug 2026 in een urllib-foutmelding belandde en zo in een LLM-context kwam.
    (re.compile(r"\b[\w.\-]+/[0-9a-fA-F]{16,}\b"), "<auth-token verwijderd>"),
    # query- en formuliersleutels die een geheim dragen
    (re.compile(r"\b(auth|token|Passwd|password|wachtwoord|api_key|apikey)=[^&\s'\"]+",
                re.IGNORECASE), r"\1=<verwijderd>"),
    # losse lange hexreeksen (hashes, tokens zonder sleutelnaam)
    (re.compile(r"\b[0-9a-fA-F]{32,}\b"), "<verwijderd>"),
)


def maskeer_geheimen(tekst: str) -> str:
    """Haalt tokens en wachtwoorden uit een tekst, bedoeld voor foutmeldingen.

    Aanleiding: een verkeerd samengestelde URL liet `urllib` de melding
    "unknown url type: 'gebruiker/<40 hex>/reader/api/...'" werpen — mét de
    GReader-auth-token erin. Het env-bestand is gitignored, curl-aanroepen sturen
    hun uitvoer naar /dev/null en de credential-sleutels worden gefilterd, maar geen
    van die maatregelen dekt een exceptie die zijn invoer terugecho't. Wie geheimen
    uit logs en tool-output wil houden, moet dus ook het foutpad afdekken.

    Puur en alleen stdlib, dus testbaar zonder netwerk.
    """
    if not tekst:
        return tekst
    for patroon, vervanging in _GEHEIM_PATRONEN:
        tekst = patroon.sub(vervanging, tekst)
    return tekst


class StreamResult:
    """Uitkomst van één GReader-stream-ophaalpoging.

    Bestaat omdat `except Exception: return {}` HTTP 400, netwerkfouten, verlopen
    auth en een echt lege stream ononderscheidbaar maakte. Signaal 3 uit de
    leerloop (NNW-gelezen) stond daardoor maandenlang droog zonder dat iets het
    meldde: FreshRSS antwoordt op de read-stream met 400, en dat werd een lege set.

    Het gevaar reikt verder dan dat ene signaal. Valt de *starred*-fetch één dag
    uit, dan verdwijnt het leeuwendeel van het positieve signaal en wordt alles die
    run timeout-negatief — zonder alarm. Zelfde vorm als FetchResult in
    feedreader_fetch.py, om dezelfde reden.
    """

    __slots__ = ("items", "status", "error", "_exc")

    def __init__(self, items, status, error=None):
        self.items = items
        self.status = status
        # `error` is bewust een **gemaskeerde tekst**, geen exceptie: dit veld wordt
        # gelogd en in diagnoses afgedrukt, en een exceptie kan de auth-token in zijn
        # boodschap dragen (zie maskeer_geheimen). De rauwe exceptie blijft in `_exc`
        # voor lokaal debuggen — druk die niet af.
        self._exc = error
        self.error = maskeer_geheimen(str(error)) if error is not None else None

    @property
    def ok(self):
        return self.status == STREAM_OK

    @property
    def failed(self):
        # STREAM_AFGEKAPT telt als mislukt: de data is onvolledig, en downstream
        # labelt er negatieven mee. Een half gelezen stream is niet te
        # onderscheiden van een hele, dus hij mag niet als bruikbaar gelden.
        return self.status in (STREAM_MISLUKT, STREAM_TIMEOUT, STREAM_AFGEKAPT)

    def __repr__(self):
        return f"StreamResult({len(self.items)} items, {self.status})"


def _authed_opener(auth):
    """Standaard-opener: GET met GoogleLogin-header en expliciete tijdslimiet."""

    def opener(url, timeout):
        req = urllib.request.Request(
            url, headers={"Authorization": f"GoogleLogin auth={auth}"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()

    return opener


def _paginate(base_url, auth, stream_id, page_size, max_items, opener, verzamel):
    """Leest een GReader-stream volledig uit, pagina voor pagina.

    GReader levert per antwoord een `continuation`-token; met `&c=<token>` haal
    je het volgende blok. Zonder token is de stroom op.

    `verzamel(item, result)` bepaalt wat er per item bewaard wordt — zo delen de
    gesterde stream en de gelezen stream dezelfde pagineerlus terwijl ze
    verschillende filters houden.

    Geeft een StreamResult. Een storing op een látere pagina levert
    STREAM_MISLUKT op en géén gedeeltelijke data: downstream labelt er negatieven
    mee, en een half gelezen stream is niet te onderscheiden van een hele.
    """
    stream_pad = urllib.parse.quote(stream_id, safe="/-")
    result = {}
    continuation = None
    gezien = 0

    while True:
        url = (
            f"{base_url}/greader.php/reader/api/0/stream/contents/"
            f"{stream_pad}?output=json&n={page_size}"
        )
        if continuation:
            url += "&c=" + urllib.parse.quote(continuation)

        data, mislukking = _fetch_json(url, auth, opener)
        if mislukking is not None:
            return mislukking

        items = data.get("items", [])
        gezien += len(items)
        for item in items:
            verzamel(item, result)

        continuation = data.get("continuation")
        if not continuation or not items:
            break
        if gezien >= max_items:
            return StreamResult(result, STREAM_AFGEKAPT)

    return StreamResult(result, STREAM_OK if result else STREAM_LEEG)


def _fetch_json(url, auth, opener):
    """Haalt JSON op en vertaalt elke storing naar een StreamResult-status.

    Geeft (data, None) bij succes en (None, StreamResult) bij mislukking, zodat de
    aanroeper zelf bepaalt hoe hij de items uit de data haalt.
    """
    if opener is None:
        opener = _authed_opener(auth)
    try:
        raw = opener(url, STREAM_TIMEOUT_SECONDS)
    except TimeoutError as exc:
        return None, StreamResult({}, STREAM_TIMEOUT, exc)
    except Exception as exc:
        if isinstance(exc, urllib.error.URLError) and isinstance(
            getattr(exc, "reason", None), TimeoutError
        ):
            return None, StreamResult({}, STREAM_TIMEOUT, exc)
        return None, StreamResult({}, STREAM_MISLUKT, exc)
    try:
        return json.loads(raw), None
    except Exception as exc:
        return None, StreamResult({}, STREAM_MISLUKT, exc)


def _first_href(item):
    """De URL van een GReader-item, of None."""
    for alt in item.get("alternate", []):
        if alt.get("href"):
            return alt["href"]
    return None


def load_freshrss_creds() -> dict:
    """
    Laad FreshRSS GReader-gegevens uit omgeving of ~/.bin/.researchvault-env.
    Geeft dict terug met sleutels 'url', 'user', 'password'.
    """
    creds = {
        "url":      os.environ.get("FRESHRSS_HA_URL", ""),
        "user":     os.environ.get("FRESHRSS_USER", ""),
        "password": os.environ.get("FRESHRSS_API_WACHTWOORD", ""),
    }
    if all(creds.values()):
        return creds
    env_file = Path.home() / "bin" / ".researchvault-env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            for key, var in [
                ("url",      "FRESHRSS_HA_URL"),
                ("user",     "FRESHRSS_USER"),
                ("password", "FRESHRSS_API_WACHTWOORD"),
            ]:
                prefix = f"{var}="
                if line.startswith(prefix) or line.startswith(f"export {prefix}"):
                    creds[key] = line.split("=", 1)[1].strip().strip('"').strip("'")
    return creds


def freshrss_auth(creds: dict) -> tuple[str, str]:
    """
    Authenticeer bij FreshRSS GReader API.
    Geeft (auth_token, post_token) terug; beide lege strings bij mislukking.
    """
    login_data = urllib.parse.urlencode(
        {"Email": creds["user"], "Passwd": creds["password"]}
    ).encode()
    try:
        with urllib.request.urlopen(
            urllib.request.Request(
                f"{creds['url']}/greader.php/accounts/ClientLogin",
                data=login_data,
            ),
            timeout=10,
        ) as resp:
            body = resp.read().decode()
        auth = next(
            (line[5:] for line in body.splitlines() if line.startswith("Auth=")), ""
        )
        if not auth:
            return "", ""
        with urllib.request.urlopen(
            urllib.request.Request(
                f"{creds['url']}/greader.php/reader/api/0/token",
                headers={"Authorization": f"GoogleLogin auth={auth}"},
            ),
            timeout=10,
        ) as resp:
            post_token = resp.read().decode().strip()
        return auth, post_token
    except Exception:
        return "", ""


def freshrss_fetch_stream(
    base_url: str, auth: str, stream_id: str,
    page_size: int = STREAM_PAGE_SIZE, max_items: int = MAX_STREAM_ITEMS,
    opener=None,
) -> StreamResult:
    """
    Haal een GReader-stream volledig op, met paginering.

    Geeft een StreamResult met {item_url: gitem_id} en een expliciete status, zodat
    "deze stream is leeg" te onderscheiden is van "de fetch is mislukt" én van
    "we hebben niet alles". De opener is injecteerbaar zodat de tests op kale
    stdlib draaien, zonder netwerk.

    Veelgebruikte stream_id waarden:
      user/-/state/com.google/reading-list  — alle items, met hun read-state
      user/-/state/com.google/starred       — gestefte items
    """
    def verzamel(item, result):
        href = _first_href(item)
        if href:
            result[href] = item["id"]

    return _paginate(base_url, auth, stream_id, page_size, max_items,
                     opener, verzamel)


def freshrss_starred_stream(base_url: str, auth: str, opener=None) -> StreamResult:
    """Gestefde items in FreshRSS, als StreamResult (volledig, gepagineerd)."""
    return freshrss_fetch_stream(
        base_url, auth, "user/-/state/com.google/starred", opener=opener
    )


def freshrss_read_stream(base_url: str, auth: str,
                         page_size: int = STREAM_PAGE_SIZE,
                         max_items: int = MAX_STREAM_ITEMS,
                         opener=None) -> StreamResult:
    """Gelezen items in FreshRSS, als StreamResult.

    Afgeleid uit de reading-list in plaats van uit een eigen read-stream. De
    directe route `stream/contents/user/-/state/com.google/read` geeft bij FreshRSS
    HTTP 400 — vastgesteld 17 aug 2026 en live gereproduceerd op 19 aug. Dat werd
    door de oude `except Exception: return {}` een lege set, ononderscheidbaar van
    "je hebt niets gelezen", waardoor signaal 3 van de leerloop maandenlang droog
    stond.

    De reading-list levert dezelfde items mét hun `categories`, en daar staat de
    read-state in. Eén call, en de URL zit er al bij — het alternatief
    (`stream/items/ids?s=…/read`) geeft alleen ID's en zou een tweede ronde vergen.
    """
    def verzamel(item, result):
        if READ_STATE not in item.get("categories", []):
            return
        href = _first_href(item)
        if href:
            result[href] = item["id"]

    return _paginate(base_url, auth, READING_LIST, page_size, max_items,
                     opener, verzamel)


def freshrss_star_by_urls(
    base_url: str, auth: str, post_token: str, urls: list[str]
) -> int:
    """
    Ster FreshRSS-items die overeenkomen met de opgegeven URLs.
    Haalt de reading-list op om URL→item_id te resolven, sterf dan de matches.
    Geeft het aantal succesvol gesterfde items terug.
    """
    stream = freshrss_fetch_stream(
        base_url, auth, "user/-/state/com.google/reading-list"
    )
    if stream.failed:
        # Onderscheid bewaren: -1 is "de lookup mislukte", 0 is "geen van deze
        # URLs stond in de reading-list". Zonder dat onderscheid ziet een storing
        # eruit als een rustige dag — de fout die deze hele reparatie aanleiding gaf.
        return -1
    to_star = [stream.items[u] for u in urls if u in stream.items]
    if not to_star:
        return 0
    starred = 0
    for item_id in to_star:
        body = urllib.parse.urlencode({
            "i": item_id,
            "a": "user/-/state/com.google/starred",
            "T": post_token,
        }).encode()
        try:
            with urllib.request.urlopen(
                urllib.request.Request(
                    f"{base_url}/greader.php/reader/api/0/edit-tag",
                    data=body,
                    headers={"Authorization": f"GoogleLogin auth={auth}"},
                ),
                timeout=10,
            ) as resp:
                if resp.status == 200:
                    starred += 1
        except Exception:
            pass
    return starred
