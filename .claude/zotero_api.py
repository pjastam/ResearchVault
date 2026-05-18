#!/usr/bin/env python3
"""
zotero_api.py — Unified Zotero API client with mode selection.

Modus via omgevingsvariabele ZOTERO_ACCESS:
  local  (default): localhost:23119 (vereist Zotero desktop, geen authenticatie nodig)
  auto:             start Zotero als het niet draait, dan local API; exit 1 na 30s time-out
  web:              api.zotero.org (headless-safe, vereist ZOTERO_API_KEY)

Publieke API: zotero_request(path, method, data, extra_headers) -> bytes
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Laad vault .env als ZOTERO_API_KEY nog niet in de omgeving staat
if not os.environ.get("ZOTERO_API_KEY"):
    _env_file = Path(__file__).parent.parent / ".env"
    if _env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(_env_file)

_MODE       = os.environ.get("ZOTERO_ACCESS", "local")
_API_KEY    = os.environ.get("ZOTERO_API_KEY", "")
_LIBRARY_ID = os.environ.get("ZOTERO_LIBRARY_ID", "24775")
_UA         = "Mozilla/5.0 (Macintosh) zotero-api/1.0 (mailto:piet@pietstam.nl)"

_LOCAL_BASE = "http://localhost:23119/api/users/0"
_WEB_BASE   = f"https://api.zotero.org/users/{_LIBRARY_ID}"

# Cache: voorkomen dat de beschikbaarheidscheck per aanroep herhaald wordt
_LOCAL_READY = False


def _check_local() -> bool:
    try:
        with urllib.request.urlopen(
            f"{_LOCAL_BASE}/collections?limit=1",
            timeout=3,
        ) as r:
            r.read()
            return True
    except Exception:
        return False


def _ensure_zotero_running() -> None:
    """Start Zotero als het niet draait; wacht max 30s. Stopt script bij mislukking."""
    if _check_local():
        return
    print("INFO: Zotero niet actief — wordt gestart...", file=sys.stderr)
    subprocess.Popen(["/usr/bin/open", "-a", "Zotero"])
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        time.sleep(2)
        if _check_local():
            print("INFO: Zotero is gereed.", file=sys.stderr)
            return
    print("FOUT: Zotero niet bereikbaar na 60s — script afgebroken.", file=sys.stderr)
    sys.exit(1)


def zotero_request(
    path: str,
    method: str = "GET",
    data: bytes | None = None,
    extra_headers: dict | None = None,
) -> bytes:
    """
    Stuurt een verzoek naar de Zotero API (local of web) op basis van ZOTERO_ACCESS.

    path: relatief t.o.v. users/{id}/, bijv. "/items/ABCD1234"
    Retourneert ruwe response-bytes. Gooit Exception bij HTTP-fouten.
    """
    global _LOCAL_READY

    if _MODE in ("local", "auto"):
        if not _LOCAL_READY:
            if _MODE == "auto":
                _ensure_zotero_running()
            elif not _check_local():
                print(
                    "FOUT: Zotero lokale API niet bereikbaar (localhost:23119). "
                    "Start Zotero of stel ZOTERO_ACCESS=web in.",
                    file=sys.stderr,
                )
                sys.exit(1)
            _LOCAL_READY = True
        base_url = _LOCAL_BASE
        headers  = {}

    else:  # web
        if not _API_KEY:
            print(
                "FOUT: ZOTERO_API_KEY niet ingesteld (vereist voor ZOTERO_ACCESS=web).",
                file=sys.stderr,
            )
            sys.exit(1)
        base_url = _WEB_BASE
        headers  = {
            "Zotero-API-Key":     _API_KEY,
            "Zotero-API-Version": "3",
            "User-Agent":         _UA,
        }

    if extra_headers:
        headers.update(extra_headers)

    req = urllib.request.Request(
        f"{base_url}{path}", data=data, headers=headers, method=method
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                wait = int(e.headers.get("Retry-After", "30"))
                print(f"  429 rate limit, wacht {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            body = e.read().decode("utf-8", errors="replace")
            raise Exception(f"HTTP {e.code} {e.reason}: {body[:300]}")
    raise Exception("Max retries bereikt")
