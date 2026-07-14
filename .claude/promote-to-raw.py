#!/usr/bin/env python3
"""
promote-to-raw.py — Promotie-poort: rijp denkwerk → schone snapshot in vault/raw/notes/.

De tweede wiki-ingang (Fase D). Je denken leeft in je authoring-map (olw ziet het niet);
is een idee rijp, dan promoveer je een schone snapshot naar vault/raw/notes/, waarna olw
de concepten extraheert. Evoluerend denken = VERVANGEN: her-promoteer met dezelfde --slug
→ hetzelfde bestand wordt overschreven → olw her-ingest en vervangt de oude concepten.

Gebruik:
    python3 .claude/promote-to-raw.py --note PAD [--slug SLUG] [--title TITEL]
                                      [--tags a,b] [--no-ingest]

Output (stdout, JSON):
    {"status": "ok", "path": "vault/raw/notes/<slug>.md", "ingested": true}
    {"status": "error", "message": "..."}

Privacy: geen bron- of body-inhoud naar stdout — alleen een JSON-statusobject. Geen LLM in
dit script; puur een mechanische kopie (olw compileert, dit genereert niet).
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

VAULT_ROOT     = Path(__file__).resolve().parent.parent
VAULT_DIR      = VAULT_ROOT / "vault"
RAW_NOTES_DIR  = VAULT_DIR / "raw" / "notes"
OLW            = Path("/Users/pietstam/.local/bin/olw")
OLW_LOG        = VAULT_DIR / ".olw-promote.log"     # gitignored (.olw-*.log)
EXPORTER_VERSION = "1.0"


def _error(msg: str, **extra) -> None:
    print(json.dumps({"status": "error", "message": msg, **extra}))
    sys.exit(1)


# ── Bron lezen (minimale stdlib-frontmatter-parse) ─────────────────────────────

def parse_source(text: str) -> tuple[dict, str]:
    """Splitst YAML-frontmatter (whitelist) van de body. Kopieert GEEN willekeurige
    velden — alleen title/created/updated/tags — zodat een `source:`/`url:`-veld nooit
    meelift (dat zou olw's web-clip-preprocessing triggeren)."""
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


def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "notitie"


# ── Hoofdlogica ────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Promoteer een notitie naar vault/raw/notes/.")
    ap.add_argument("--note", required=True, help="Pad naar de bronnotitie (authoring).")
    ap.add_argument("--slug", help="Stabiele bestandsnaam-stam (default: van bronbestandsnaam).")
    ap.add_argument("--title", help="Titel (default: frontmatter-title of bestandsstam).")
    ap.add_argument("--tags", help="Extra tags, kommagescheiden.")
    ap.add_argument("--no-ingest", action="store_true", help="Alleen snapshot; geen olw ingest.")
    args = ap.parse_args()

    src = Path(args.note).expanduser()
    if not src.is_file():
        _error(f"bronnotitie niet gevonden: {src}")

    try:
        text = src.read_text(encoding="utf-8")
    except Exception as exc:
        _error(f"bron niet leesbaar: {exc}")

    meta, body = parse_source(text)

    title = args.title or meta.get("title") or src.stem.replace("-", " ").replace("_", " ").strip()
    slug = slugify(args.slug or src.stem)

    tags = list(meta.get("tags", []))
    if args.tags:
        tags += [t.strip() for t in args.tags.split(",") if t.strip()]
    tags = list(dict.fromkeys(tags))  # dedup, orde behouden

    # ── Gecontroleerde frontmatter opbouwen ─────────────────────────────────────
    lines = ["---",
             f"title: {json.dumps(title, ensure_ascii=False)}",
             "source_type: personal",
             f"origin_uri: {json.dumps(str(src.resolve()), ensure_ascii=False)}",
             f"promoted_at: {date.today().isoformat()}"]
    if meta.get("created"):
        lines.append(f"created: {json.dumps(meta['created'])}")
    if meta.get("updated"):
        lines.append(f"updated: {json.dumps(meta['updated'])}")
    lines.append(f"tags: {json.dumps(tags, ensure_ascii=False)}")
    lines.append(f'exporter_version: "{EXPORTER_VERSION}"')
    lines += ["---", "", body.strip(), ""]

    RAW_NOTES_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_NOTES_DIR / f"{slug}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    rel = str(out.relative_to(VAULT_ROOT))

    # ── olw ingest (tenzij --no-ingest) ─────────────────────────────────────────
    ingested = False
    if not args.no_ingest:
        try:
            with open(OLW_LOG, "w", encoding="utf-8") as lf:
                proc = subprocess.run(
                    [str(OLW), "ingest", str(out), "--vault", str(VAULT_DIR),
                     "--fast-model", "mistral-small:22b"],
                    stdout=lf, stderr=lf, timeout=1800, cwd=str(VAULT_DIR),
                )
            if proc.returncode != 0:
                # Snapshot staat er; alleen de ingest faalde. Log-inhoud nooit tonen.
                _error(f"snapshot geschreven; olw ingest faalde (exit {proc.returncode}), "
                       f"zie {OLW_LOG.name}", path=rel)
            ingested = True
        except subprocess.TimeoutExpired:
            _error(f"snapshot geschreven; olw ingest timeout (>1800s)", path=rel)
        except Exception as exc:
            _error(f"snapshot geschreven; olw ingest fout: {exc}", path=rel)

    print(json.dumps({"status": "ok", "path": rel, "ingested": ingested}))


if __name__ == "__main__":
    main()
