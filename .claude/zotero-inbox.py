#!/usr/bin/env python3
"""
zotero-inbox.py — Haal alle items op uit de Zotero _inbox collectie
====================================================================
Maakt verbinding met de lokale Zotero API (localhost:23119) en toont
alle content-items (geen bijlagen) in de _inbox collectie, inclusief
title, auteur, jaar, type en tags.

Gebruik:
    python3 zotero-inbox.py              # toon alle items
    python3 zotero-inbox.py --json       # output als JSON (voor scripts)
    python3 zotero-inbox.py --key XXXX   # toon details van één item
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any

# ── Configuratie ──────────────────────────────────────────────────────────────

ZOTERO_API  = "http://localhost:23119/api/users/0"
INBOX_NAME  = "_inbox"
PAGE_SIZE   = 100

# Bijlage-types die we overslaan
SKIP_TYPES = {"attachment", "note"}

# ── Hulpfuncties ──────────────────────────────────────────────────────────────

def api_get(path: str) -> Any:
    """Haalt JSON op van de lokale Zotero API."""
    url = f"{ZOTERO_API}{path}"
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return json.loads(r.read())
    except urllib.error.URLError as e:
        print(f"❌  Zotero API niet bereikbaar: {e}")
        print("    Zorg dat Zotero open is en de lokale API actief is.")
        sys.exit(1)


def find_inbox_key() -> str:
    """Zoekt de collectie-key van _inbox."""
    cols = api_get("/collections?limit=100")
    for col in cols:
        if col["data"]["name"] == INBOX_NAME:
            return col["key"]
    print(f"❌  Collectie '{INBOX_NAME}' niet gevonden in Zotero.")
    print("    Controleer of de collectie bestaat en de naam klopt.")
    sys.exit(1)


def fetch_all_items(collection_key: str) -> list[dict]:
    """Haalt alle items op uit een collectie, gepagineerd."""
    items = []
    start = 0
    while True:
        batch = api_get(f"/collections/{collection_key}/items?limit={PAGE_SIZE}&start={start}&format=json")
        if not batch:
            break
        items.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return items


def extract_meta(item: dict) -> dict:
    """Extraheert relevante metadata uit een Zotero item."""
    d = item["data"]
    creators = d.get("creators", [])
    first_author = ""
    if creators:
        c = creators[0]
        first_author = c.get("lastName") or c.get("name") or ""
    return {
        "key":    item["key"],
        "title":  d.get("title", "(geen titel)"),
        "type":   d.get("itemType", ""),
        "author": first_author,
        "year":   (d.get("date") or d.get("year") or "")[:4],
        "tags":   [t["tag"] for t in d.get("tags", [])],
        "url":    d.get("url", ""),
    }


def format_tags(tags: list[str]) -> str:
    if not tags:
        return ""
    return "  [" + "  ".join(tags) + "]"


# ── Hoofdprogramma ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Zotero _inbox viewer")
    parser.add_argument("--json", action="store_true", help="Output als JSON")
    parser.add_argument("--key", metavar="KEY", help="Toon details van één item")
    args = parser.parse_args()

    inbox_key = find_inbox_key()
    raw_items = fetch_all_items(inbox_key)

    # Filter bijlagen en notes
    content = [extract_meta(it) for it in raw_items
               if it["data"].get("itemType") not in SKIP_TYPES]

    if args.key:
        match = next((it for it in content if it["key"] == args.key), None)
        if match:
            print(json.dumps(match, indent=2, ensure_ascii=False))
        else:
            print(f"❌  Item {args.key} niet gevonden (of is een bijlage).")
        return

    if args.json:
        print(json.dumps(content, indent=2, ensure_ascii=False))
        return

    # ── Leesbare output ───────────────────────────────────────────────────────
    print(f"\n📥  Zotero _inbox — {len(content)} items\n")
    print(f"{'─' * 70}")

    for it in content:
        title  = it["title"][:65] + ("…" if len(it["title"]) > 65 else "")
        byline = " · ".join(filter(None, [it["author"], it["year"]]))
        tags   = format_tags(it["tags"])
        itype  = it["type"]

        print(f"[{it['key']}]  {title}")
        meta = " · ".join(filter(None, [itype, byline]))
        print(f"          {meta}{tags}")
        print()

    print(f"{'─' * 70}")
    print(f"Totaal: {len(content)} content-items  "
          f"(bijlagen niet meegeteld)\n")


if __name__ == "__main__":
    main()
