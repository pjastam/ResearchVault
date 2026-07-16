#!/usr/bin/env python3
"""sync-personal-wiki-ref.py — Fase G/G2-B: read-only personal-wiki referentielaag.

Kloont de gepubliceerde persoonlijke wiki-concepten naar `<compartiment>/wiki/_personal/`
als **read-only referentie**, zodat Obsidian binnen de compartiment-vault `[[links]]` en
backlinks naar persoonlijke concepten kan resolveren. Obsidian resolvet links alléén binnen
één vault-root — dus de personal-concepten moeten fysiek in het compartiment staan.

Verschil met sync-personal-context.py (G2-A):
- G2-A → `raw/_personal-context/`: KOPIE + marker; olw INGEST het als synthese-bron.
- G2-B → `wiki/_personal/`: verbatim APFS-KLOON, GEEN marker; puur Obsidian-referentie in de
  output-laag. olw ingest het niet (olw ingest leest `raw/`, niet `wiki/`).

Waarom APFS-klonen (`cp -c`) i.p.v. kopie of hardlink (G2-discussie 2026-07-16):
- Eigen inode + eigen metadata → schrijf-isolatie geldt ALTIJD (getest), ongeacht welk
  gereedschap `_personal/` aanraakt → structureel veilig, i.t.t. hardlink (contingent op
  atomic-write-gedrag).
- ~0 schijf via copy-on-write, schaal-invariant (kopie = O(wiki-omvang x N-compartimenten)).
- Vereist APFS + zelfde volume (bevestigd: vault en ~/Confidential op device 16777233).

GEEN marker en verbatim: olw negeert onbekende velden toch, en Obsidian heeft geen marker
nodig; verbatim houdt `_personal/` een schone spiegel. De "read-only / niet-beheren"-garantie
komt van de guardrail (nooit `olw maintain`/`lint --fix` op een compartiment), niet van een veld.

Privacy-grens: kloont bestanden lokaal (`cp -c`, geen stdout-inhoud), geeft alleen JSON-status
terug. Leest of print nooit inhoud.

Gebruik:
    sync-personal-wiki-ref.py <naam>
    # → {"status": "ok", "path": ".../wiki/_personal", "cloned": N, ...}
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

CONFIDENTIAL_ROOT = Path.home() / "Confidential"
VAULT_ROOT = Path(__file__).resolve().parent.parent  # repo-root
PERSONAL_WIKI = VAULT_ROOT / "vault" / "wiki"
NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def fail(message):
    print(json.dumps({"status": "error", "error": message}))
    sys.exit(1)


def collect_sources():
    """Gepubliceerde persoonlijke concepten (top-level) + syntheses. Zelfde set als G2-A."""
    items = []
    for p in sorted(PERSONAL_WIKI.glob("*.md")):
        items.append((p, Path(p.name)))
    syn_dir = PERSONAL_WIKI / "syntheses"
    if syn_dir.is_dir():
        for p in sorted(syn_dir.glob("*.md")):
            items.append((p, Path("syntheses") / p.name))
    return items


def clone(src, dst):
    """APFS-kloon via `cp -c` (clonefile). capture_output zodat geen inhoud kan lekken."""
    subprocess.run(["cp", "-c", str(src), str(dst)], check=True, capture_output=True)


def main():
    if len(sys.argv) != 2:
        fail("gebruik: sync-personal-wiki-ref.py <naam>")

    name = sys.argv[1].strip()
    if not NAME_RE.match(name):
        fail(f"ongeldige naam {name!r}: alleen letters, cijfers, '-' en '_' toegestaan")

    compartment = CONFIDENTIAL_ROOT / name
    if not compartment.is_dir():
        fail(f"compartiment bestaat niet: {compartment} — draai eerst new-compartment.py")
    wiki_dir = compartment / "wiki"
    if not wiki_dir.is_dir():
        fail(f"geen wiki/-map in compartiment: {wiki_dir}")
    if not PERSONAL_WIKI.is_dir():
        fail(f"persoonlijke wiki niet gevonden: {PERSONAL_WIKI}")

    sources = collect_sources()
    if not sources:
        fail(f"geen gepubliceerde artikelen gevonden in {PERSONAL_WIKI}")

    # Idempotent: subtree vers herbouwen met verse klonen.
    ref_dir = wiki_dir / "_personal"
    if ref_dir.exists():
        shutil.rmtree(ref_dir)
    ref_dir.mkdir(mode=0o700, parents=True)

    n_concepts = 0
    n_syntheses = 0
    for src, rel in sources:
        dst = ref_dir / rel
        dst.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        clone(src, dst)
        if rel.parent == Path("syntheses"):
            n_syntheses += 1
        else:
            n_concepts += 1

    print(json.dumps({
        "status": "ok",
        "path": str(ref_dir),
        "cloned": n_concepts + n_syntheses,
        "sources": {"concepts": n_concepts, "syntheses": n_syntheses},
        "method": "apfs-clone",
    }))


if __name__ == "__main__":
    main()
