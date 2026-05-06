#!/usr/bin/env python3
"""
build-zotero-bundle.py — Canonical markdown bundle per Zotero-item.

Haalt voor een Zotero-item op:
  - Metadata (titel, auteurs, jaar, citekey, tags)
  - Abstract (abstractNote)
  - Verbatim child notes (HTML → Markdown, stdlib only)
  - PDF-annotaties (highlights + opmerkingen, gegroepeerd per pagina)
  - Volledige PDF-tekst (via bestaande fetch-fulltext.py)

Schrijft alles als canonical bundle naar vault/raw/{citekey}__{itemKey}.md.
Geen LLM betrokken: puur format-conversie van Zotero-data naar Markdown.

Gebruik:
    python3 .claude/build-zotero-bundle.py --item-key ITEMKEY

Output (stdout, JSON):
    {"status": "ok", "path": "vault/raw/{citekey}__{itemKey}.md"}
    {"status": "error", "message": "..."}

Privacy: geen broninhoud naar stdout — alleen JSON-statusobject.
"""

from __future__ import annotations

import argparse
import html as html_module
import json
import os
import re
import subprocess
import sys
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

# ── Padconfiguratie ───────────────────────────────────────────────────────────

VAULT_ROOT  = Path(__file__).resolve().parent.parent
CLAUDE_DIR  = VAULT_ROOT / ".claude"
PYTHON      = Path(os.environ.get(
    "ZOTERO_PYTHON",
    "/Users/pietstam/.local/share/uv/tools/zotero-mcp-server/bin/python3",
))
FETCH_SCRIPT      = CLAUDE_DIR / "fetch-fulltext.py"
RAW_DIR           = VAULT_ROOT / "vault" / "raw"
CACHE_DIR         = VAULT_ROOT / "vault" / ".cache"
ZOTERO_BASE       = "http://localhost:23119/api/users/0"
EXPORTER_VERSION  = "1.0"

# ── Zotero API ────────────────────────────────────────────────────────────────

def zotero_get(path: str) -> list | dict:
    """GET-request naar lokale Zotero REST API (poort 23119)."""
    url = f"{ZOTERO_BASE}{path}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read())
    except Exception as exc:
        _error(f"Zotero lokale API niet bereikbaar ({url}): {exc}")


def _error(msg: str) -> None:
    print(json.dumps({"status": "error", "message": msg}))
    sys.exit(1)

# ── HTML → Markdown (stdlib) ──────────────────────────────────────────────────

def html_to_md(raw: str) -> str:
    """Eenvoudige HTML → Markdown conversie zonder externe dependencies."""
    text = html_module.unescape(raw)

    # Koppen
    for level in range(6, 0, -1):
        prefix = "#" * level + " "
        text = re.sub(
            rf"<h{level}[^>]*>(.*?)</h{level}>",
            lambda m, p=prefix: p + m.group(1).strip(),
            text, flags=re.IGNORECASE | re.DOTALL,
        )

    # Vet en cursief
    text = re.sub(r"<strong[^>]*>(.*?)</strong>", r"**\1**", text,
                  flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<b[^>]*>(.*?)</b>", r"**\1**", text,
                  flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<em[^>]*>(.*?)</em>", r"*\1*", text,
                  flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<i[^>]*>(.*?)</i>", r"*\1*", text,
                  flags=re.IGNORECASE | re.DOTALL)

    # Links
    text = re.sub(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        r"[\2](\1)", text, flags=re.IGNORECASE | re.DOTALL,
    )

    # Lijstitems (vóór het verwijderen van ul/ol/li-tags)
    text = re.sub(r"<li[^>]*>(.*?)</li>", r"- \1", text,
                  flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"</?(u|o)l[^>]*>", "", text, flags=re.IGNORECASE)

    # Alinea's en regeleinden
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)

    # Resterende HTML-tags verwijderen
    text = re.sub(r"<[^>]+>", "", text)

    # Overtollige witruimte opruimen
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

# ── Hulpfuncties ──────────────────────────────────────────────────────────────

def format_creators(creators: list) -> list[str]:
    result = []
    for c in creators:
        if "lastName" in c:
            name = c["lastName"]
            if "firstName" in c:
                name += f", {c['firstName']}"
        elif "name" in c:
            name = c["name"]
        else:
            continue
        result.append(name)
    return result


def page_sort_key(label: str) -> tuple:
    """Sorteert paginanummers: numeriek eerst (op waarde), daarna alfabet."""
    return (0, int(label), "") if label.isdigit() else (1, 0, label)


def detect_source_type(item_type: str) -> str:
    if item_type in ("journalArticle", "book", "bookSection", "report",
                     "thesis", "preprint", "conferencePaper"):
        return "paper"
    if item_type == "videoRecording":
        return "youtube"
    if item_type in ("podcast", "audioRecording"):
        return "podcast"
    return "web"

# ── Bundle builder ────────────────────────────────────────────────────────────

def build_bundle(item_key: str) -> Path:
    """Bouw canonical bundle voor één Zotero-item. Retourneert het pad."""

    # 1 ── Metadata
    print(f"[1/4] Metadata ophalen voor {item_key}…", file=sys.stderr)
    item = zotero_get(f"/items/{item_key}")
    data = item.get("data", {})

    title       = data.get("title", "")
    creators    = format_creators(data.get("creators", []))
    raw_date    = str(data.get("date", ""))
    year        = raw_date[:4] if raw_date else ""
    doi         = data.get("DOI", "")
    journal     = data.get("publicationTitle",
                  data.get("bookTitle", data.get("publisher", "")))
    tags        = [t["tag"] for t in data.get("tags", [])
                   if not t["tag"].startswith("_")]
    citekey     = data.get("citationKey", "")
    item_type   = data.get("itemType", "")
    abstract    = data.get("abstractNote", "")
    source_type = detect_source_type(item_type)

    # 2 ── Child items (notes + PDF-bijlagen)
    print("[2/4] Child items ophalen…", file=sys.stderr)
    children = zotero_get(f"/items/{item_key}/children")

    child_notes = [c for c in children if c["data"].get("itemType") == "note"]
    pdf_attachments = [
        c for c in children
        if c["data"].get("itemType") == "attachment"
        and c["data"].get("contentType") == "application/pdf"
    ]

    # 3 ── Annotaties (children van de PDF-bijlage)
    annotations_by_page: dict[str, list] = defaultdict(list)
    if pdf_attachments:
        attachment_key = pdf_attachments[0]["key"]
        print(f"[3/4] Annotaties ophalen voor bijlage {attachment_key}…",
              file=sys.stderr)
        try:
            ann_items = zotero_get(f"/items/{attachment_key}/children")
            for ann in ann_items:
                ann_data = ann.get("data", {})
                if ann_data.get("itemType") != "annotation":
                    continue
                page = ann_data.get("annotationPageLabel", "?")
                annotations_by_page[page].append({
                    "type":    ann_data.get("annotationType", "highlight"),
                    "text":    ann_data.get("annotationText", "").strip(),
                    "comment": ann_data.get("annotationComment", "").strip(),
                })
        except SystemExit:
            raise
        except Exception as exc:
            print(f"  Annotaties ophalen mislukt (niet fataal): {exc}",
                  file=sys.stderr)
    else:
        print("[3/4] Geen PDF-bijlage — annotaties overgeslagen.",
              file=sys.stderr)

    # 4 ── Volledige tekst via fetch-fulltext.py
    print("[4/4] Volledige tekst ophalen…", file=sys.stderr)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    temp_txt = CACHE_DIR / f"_bundle_tmp_{item_key}.txt"

    fulltext = ""
    try:
        proc = subprocess.run(
            [str(PYTHON), str(FETCH_SCRIPT), item_key, str(temp_txt)],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode == 0 and temp_txt.exists():
            fulltext = temp_txt.read_text(encoding="utf-8")
        else:
            print(f"  Tekst ophalen mislukt: {proc.stderr.strip()}",
                  file=sys.stderr)
    except Exception as exc:
        print(f"  fetch-fulltext.py fout (niet fataal): {exc}", file=sys.stderr)
    finally:
        temp_txt.unlink(missing_ok=True)

    # ── Bundle samenstellen ───────────────────────────────────────────────────
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"{citekey}__{item_key}.md" if citekey else f"{item_key}.md"
    bundle_path = RAW_DIR / filename

    lines: list[str] = []

    # Frontmatter
    lines += ["---",
              f"citekey: {citekey or item_key}",
              f"zotero_item_key: {item_key}",
              f'title: {json.dumps(title, ensure_ascii=False)}',
              f"creators: {json.dumps(creators, ensure_ascii=False)}",
              f"year: {year!r}"]
    if doi:
        lines.append(f"doi: {json.dumps(doi)}")
    if journal:
        lines.append(f"journal: {json.dumps(journal, ensure_ascii=False)}")
    lines += [f'zotero_uri: "zotero://select/library/items/{item_key}"',
              f"tags: {json.dumps(tags, ensure_ascii=False)}",
              f"source_type: {source_type}",
              f"exported_at: {date.today().isoformat()}",
              f'exporter_version: "{EXPORTER_VERSION}"',
              "---", ""]

    lines += [f"# {citekey or item_key}", ""]

    if abstract:
        lines += ["## Abstract", "", abstract, ""]

    if child_notes:
        lines += ["## Zotero-notities", ""]
        for note in child_notes:
            note_html = note["data"].get("note", "")
            if note_html.strip():
                lines += [html_to_md(note_html), ""]

    if annotations_by_page:
        lines += ["## Annotaties", ""]
        for page in sorted(annotations_by_page, key=page_sort_key):
            lines.append(f"### Pagina {page}")
            for ann in annotations_by_page[page]:
                if ann["text"]:
                    lines.append(
                        f'- **{ann["type"].capitalize()}**: "{ann["text"]}"'
                    )
                    if ann["comment"]:
                        lines.append(f'  - Opmerking: {ann["comment"]}')
                elif ann["comment"]:
                    lines.append(f'- **Opmerking**: {ann["comment"]}')
            lines.append("")

    if fulltext:
        lines += ["## Volledige tekst", ""]
        # Splits op form-feed paginascheidingstekens (gangbaar in PDF-extractie)
        pages = re.split(r"\f", fulltext)
        if len(pages) > 1:
            for i, page_text in enumerate(pages, 1):
                page_text = page_text.strip()
                if page_text:
                    lines += [f"### Pagina {i}", "", page_text, ""]
        else:
            lines += [fulltext.strip(), ""]

    bundle_path.write_text("\n".join(lines), encoding="utf-8")
    return bundle_path

# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Canonical Zotero bundle builder — vault/raw/"
    )
    parser.add_argument("--item-key", required=True, help="Zotero item key")
    args = parser.parse_args()

    # Laad .env als ZOTERO_API_KEY niet gezet is (voor fetch-fulltext.py)
    if not os.environ.get("ZOTERO_API_KEY"):
        env_file = VAULT_ROOT / ".env"
        if env_file.exists():
            try:
                from dotenv import load_dotenv
                load_dotenv(env_file)
            except ImportError:
                pass

    bundle_path = build_bundle(args.item_key)

    try:
        rel = bundle_path.relative_to(VAULT_ROOT)
    except ValueError:
        rel = bundle_path

    print(json.dumps({"status": "ok", "path": str(rel)}))


if __name__ == "__main__":
    main()
