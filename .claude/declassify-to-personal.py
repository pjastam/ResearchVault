#!/usr/bin/env python3
"""
declassify-to-personal.py — Fase G/G3: de declassificatie-klep (spec-naam: "promote-to-wiki").

De ENIGE toegestane neerwaartse stroom in de need-to-know lattice (Bell-LaPadula "no
write-down"): een algemeen, herbruikbaar inzicht (een methode) dat je in een vertrouwelijk
compartiment (HOOG) ontwikkelde, bewust ONTGEVOELIGD naar je persoonlijke wiki (LAAG) brengen —
zodat het je toekomstige authoring verrijkt, zónder klant-data mee te nemen.

NAAM-MAPPING: de ontwerpdocs + diagram-v5-volledig.jsx noemen deze klep "promote-to-wiki".
Dit script IS die klep; de naam benadrukt de veiligheidskritieke richting (declassificatie).
Bij G7 (docs + einddroom-diagram) de doc-/diagramnaam meeverhuizen naar declassify-to-personal.

VEILIGHEIDSMODEL — eerlijk: dit is het enige punt in het systeem waar menselijk oordeel dragend
is en NIET structureel gemaakt kan worden. Een script kan niet vaststellen dat er geen klant-data
in zit. Dit script levert daarom FRICTIE + PROVENANCE-HYGIËNE, geen inhoudelijke garantie:
  - Dubbele bevestiging (frictie, geen assurance): CLI-flag --confirm-desensitized ÉN een
    verplichte `_desensitized: true`-marker in de bronnotitie. Twee bewuste handelingen.
  - Bron moet in een compartiment (~/Confidential/) liggen — bevestigt dat dit een echte
    declassificatie is.
  - Provenance-STRIP: GEEN origin_uri/compartiment-pad in de personal-notitie (dat zou de
    LAAG-wiki de HOOG-herkomst inlekken). Alleen een generieke marker `declassified: true`.
De echte zekerheid blijft: (a) jouw inhoudelijke ontgevoeliging en (b) de persoonlijke
`olw review`-gate als tweede menselijke checkpoint vóór publicatie.

Gebruik:
    python3 .claude/declassify-to-personal.py --note PAD --confirm-desensitized
                                              [--slug SLUG] [--title TITEL] [--tags a,b]
                                              [--dry-run] [--no-ingest]

Output (stdout, JSON): {"status": "ok", "path": "vault/raw/notes/<slug>.md", "ingested": bool}
Privacy: geen bron-/body-inhoud naar stdout — alleen een JSON-statusobject. Geen LLM.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

# ── Padconfiguratie ───────────────────────────────────────────────────────────

VAULT_ROOT        = Path(__file__).resolve().parent.parent
VAULT_DIR         = VAULT_ROOT / "vault"
RAW_NOTES_DIR     = VAULT_DIR / "raw" / "notes"
CONFIDENTIAL_ROOT = Path.home() / "Confidential"
OLW               = Path("/Users/pietstam/.local/bin/olw")
OLW_LOG           = VAULT_DIR / ".olw-declassify.log"   # gitignored (.olw-*.log)
EXPORTER_VERSION  = "1.0"


def _error(msg: str, **extra) -> None:
    print(json.dumps({"status": "error", "message": msg, **extra}))
    sys.exit(1)


# ── Frontmatter ────────────────────────────────────────────────────────────────

def parse_source(text: str) -> tuple[dict, str]:
    """Splitst YAML-frontmatter (WHITELIST title/created/updated/tags) van de body. Kopieert
    GEEN willekeurige velden — zo lift een `source:`/`url:`/`_desensitized:`-veld nooit mee de
    personal-notitie in (provenance-hygiëne; `_desensitized` blijft compartiment-zijde)."""
    meta: dict = {}
    body = text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
    if m:
        fm, body = m.group(1), m.group(2)
        for line in fm.splitlines():
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            key, val = key.strip(), val.strip()
            if key in ("title", "created", "updated"):
                meta[key] = val.strip('"').strip("'")
            elif key == "tags":
                inner = val.strip().strip("[]")
                if inner:
                    meta["tags"] = [t.strip().strip('"').strip("'")
                                    for t in inner.split(",") if t.strip()]
    return meta, body


def has_desensitized_marker(text: str) -> bool:
    """True als de bron-frontmatter `_desensitized: true` bevat (gate-marker, zelf-attestatie)."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not m:
        return False
    for line in m.group(1).splitlines():
        key, _, val = line.partition(":")
        if key.strip() == "_desensitized" and val.strip().strip('"').strip("'").lower() == "true":
            return True
    return False


def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "notitie"


def in_compartment(path: Path) -> bool:
    """True als path binnen ~/Confidential/<naam>/ ligt (echte declassificatie-bron)."""
    try:
        resolved = path.resolve()
    except Exception:
        return False
    return CONFIDENTIAL_ROOT.resolve() in resolved.parents


# ── Hoofdlogica ────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Declassificeer een ontgevoeligd inzicht: compartiment → persoonlijke raw/notes/.")
    ap.add_argument("--note", required=True, help="Pad naar de ontgevoeligde bronnotitie (in een compartiment).")
    ap.add_argument("--slug", help="Stabiele bestandsnaam-stam (default: van bronbestandsnaam).")
    ap.add_argument("--title", help="Titel (default: frontmatter-title of bestandsstam).")
    ap.add_argument("--tags", help="Extra tags, kommagescheiden.")
    ap.add_argument("--confirm-desensitized", action="store_true",
                    help="Bevestig bewust dat de inhoud is ontgevoeligd (gate 1 van 2).")
    ap.add_argument("--dry-run", action="store_true", help="Toon bron→doel zonder iets te schrijven.")
    ap.add_argument("--no-ingest", action="store_true", help="Alleen snapshot; geen olw ingest.")
    args = ap.parse_args()

    src = Path(args.note).expanduser()
    if not src.is_file():
        _error(f"bronnotitie niet gevonden: {src}")

    # Herkomst-guardrail: altijd afgedwongen (ook bij --dry-run).
    if not in_compartment(src):
        _error(f"bron ligt niet in een compartiment (~/Confidential/): {src} — "
               "declassify-to-personal promoot uitsluitend uit een compartiment")

    try:
        text = src.read_text(encoding="utf-8")
    except Exception as exc:
        _error(f"bron niet leesbaar: {exc}")

    slug = slugify(args.slug or src.stem)
    target = RAW_NOTES_DIR / f"{slug}.md"
    rel = str(target.relative_to(VAULT_ROOT))
    marker = has_desensitized_marker(text)

    # --dry-run: preview zonder gates af te dwingen (schrijft toch niks) en zonder writes.
    if args.dry_run:
        print(json.dumps({
            "status": "ok", "dry_run": True, "source": str(src), "target": rel, "slug": slug,
            "has_desensitized_marker": marker, "would_ingest": not args.no_ingest,
        }))
        return

    # Dubbele bevestiging (frictie, geen assurance) — beide gates verplicht voor een echte run.
    if not args.confirm_desensitized:
        _error("gate 1/2 ontbreekt: geef --confirm-desensitized om de declassificatie te bevestigen")
    if not marker:
        _error("gate 2/2 ontbreekt: voeg `_desensitized: true` toe aan de frontmatter van de bronnotitie")

    meta, body = parse_source(text)
    title = args.title or meta.get("title") or src.stem.replace("-", " ").replace("_", " ").strip()

    tags = list(meta.get("tags", []))
    if args.tags:
        tags += [t.strip() for t in args.tags.split(",") if t.strip()]
    tags = list(dict.fromkeys(tags))

    # Gecontroleerde frontmatter — GEEN origin_uri (provenance-strip); geen compartiment-spoor.
    lines = ["---",
             f"title: {json.dumps(title, ensure_ascii=False)}",
             "source_type: personal",
             "declassified: true",
             f"declassified_at: {date.today().isoformat()}"]
    if meta.get("created"):
        lines.append(f"created: {json.dumps(meta['created'])}")
    if meta.get("updated"):
        lines.append(f"updated: {json.dumps(meta['updated'])}")
    lines.append(f"tags: {json.dumps(tags, ensure_ascii=False)}")
    lines.append(f'exporter_version: "{EXPORTER_VERSION}"')
    lines += ["---", "", body.strip(), ""]

    RAW_NOTES_DIR.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")

    # olw ingest in de PERSOONLIJKE vault → persoonlijke draft → `olw review`-gate (2e checkpoint).
    ingested = False
    if not args.no_ingest:
        try:
            with open(OLW_LOG, "w", encoding="utf-8") as lf:
                proc = subprocess.run(
                    [str(OLW), "ingest", str(target), "--vault", str(VAULT_DIR),
                     "--fast-model", "mistral-small:22b"],
                    stdout=lf, stderr=lf, timeout=1800, cwd=str(VAULT_DIR),
                )
            if proc.returncode != 0:
                _error(f"snapshot geschreven; olw ingest faalde (exit {proc.returncode}), "
                       f"zie {OLW_LOG.name}", path=rel)
            ingested = True
        except subprocess.TimeoutExpired:
            _error("snapshot geschreven; olw ingest timeout (>1800s)", path=rel)
        except Exception as exc:
            _error(f"snapshot geschreven; olw ingest fout: {exc}", path=rel)

    print(json.dumps({"status": "ok", "path": rel, "ingested": ingested}))


if __name__ == "__main__":
    main()
