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
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

STREAM_OK = "ok"            # stream opgehaald, er zijn items
STREAM_LEEG = "leeg"        # stream opgehaald en geparsed, maar zonder items
STREAM_MISLUKT = "mislukt"  # niet op te halen of niet te parsen
STREAM_TIMEOUT = "timeout"  # server antwoordde niet binnen de tijdslimiet

STREAM_TIMEOUT_SECONDS = 30


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

    __slots__ = ("items", "status", "error")

    def __init__(self, items, status, error=None):
        self.items = items
        self.status = status
        self.error = error

    @property
    def ok(self):
        return self.status == STREAM_OK

    @property
    def failed(self):
        return self.status in (STREAM_MISLUKT, STREAM_TIMEOUT)

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
    base_url: str, auth: str, stream_id: str, n: int = 1000, opener=None
) -> StreamResult:
    """
    Haal items op uit een GReader-stream.

    Geeft een StreamResult met {item_url: gitem_id} en een expliciete status, zodat
    "deze stream is leeg" te onderscheiden is van "de fetch is mislukt". De opener
    is injecteerbaar zodat de tests op kale stdlib draaien, zonder netwerk.

    Veelgebruikte stream_id waarden:
      user/-/state/com.google/reading-list  — alle ongelezen items
      user/-/state/com.google/starred       — gestefte items
    """
    url = (
        f"{base_url}/greader.php/reader/api/0/stream/contents/"
        f"{urllib.parse.quote(stream_id, safe='/-')}"
        f"?output=json&n={n}"
    )
    data, mislukking = _fetch_json(url, auth, opener)
    if mislukking is not None:
        return mislukking

    result = {}
    for item in data.get("items", []):
        href = _first_href(item)
        if href:
            result[href] = item["id"]
    return StreamResult(result, STREAM_OK if result else STREAM_LEEG)


def freshrss_starred_stream(base_url: str, auth: str, opener=None) -> StreamResult:
    """Gestefde items in FreshRSS, als StreamResult."""
    return freshrss_fetch_stream(
        base_url, auth, "user/-/state/com.google/starred", opener=opener
    )


def freshrss_read_stream(base_url: str, auth: str, opener=None) -> StreamResult:
    """Gelezen items in FreshRSS, als StreamResult."""
    return freshrss_fetch_stream(
        base_url, auth, "user/-/state/com.google/read", opener=opener
    )


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
