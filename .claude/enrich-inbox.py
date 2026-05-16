#!/usr/bin/env python3
"""
enrich-inbox.py — Verrijkt Zotero _inbox-items die via iOS zijn gedeeld.

Verrijkt items zonder tag '_enriched' met:
1. Metadata: CrossRef (DOI-items) of Open Graph tags (webartikelen)
2. PDF-bijlage via Unpaywall (open access), of VU EZProxy-URL in extra (paywall)
3. HTML-snapshot als linked_file bijlage (webartikelen zonder DOI)

Output (stdout): JSON-summary {"status","enriched","skipped","errors"}
Privacypatroon: geen webinhoud in stdout — alles gaat naar lokale bestanden.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

# ── Constanten ─────────────────────────────────────────────────────────────────

ZOTERO_LOCAL_API = "http://localhost:23119/api/users/0"
INBOX_COLLECTION_KEY = "N4MP46Y5"

# Zotero-veldnaam voor "publicatienaam" verschilt per itemtype
PUBLICATION_FIELD: dict = {
    "journalArticle": "publicationTitle",
    "magazineArticle": "publicationTitle",
    "newspaperArticle": "publicationTitle",
    "webpage": "websiteTitle",
    "blogPost": "blogTitle",
    # videoRecording, podcast, report etc. hebben geen publicatienaam-veld
}

CROSSREF_API = "https://api.crossref.org/works/{}?mailto=piet@pietstam.nl"
UNPAYWALL_API = "https://api.unpaywall.org/v2/{}?email=piet@pietstam.nl"
VU_EZPROXY_PREFIX = "https://vu-nl.idm.oclc.org/login?url="

PAPERS_DIR = Path.home() / "Zotero" / "Papers"
SNAPSHOTS_DIR = Path.home() / "Zotero" / "Snapshots"

UA = "Mozilla/5.0 (Macintosh) enrich-inbox/1.0 (mailto:piet@pietstam.nl)"

ZOTERO_API_KEY = os.environ.get("ZOTERO_API_KEY", "")
ZOTERO_USER_ID = os.environ.get("ZOTERO_LIBRARY_ID", "")
ZOTERO_API_BASE = f"https://api.zotero.org/users/{ZOTERO_USER_ID}"

# ── HTTP-helpers ────────────────────────────────────────────────────────────────

def _get_local(url: str, timeout: int = 30) -> bytes:
    """Zotero lokale API (localhost) — geen User-Agent, anders weigert Zotero de verbinding."""
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def _get(url: str, headers: dict = None, timeout: int = 30) -> bytes:
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        return r.read()


def _zotero(path: str, method: str = "GET", data: bytes = None,
            extra: dict = None) -> bytes:
    h = {"Zotero-API-Key": ZOTERO_API_KEY, "Zotero-API-Version": "3", "User-Agent": UA}
    if extra:
        h.update(extra)
    req = urllib.request.Request(
        f"{ZOTERO_API_BASE}{path}", data=data, headers=h, method=method
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

# ── _inbox items ophalen ────────────────────────────────────────────────────────

def get_inbox_items() -> list:
    items, PAGE = [], 100
    try:
        for start in range(0, 5000, PAGE):
            batch = json.loads(
                _get_local(f"{ZOTERO_LOCAL_API}/collections/{INBOX_COLLECTION_KEY}"
                           f"/items?limit={PAGE}&start={start}&format=json")
            )
            if not batch:
                break
            items.extend(batch)
            if len(batch) < PAGE:
                break
    except Exception as e:
        print(f"WAARSCHUWING: _inbox ophalen mislukt: {e}", file=sys.stderr)
    return [i for i in items if i["data"]["itemType"] not in ("attachment", "note")]

# ── DOI-detectie ────────────────────────────────────────────────────────────────

def detect_doi(data: dict) -> Optional[str]:
    if doi := data.get("DOI", "").strip():
        return doi
    m = re.search(r'(?:^|\n)DOI:\s*(10\.\S+)', data.get("extra", ""), re.IGNORECASE)
    if m:
        return m.group(1).rstrip(".,)")
    url = data.get("url", "")
    # doi.org of dx.doi.org links
    m = re.search(r'(?:doi\.org|dx\.doi\.org)/?([^?\s#]+)', url)
    if m:
        return m.group(1).rstrip(".,)")
    # Springer/publisher PDF-URLs: link.springer.com/content/pdf/10.xxx/yyy.pdf
    m = re.search(r'/(10\.\d{4,}/[^?\s#]+?)(?:\.pdf)?$', url)
    if m:
        return m.group(1).rstrip(".,)")
    return None

# ── Fase 1: Metadata ─────────────────────────────────────────────────────────────

def crossref_lookup(doi: str) -> dict:
    raw = json.loads(_get(CROSSREF_API.format(urllib.parse.quote(doi, safe=""))))["message"]
    fields = {}
    if raw.get("title"):
        fields["title"] = raw["title"][0]
    creators = []
    for a in raw.get("author", []):
        if "family" in a:
            creators.append({"creatorType": "author",
                              "firstName": a.get("given", ""), "lastName": a["family"]})
        elif "name" in a:
            creators.append({"creatorType": "author", "name": a["name"]})
    if creators:
        fields["creators"] = creators
    if abstract := re.sub(r'<[^>]+>', '', raw.get("abstract", "")).strip():
        fields["abstractNote"] = abstract
    if containers := raw.get("container-title", []):
        fields["publicationTitle"] = containers[0]
    published = raw.get("published-print") or raw.get("published-online") or {}
    parts = published.get("date-parts", [[]])[0]
    if parts:
        fields["date"] = f"{parts[0]}-{parts[1]:02d}" if len(parts) > 1 else str(parts[0])
    for crossref_f, zotero_f in (("volume", "volume"), ("issue", "issue"), ("page", "pages")):
        if raw.get(crossref_f):
            fields[zotero_f] = str(raw[crossref_f])
    if raw.get("DOI"):
        fields["DOI"] = raw["DOI"]
    return fields


def fetch_og_tags(url: str) -> dict:
    try:
        html = _get(url, timeout=15).decode("utf-8", errors="replace")
    except Exception:
        return {}

    def meta(*names) -> str:
        for name in names:
            for pat in [
                rf'<meta[^>]+(?:property|name)\s*=\s*["\'][^"\']*{re.escape(name)}[^"\']*["\'][^>]*content\s*=\s*["\']([^"\']+)',
                rf'<meta[^>]+content\s*=\s*["\']([^"\']+)["\'][^>]*(?:property|name)\s*=\s*["\'][^"\']*{re.escape(name)}[^"\']*["\']',
            ]:
                if m := re.search(pat, html, re.IGNORECASE):
                    return m.group(1).strip()
        return ""

    fields = {}
    if desc := meta("og:description", "description"):
        fields["abstractNote"] = desc
    if author := meta("author", "article:author"):
        parts = author.rsplit(" ", 1)
        fields["creators"] = [{"creatorType": "author",
                                "firstName": parts[0] if len(parts) > 1 else "",
                                "lastName": parts[-1]}]
    if site := meta("og:site_name"):
        fields["publicationTitle"] = site
    if pub := meta("article:published_time", "datePublished"):
        if m := re.match(r'(\d{4}-\d{2}-\d{2})', pub):
            fields["date"] = m.group(1)
    return fields

# ── Fase 2: Bijlage ──────────────────────────────────────────────────────────────

def unpaywall_lookup(doi: str) -> Optional[str]:
    try:
        data = json.loads(_get(UNPAYWALL_API.format(urllib.parse.quote(doi, safe=""))))
        best = data.get("best_oa_location") or {}
        return best.get("url_for_pdf") or best.get("url")
    except Exception:
        return None


def download_pdf(pdf_url: str, dest: Path) -> bool:
    try:
        content = _get(pdf_url, timeout=60)
        if not content.startswith(b"%PDF"):
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        return True
    except Exception:
        return False


def fetch_html_snapshot(url: str, dest: Path) -> bool:
    try:
        html = _get(url, timeout=30)
        # Verwijder script- en stijl-tags voor een beter leesbaar snapshot
        cleaned = re.sub(rb'<script[^>]*>.*?</script>', b'', html, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(rb'<style[^>]*>.*?</style>', b'', cleaned, flags=re.DOTALL | re.IGNORECASE)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(cleaned)
        return True
    except Exception:
        return False


def create_attachment(item_key: str, path: Path, content_type: str, title: str):
    payload = json.dumps([{
        "itemType": "attachment", "linkMode": "linked_file",
        "title": title, "parentItem": item_key,
        "contentType": content_type, "path": str(path),
    }]).encode()
    _zotero("/items", method="POST", data=payload,
            extra={"Content-Type": "application/json"})

# ── Hoofd-enrichment ─────────────────────────────────────────────────────────────

def enrich_item(item: dict) -> dict:
    data = item["data"]
    key = data["key"]
    existing_tags = {t["tag"] for t in data.get("tags", [])}

    if "_enriched" in existing_tags:
        return {"key": key, "status": "skipped"}

    actions = []
    doi = detect_doi(data)
    url = data.get("url", "")

    # ── Fase 1: Metadata (externe API-calls) ─────────────────────────────────
    metadata = {}
    if doi:
        try:
            metadata = crossref_lookup(doi)
            actions.append("crossref")
        except Exception as e:
            print(f"  CrossRef {key}: {e}", file=sys.stderr)
    elif url:
        try:
            metadata = fetch_og_tags(url)
            if metadata:
                actions.append("og-tags")
        except Exception as e:
            print(f"  OG-tags {key}: {e}", file=sys.stderr)

    # ── Fase 2: Bijlage (lokale opslag, vóór Zotero-PATCH) ───────────────────
    pdf_path = snapshot_path = None
    attachment_type = None

    if doi:
        if pdf_url := unpaywall_lookup(doi):
            dest = PAPERS_DIR / f"{key}.pdf"
            if download_pdf(pdf_url, dest):
                pdf_path = dest
                attachment_type = "pdf"
                actions.append("unpaywall-pdf")
        if not pdf_path:
            attachment_type = "ezproxy"
            actions.append("vu-ezproxy")
    elif url:
        dest = SNAPSHOTS_DIR / f"{key}.html"
        if fetch_html_snapshot(url, dest):
            snapshot_path = dest
            attachment_type = "snapshot"
            actions.append("html-snapshot")

    # ── Zotero bijwerken: één GET → één PATCH → optioneel POST bijlage ────────
    try:
        current = json.loads(_zotero(f"/items/{key}"))
        current_data = current["data"]
        version = current_data["version"]
        item_type = current_data.get("itemType", "")

        # Bouw gecombineerde update-payload (veldnamen aanpassen per itemtype)
        update: dict = {}
        for k, v in metadata.items():
            if k == "tags":
                continue
            if k == "publicationTitle":
                mapped = PUBLICATION_FIELD.get(item_type)
                if mapped:
                    update[mapped] = v
                # Geen geldig veld voor dit type → weglaten
            elif k in ("volume", "issue", "pages") and item_type not in (
                "journalArticle", "magazineArticle", "newspaperArticle"
            ):
                pass  # Paginering irrelevant voor niet-artikel types
            else:
                update[k] = v

        if attachment_type == "ezproxy" and doi:
            extra = current_data.get("extra", "")
            if "VU EZProxy:" not in extra:
                update["extra"] = (
                    extra + f"\nVU EZProxy: {VU_EZPROXY_PREFIX}https://doi.org/{doi}"
                ).strip()

        # Tags: bewaar bestaande + voeg nieuwe toe
        new_tags = list(current_data.get("tags", []))
        tag_names = {t["tag"] for t in new_tags}
        new_tags.append({"tag": "_enriched"})
        if metadata and "_enriched-metadata" not in tag_names:
            new_tags.append({"tag": "_enriched-metadata"})
        type_tag = {
            "pdf": "_enriched-pdf",
            "ezproxy": "_enriched-oa-missing",
            "snapshot": "_enriched-snapshot",
        }.get(attachment_type)
        if type_tag and type_tag not in tag_names:
            new_tags.append({"tag": type_tag})
        update["tags"] = new_tags

        _zotero(
            f"/items/{key}", method="PATCH",
            data=json.dumps(update).encode(),
            extra={"Content-Type": "application/json",
                   "If-Unmodified-Since-Version": str(version)},
        )

        # Bijlage aanmaken na de PATCH (verwijzing naar al opgeslagen bestand)
        if pdf_path:
            create_attachment(key, pdf_path, "application/pdf", f"PDF – {doi}")
        elif snapshot_path:
            create_attachment(key, snapshot_path, "text/html", "Snapshot")

        return {"key": key, "status": "ok", "actions": actions}

    except Exception as e:
        return {"key": key, "status": "error", "error": str(e), "actions": actions}

# ── Main ──────────────────────────────────────────────────────────────────────────

def main():
    if not ZOTERO_API_KEY or not ZOTERO_USER_ID:
        print(json.dumps({
            "status": "error",
            "message": "ZOTERO_API_KEY of ZOTERO_LIBRARY_ID niet gezet in omgeving",
        }))
        sys.exit(1)

    items = get_inbox_items()
    enriched = skipped = 0
    errors = []

    for item in items:
        result = enrich_item(item)
        print(f"  {result['status']:7s} {result['key']} "
              f"{result.get('actions', [])}", file=sys.stderr)
        if result["status"] == "ok":
            enriched += 1
        elif result["status"] == "skipped":
            skipped += 1
        else:
            errors.append({"key": result["key"], "error": result.get("error", "?")})
        time.sleep(1.5)  # Beleefd jegens externe APIs en Zotero Web API rate limit

    print(json.dumps({
        "status": "ok",
        "enriched": enriched,
        "skipped": skipped,
        "errors": errors,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
