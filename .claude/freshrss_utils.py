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
import urllib.parse
import urllib.request
from pathlib import Path


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
                if line.startswith(f"export {var}="):
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
    base_url: str, auth: str, stream_id: str, n: int = 1000
) -> dict[str, str]:
    """
    Haal items op uit een GReader-stream.
    Geeft {item_url: gitem_id} terug; leeg dict bij mislukking.

    Veelgebruikte stream_id waarden:
      user/-/state/com.google/reading-list  — alle ongelezen items
      user/-/state/com.google/starred       — gestefte items
      user/-/state/com.google/read          — gelezen items
    """
    url = (
        f"{base_url}/greader.php/reader/api/0/stream/contents/"
        f"{urllib.parse.quote(stream_id, safe='/-')}"
        f"?output=json&n={n}"
    )
    try:
        with urllib.request.urlopen(
            urllib.request.Request(
                url, headers={"Authorization": f"GoogleLogin auth={auth}"}
            ),
            timeout=30,
        ) as resp:
            data = json.loads(resp.read())
        result = {}
        for item in data.get("items", []):
            for alt in item.get("alternate", []):
                if alt.get("href"):
                    result[alt["href"]] = item["id"]
                    break
        return result
    except Exception:
        return {}


def freshrss_starred_urls(base_url: str, auth: str) -> set[str]:
    """Geeft de set van URLs van gestefte items in FreshRSS."""
    return set(
        freshrss_fetch_stream(base_url, auth, "user/-/state/com.google/starred")
    )


def freshrss_read_urls(base_url: str, auth: str) -> set[str]:
    """Geeft de set van URLs van gelezen items in FreshRSS."""
    return set(
        freshrss_fetch_stream(base_url, auth, "user/-/state/com.google/read")
    )


def freshrss_star_by_urls(
    base_url: str, auth: str, post_token: str, urls: list[str]
) -> int:
    """
    Ster FreshRSS-items die overeenkomen met de opgegeven URLs.
    Haalt de reading-list op om URL→item_id te resolven, sterf dan de matches.
    Geeft het aantal succesvol gesterfde items terug.
    """
    stream_map = freshrss_fetch_stream(
        base_url, auth, "user/-/state/com.google/reading-list"
    )
    to_star = [stream_map[u] for u in urls if u in stream_map]
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
