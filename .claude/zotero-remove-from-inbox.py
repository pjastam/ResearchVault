#!/usr/bin/env python3
"""
zotero-remove-from-inbox.py — Verwijder een item uit de Zotero _inbox collectie.

Gebruik:
    python3 .claude/zotero-remove-from-inbox.py ITEMKEY

Modus via ZOTERO_ACCESS (default: local — vereist Zotero desktop).
"""

import json
import sys

from zotero_api import zotero_request

INBOX_COLLECTION_KEY = "N4MP46Y5"


def main():
    if len(sys.argv) != 2:
        print("Gebruik: zotero-remove-from-inbox.py ITEMKEY", file=sys.stderr)
        sys.exit(1)

    item_key = sys.argv[1]

    raw         = json.loads(zotero_request(f"/items/{item_key}"))
    version     = raw["data"]["version"]
    collections = raw["data"].get("collections", [])

    if INBOX_COLLECTION_KEY not in collections:
        print(f"Item {item_key} staat niet in _inbox, niets te doen.")
        return

    new_collections = [c for c in collections if c != INBOX_COLLECTION_KEY]
    payload = json.dumps({"collections": new_collections}).encode()
    zotero_request(
        f"/items/{item_key}", method="PATCH", data=payload,
        extra_headers={
            "Content-Type":                "application/json",
            "If-Unmodified-Since-Version": str(version),
        },
    )
    print(f"Item {item_key} verwijderd uit _inbox.")


if __name__ == "__main__":
    main()
