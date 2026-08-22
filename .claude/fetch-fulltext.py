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


def _naive_html_to_text(raw_html: str) -> str:
    """Strip álle tags → tekst (oud gedrag). Fallback als trafilatura niets vindt."""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    return re.sub(r"\s+", " ", html_module.unescape(text)).strip()


# Gelijk aan MIN_INHOUD_WOORDEN in build-zotero-bundle.py: onder deze grens wordt de
# bundle daar afgewezen. Een extractie die er niet overheen komt is dus per definitie
# onbruikbaar, en er valt niets te verliezen door het met de naïeve strip te proberen.
MIN_ARTIKEL_WOORDEN = 300


def extract_article_text(raw_html: str, url: str = "") -> str:
    """Haal de hoofd-artikeltekst uit snapshot-HTML — nav/ads/comments/boilerplate eruit.

    Volledige-pagina-snapshots (vooral van sites als Tweakers.net) bevatten enorm veel
    boilerplate; de oude naïeve tag-strip zette dat allemaal in de bundle → trage ingest +
    vervuilde concept-extractie. trafilatura vindt de hoofd-content; komt daar te weinig
    uit, dan valt het terug op de naïeve strip zodat we nooit naar 'leeg' regresseren.

    **De toets was tot 22 aug 2026 `if extracted and extracted.strip()`** — oftewel:
    bestáát er output. Dat is geen bruikbaar criterium, want een degeneratieve extractie
    is niet leeg. Gemeten die dag op vier Skipr/Zorgvisie-artikelen, allemaal met een
    volwaardige snapshot (18 `<p>`-tags, `<article>`-elementen, geen JS-shell):

        item        trafilatura   naïeve strip
        PPWVUYJ5             58            498
        GXAHWB4K            183            587
        R259SKCH             52            966
        6STPYA4B            239            717

    Alle vier waren met de naïeve strip ruim door de bundeldrempel gekomen; met
    trafilatura strandden ze op `status: "leeg"` en bleven ze in de `_inbox` hangen.

    Waarom een *absolute* ondergrens en geen verhouding: trafilatura's bestaansreden is
    juist dat zijn output veel kleiner is dan de naïeve strip (Tweakers ging van ~170 KB
    naar ~5 KB). "Kleiner dan naïef" is dus normaal en geen faalsignaal. Wat hier telt is
    dat het resultaat te klein is om een artikel te kúnnen zijn.
    """
    extracted = ""
    try:
        import trafilatura
        extracted = trafilatura.extract(
            raw_html, include_comments=False, include_tables=True,
            url=url or None,
        ) or ""
    except Exception as exc:  # trafilatura ontbreekt of faalt → fallback
        print(f"  trafilatura niet gebruikt ({exc}) — val terug op naïeve strip", file=sys.stderr)

    tekst = extracted.strip()
    if len(tekst.split()) >= MIN_ARTIKEL_WOORDEN:
        return tekst

    naief = _naive_html_to_text(raw_html)
    gekozen = _kies_tekst(tekst, naief)
    if gekozen is naief and tekst:
        print(f"  trafilatura gaf {len(tekst.split())} woorden waar de naïeve strip er "
              f"{len(naief.split())} vindt — naïeve strip gebruikt", file=sys.stderr)
    return gekozen


def _kies_tekst(getrokken: str, naief: str) -> str:
    """Kiest tussen de trafilatura-extractie en de naïeve tag-strip.

    Apart gehouden zodat de beslissing testbaar is zonder trafilatura (de CI installeert
    niets). De regel: haalt de extractie de bundeldrempel, dan wint hij — dát is waar
    trafilatura voor is. Haalt hij hem niet, dan wordt de bundle toch afgewezen en is de
    keuze er een tussen boilerplate en niets; pak dan wat het meeste oplevert.
    """
    if len(getrokken.split()) >= MIN_ARTIKEL_WOORDEN:
        return getrokken
    return naief if len(naief.split()) > len(getrokken.split()) else getrokken


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
        # Fallback: gebruik abstractNote als het item de _enriched-shownotes tag heeft.
        # Dit dekt podcast-items die via enrich-inbox.py show notes hebben gekregen
        # maar nog geen transcript-bijlage hebben.
        try:
            import urllib.request as _ureq
            _item_url = f"http://localhost:23119/api/users/0/items/{item_key}"
            with _ureq.urlopen(_item_url, timeout=5) as _r:
                _item_data = json.loads(_r.read())
            _tags = [t["tag"] for t in _item_data["data"].get("tags", [])]
            if "_enriched-shownotes" in _tags:
                _abstract = _item_data["data"].get("abstractNote", "").strip()
                if _abstract:
                    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(_abstract)
                    print(f"Opgeslagen: {output_path} ({len(_abstract):,} tekens, type: shownotes)")
                    return
        except Exception as _e:
            print(f"  Show notes fallback mislukt: {_e}", file=sys.stderr)

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
            content = extract_article_text(raw_html)
            print(f"  Linked snapshot gelezen: {linked.name} ({len(content):,} tekens, schoongemaakt)",
                  file=sys.stderr)

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
            content = extract_article_text(raw_html)
            print(f"  Snapshot uit storage: {html_files[0].name} ({len(content):,} tekens, schoongemaakt)",
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
