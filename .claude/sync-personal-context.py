#!/usr/bin/env python3
"""sync-personal-context.py — Fase G/G2 (mechanisme A): personal→compartiment context-brug.

Kopieert de gepubliceerde persoonlijke wiki-kennis naar de `raw/_personal-context/`-laag
van een vertrouwelijk compartiment, zodat olw-synthese ín dat compartiment de persoonlijke
(LAAG) kennis kan meewegen. Dit is de toegestane "read-down" van de need-to-know lattice
(Bell-LaPadula): persoonlijk verrijkt vertrouwelijk werk; niets stroomt terug.

Ontwerpbesluiten (ontwerpsessie 2026-07-10 + G2-discussie 2026-07-16):
- Mechanisme A = KOPIE (geen hardlink/symlink): een marker moet worden geïnjecteerd, wat
  het bestand wijzigt → een hardlink zou personal's origineel meewijzigen; een symlink laat
  olw's `resolve()`+`relative_to(vault)` crashen. Kopie is bovendien structureel veilig.
- Bron = `wiki/*.md` (concepten) + `wiki/syntheses/*.md`. EXCLUSIEF `sources/` (per-bron
  bibliografische kruisverwijzingen = synthese-ruis) en `.drafts/` (nog niet gepubliceerd).
- DETERMINISTISCHE marker `_personal_context: true` — GEEN timestamp: olw detecteert
  wijzigingen via een content-hash; een datum zou elke sync álle bestanden opnieuw laten
  ingesten. olw negeert onbekende frontmatter-velden (leest alleen `title`).
- Idempotent: de `_personal-context/`-subtree wordt elke run vers herbouwd vanuit de bron.
- Geen auto-ingest: populeert + geeft het `olw ingest`-vervolgcommando terug (lange
  olw-runs draai je in je eigen terminal).
- Privacy-grens: leest bron-bestanden lokaal, schrijft lokaal, geeft alleen JSON-status
  terug. Geen inhoud wordt geprint (subagent-patroon).

Gebruik:
    sync-personal-context.py <naam>
    # → {"status": "ok", "path": ".../raw/_personal-context", "synced": N, ...}
"""

import json
import re
import shutil
import sys
from pathlib import Path

CONFIDENTIAL_ROOT = Path.home() / "Confidential"
VAULT_ROOT = Path(__file__).resolve().parent.parent  # repo-root
PERSONAL_WIKI = VAULT_ROOT / "vault" / "wiki"
NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
MARKER_LINE = "_personal_context: true"


def fail(message):
    print(json.dumps({"status": "error", "error": message}))
    sys.exit(1)


def collect_sources():
    """Gepubliceerde persoonlijke kennis: concepten (top-level) + syntheses.

    Retourneert een lijst (src_path, rel_path) waarbij rel_path de plaatsing binnen
    _personal-context/ bepaalt (structuur gespiegeld, geen naambotsingen).
    """
    items = []
    # Concepten: alleen top-level *.md in wiki/ (geen submappen).
    for p in sorted(PERSONAL_WIKI.glob("*.md")):
        items.append((p, Path(p.name)))
    # Syntheses: wiki/syntheses/*.md → _personal-context/syntheses/*.md.
    syn_dir = PERSONAL_WIKI / "syntheses"
    if syn_dir.is_dir():
        for p in sorted(syn_dir.glob("*.md")):
            items.append((p, Path("syntheses") / p.name))
    return items


def inject_marker(text):
    """Voeg de deterministische _personal_context-marker toe aan de frontmatter.

    Werkt op zowel bestanden mét als zonder frontmatter. Idempotent: als de marker al
    aanwezig is, ongewijzigd teruggeven. Body blijft verbatim (nooit geprint).
    """
    if re.search(rf"^{re.escape(MARKER_LINE)}\s*$", text, flags=re.MULTILINE):
        return text  # al aanwezig

    if text.startswith("---\n"):
        # Injecteer als eerste veld ná de openings-`---`.
        return "---\n" + MARKER_LINE + "\n" + text[4:]
    # Geen frontmatter → wikkel er een omheen.
    return "---\n" + MARKER_LINE + "\n---\n\n" + text


def main():
    if len(sys.argv) != 2:
        fail("gebruik: sync-personal-context.py <naam>")

    name = sys.argv[1].strip()
    if not NAME_RE.match(name):
        fail(f"ongeldige naam {name!r}: alleen letters, cijfers, '-' en '_' toegestaan")

    compartment = CONFIDENTIAL_ROOT / name
    if not compartment.is_dir():
        fail(f"compartiment bestaat niet: {compartment} — draai eerst new-compartment.py")
    raw_dir = compartment / "raw"
    if not raw_dir.is_dir():
        fail(f"geen raw/-map in compartiment: {raw_dir}")

    if not PERSONAL_WIKI.is_dir():
        fail(f"persoonlijke wiki niet gevonden: {PERSONAL_WIKI}")

    sources = collect_sources()
    if not sources:
        fail(f"geen gepubliceerde artikelen gevonden in {PERSONAL_WIKI}")

    # Idempotent: subtree vers herbouwen.
    ctx_dir = raw_dir / "_personal-context"
    if ctx_dir.exists():
        shutil.rmtree(ctx_dir)
    ctx_dir.mkdir(mode=0o700, parents=True)

    n_concepts = 0
    n_syntheses = 0
    for src, rel in sources:
        dst = ctx_dir / rel
        dst.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        # Lees lokaal, injecteer marker, schrijf lokaal — inhoud wordt nooit geprint.
        dst.write_text(inject_marker(src.read_text(encoding="utf-8")), encoding="utf-8")
        if rel.parent == Path("syntheses"):
            n_syntheses += 1
        else:
            n_concepts += 1

    print(json.dumps({
        "status": "ok",
        "path": str(ctx_dir),
        "synced": n_concepts + n_syntheses,
        "sources": {"concepts": n_concepts, "syntheses": n_syntheses},
        "next": f"olw ingest {ctx_dir} --vault {compartment} --fast-model mistral-small:22b",
    }))


if __name__ == "__main__":
    main()
