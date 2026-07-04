#!/usr/bin/env python3
"""
fetch-fulltext.py — Haal de volledige tekst van een Zotero-item op en sla op naar bestand.

Gebruik:
    python3 .claude/fetch-fulltext.py ITEMKEY inbox/bestand.txt

De volledige tekst wordt naar het opgegeven bestand geschreven.
Alleen lengte en status worden geprint — nooit de inhoud zelf.
"""

import html as html_module
import json
import os
import re
import sys
from pathlib import Path

# Laad vault .env als ZOTERO_API_KEY nog niet in de omgeving staat
if not os.environ.get("ZOTERO_API_KEY"):
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)


def main():
    if len(sys.argv) != 3:
        print("Gebruik: fetch-fulltext.py ITEMKEY doelbestand.txt", file=sys.stderr)
        sys.exit(1)

    item_key = sys.argv[1]
    output_path = sys.argv[2]

    # Gebruik web API als ZOTERO_API_KEY beschikbaar is, anders lokale API
    if not os.environ.get("ZOTERO_API_KEY"):
        os.environ["ZOTERO_LOCAL"] = "true"

    from zotero_mcp.server import get_zotero_client

    client = get_zotero_client()

    # Haal children op om attachment key te vinden
    children = client.children(item_key)
    attachments = [
        c for c in children
        if c["data"].get("itemType") == "attachment"
        and c["data"].get("contentType") in ("application/pdf", "text/html")
    ]

    if not attachments:
        # Probeer ook snapshot en andere types
        attachments = [
            c for c in children
            if c["data"].get("itemType") == "attachment"
            and c["data"].get("contentType") not in ("", None)
        ]

    if not attachments:
        # Fallback: zoek naar transcript-note (_transcript tag).
        # Web API heeft een bekende bug waarbij notes niet opvraagbaar zijn via GET,
        # ook al zijn ze aangemaakt. Gebruik lokale Zotero API (port 23119) als fallback.
        def _find_transcript_notes(items):
            return [
                c for c in items
                if c["data"].get("itemType") == "note"
                and any(t["tag"] == "_transcript" for t in c["data"].get("tags", []))
            ]

        transcript_notes = _find_transcript_notes(children)

        if not transcript_notes:
            # Fallback naar lokale Zotero API
            try:
                import urllib.request as _ureq
                _local_url = f"http://localhost:23119/api/users/0/items/{item_key}/children"
                with _ureq.urlopen(_local_url, timeout=5) as _r:
                    _local_children = json.loads(_r.read())
                transcript_notes = _find_transcript_notes(_local_children)
                if transcript_notes:
                    print(f"  Transcript-note gevonden via lokale Zotero API", file=sys.stderr)
            except Exception as _e:
                print(f"  Lokale Zotero API niet bereikbaar: {_e}", file=sys.stderr)
        if transcript_notes:
            note_html = transcript_notes[0]["data"].get("note", "")
            # Strip HTML-tags en decode HTML-entiteiten
            text = re.sub(r"<[^>]+>", " ", note_html)
            content = html_module.unescape(text).strip()
            content = re.sub(r" {2,}", " ", content)
            if content:
                os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"Opgeslagen: {output_path} ({len(content):,} tekens, type: transcript note)")
                return
        print(f"Geen bijlage of transcript-note gevonden voor item {item_key}", file=sys.stderr)
        sys.exit(1)

    attachment_key = attachments[0]["key"]
    attachment_type = attachments[0]["data"].get("contentType", "?")
    attachment_link_mode = attachments[0]["data"].get("linkMode", "")
    attachment_path = attachments[0]["data"].get("path", "")

    # Haal volledige tekst op
    content = ""
    try:
        result = client.fulltext_item(attachment_key)
        content = result.get("content", "")
    except Exception as _ft_err:
        pass  # zie fallback hieronder

    # Fallback voor linked_file HTML-snapshots: het bestand staat op het opgegeven pad
    # (bijv. ~/Zotero/Snapshots/), niet in ~/Zotero/storage/{attachment_key}/.
    if not content and attachment_type == "text/html" and attachment_link_mode == "linked_file" and attachment_path:
        linked = Path(attachment_path)
        if linked.exists():
            raw_html = linked.read_text(encoding="utf-8", errors="replace")
            text = re.sub(r"<[^>]+>", " ", raw_html)
            content = re.sub(r"\s+", " ", html_module.unescape(text)).strip()
            print(f"  Linked snapshot gelezen: {linked.name} ({len(content):,} tekens)", file=sys.stderr)

    # Fallback voor linked_file text/plain (transcripten): lees direct van het opgegeven pad.
    if not content and attachment_type == "text/plain" and attachment_link_mode == "linked_file" and attachment_path:
        linked = Path(attachment_path)
        if linked.exists():
            content = linked.read_text(encoding="utf-8", errors="replace")
            print(f"  Linked transcript gelezen: {linked.name} ({len(content):,} tekens)", file=sys.stderr)

    # Fallback voor imported_file HTML-snapshots: lees het bestand uit ~/Zotero/storage/{attachment_key}/.
    if not content and attachment_type == "text/html":
        storage_dir = Path.home() / "Zotero" / "storage" / attachment_key
        html_files = sorted(storage_dir.glob("*.html")) if storage_dir.exists() else []
        if html_files:
            raw_html = html_files[0].read_text(encoding="utf-8", errors="replace")
            text = re.sub(r"<[^>]+>", " ", raw_html)
            content = re.sub(r"\s+", " ", html_module.unescape(text)).strip()
            print(f"  Snapshot gelezen uit storage: {html_files[0].name} ({len(content):,} tekens)",
                  file=sys.stderr)

    # Fallback voor PDF: pyzotero gebruikt het web-gebruiker-ID ook in lokale modus,
    # waardoor /users/24775/... 404 geeft. Direct via de lokale REST API met /users/0/.
    if not content and attachment_type == "application/pdf":
        try:
            import urllib.request as _ureq
            _ft_url = f"http://localhost:23119/api/users/0/items/{attachment_key}/fulltext"
            with _ureq.urlopen(_ft_url, timeout=10) as _r:
                _ft_data = json.loads(_r.read())
                content = _ft_data.get("content", "")
                if content:
                    print(f"  PDF-fulltext via lokale API ({len(content):,} tekens)", file=sys.stderr)
        except Exception as _e:
            print(f"  Lokale fulltext-API niet bereikbaar voor PDF: {_e}", file=sys.stderr)

    if not content:
        print(f"Geen tekstinhoud gevonden in bijlage {attachment_key} (type: {attachment_type})",
              file=sys.stderr)
        sys.exit(1)

    # Schrijf naar doelbestand
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Opgeslagen: {output_path} ({len(content):,} tekens, type: {attachment_type})")


if __name__ == "__main__":
    main()
