#!/usr/bin/env python3
"""
zotero-remove-from-inbox.py — Verwijder een item uit de Zotero _inbox collectie.

Gebruik:
    python3 .claude/zotero-remove-from-inbox.py ITEMKEY

Vereist ZOTERO_API_KEY, ZOTERO_LIBRARY_ID en ZOTERO_LIBRARY_TYPE in de omgeving.
"""

import os
import sys
from pathlib import Path

# Laad vault .env als ZOTERO_API_KEY nog niet in de omgeving staat
if not os.environ.get("ZOTERO_API_KEY"):
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)

INBOX_COLLECTION_KEY = "N4MP46Y5"


def main():
    if len(sys.argv) != 2:
        print("Gebruik: zotero-remove-from-inbox.py ITEMKEY", file=sys.stderr)
        sys.exit(1)

    item_key = sys.argv[1]

    api_key = os.environ.get("ZOTERO_API_KEY")
    if not api_key:
        print("ZOTERO_API_KEY niet ingesteld.", file=sys.stderr)
        sys.exit(1)

    from zotero_mcp.server import get_zotero_client

    client = get_zotero_client()

    item = client.item(item_key)
    collections = item["data"].get("collections", [])

    if INBOX_COLLECTION_KEY not in collections:
        print(f"Item {item_key} staat niet in _inbox, niets te doen.")
        return

    item["data"]["collections"] = [c for c in collections if c != INBOX_COLLECTION_KEY]
    result = client.update_item(item)

    if result:
        print(f"Item {item_key} verwijderd uit _inbox.")
    else:
        print(f"Verwijderen mislukt voor item {item_key}.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
