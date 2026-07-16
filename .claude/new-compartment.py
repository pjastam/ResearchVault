#!/usr/bin/env python3
"""new-compartment.py — Fase G/G1: scaffolding voor een vertrouwelijk compartiment.

Maakt één geïsoleerde olw-vault per compartiment (need-to-know lattice, Bell-LaPadula
"no write-down"). Elk compartiment is een op zichzelf staande olw-vault met eigen
raw/, wiki/, wiki.toml en (na de eerste ingest) .olw/state.db — fysiek gescheiden van
de persoonlijke ResearchVault-vault én van elkaar.

Ontwerpbesluiten (ontwerpsessie 2026-07-10, sectie "compartimenten-lattice"):
- Compartimenten leven BUITEN de git-repo (~/Confidential/<naam>/) — voorkomt per
  ongeluk committen zonder encryptie nodig te hebben.
- Platte tekst, geen eigen encryptie (FileVault + Laag-1-afsluiten dekt data-at-rest).
- mode 700 op ~/Confidential/ en op elk compartiment (footprint in het ingelogd-venster).
- Dit script leest of print NOOIT bron-/wiki-inhoud — alleen structuur + config.
  Het geeft uitsluitend een JSON-statusobject terug (subagent-patroon, privacy-grens).

Gebruik:
    new-compartment.py <naam>
    # → {"status": "ok", "path": "/Users/.../Confidential/<naam>", "created": [...]}

De .olw/-map wordt niet hier aangemaakt maar door olw zelf bij de eerste `olw ingest`.
"""

import json
import os
import re
import stat
import sys
from pathlib import Path

CONFIDENTIAL_ROOT = Path.home() / "Confidential"
NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")

# Per-compartiment wiki.toml — afgeleid van de persoonlijke vault/wiki.toml, met twee
# bewuste verschillen: (1) vertrouwelijkheids-header + guardrail-comment; (2) een
# gecommentarieerde hint voor een zwaarder per-compartiment model (spec punt 2 V1).
WIKI_TOML_TEMPLATE = """\
# olw / kytmanov config voor VERTROUWELIJK COMPARTIMENT: {name}
#
# Need-to-know lattice (Bell-LaPadula "no write-down"): dit is een HOOG-compartiment.
# Persoonlijk (LAAG) mag hierheen stromen; hieruit stroomt NIETS terug naar persoonlijk.
# GUARDRAIL: draai op dit compartiment NOOIT `olw maintain` of `olw lint --fix` — die
# zouden de read-only `wiki/_personal/`-context (G2) willen herschrijven.

[models]
fast = "mistral-small:22b"
heavy = "mistral-small:22b"
# fast = heavy: één geladen model → geen swap-thrash.
# Per-compartiment mag je hier een zwaarder model kiezen voor gevoelig werk
# (spec punt 2 V1); test dan eerst via `olw compare` op één cluster.

[ollama]
url = "http://localhost:11434"
timeout = 1800                    # per-request (s); ruim i.v.m. trage prefill grote context
fast_ctx = 16384
heavy_ctx = 16384                 # gelijk aan fast_ctx → geen Ollama-herlaad bij één model

[pipeline]
auto_approve = false              # olw review = menselijke kwaliteitspoort
auto_commit = false               # compartimenten zijn geen git-repo → nooit zelf committen
auto_maintain = false             # dekt de maintain-guardrail voor de auto-modus
watch_debounce = 3.0
max_concepts_per_source = 8
ingest_parallel = false
article_max_tokens = 16384
graph_quality_checks = true
# language = "en"  # unset = auto per artikel
"""

COMPARTMENT_MEMO = """\
# Compartiment: {name}

> Vertrouwelijk compartiment (Fase G — need-to-know lattice). **Buiten de git-repo.**

## Lattice-regels (niet onderhandelbaar)

- **No write-down.** Persoonlijk (LAAG) → dit compartiment (HOOG) is toegestaan; uit dit
  compartiment stroomt **niets** terug naar de persoonlijke vault. De scheiding is
  structureel (fysiek gescheiden vault + state), niet policy-based.
- **Nooit `olw maintain` of `olw lint --fix`** op dit compartiment — die willen de
  read-only `wiki/_personal/`-context (G2) herschrijven.
- **Privacy-grens.** Vertrouwelijke bron- én afgeleide inhoud komt nooit als tool-output
  in Claude's context. Alle operaties via lokale subagents (olw, build-zotero-bundle);
  het sync-/hardlink-script (G2) doet geen `cat`/`print` op inhoud.
- **Één uitzonderingsklep:** `promote-to-wiki` (G3) = de enige toegestane neerwaartse
  stroom, handmatig + bewust ontgevoeligd (algemene methode wél, klant-data niet).

## Structuur

- `raw/`   — olw-invoerlaag (Zotero-bundels + `raw/notes/` van dit compartiment)
- `wiki/`  — olw-uitvoer; `wiki/_personal/` (G2) = read-only hardlink-farm van persoonlijk
- `.olw/`  — per-vault state (door olw aangemaakt bij eerste ingest)

Backup: Proton Route A (G5), **niet** "Available Offline" gepind (dormant = placeholder).
"""


def fail(message):
    print(json.dumps({"status": "error", "error": message}))
    sys.exit(1)


def inside_git_repo(path):
    """Loop omhoog vanaf path; return het eerste .git-bevattende pad, of None."""
    for parent in [path, *path.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def chmod_700(path):
    path.chmod(stat.S_IRWXU)  # 0o700


def main():
    if len(sys.argv) != 2:
        fail("gebruik: new-compartment.py <naam>")

    name = sys.argv[1].strip()
    if not NAME_RE.match(name):
        fail(f"ongeldige naam {name!r}: alleen letters, cijfers, '-' en '_' toegestaan")

    target = CONFIDENTIAL_ROOT / name

    # Guardrail 1: geen clobber.
    if target.exists():
        fail(f"compartiment bestaat al: {target}")

    # Guardrail 2: nooit binnen een git-repo aanmaken (spec: buiten de git-repo).
    repo = inside_git_repo(CONFIDENTIAL_ROOT)
    if repo is not None:
        fail(f"weigering: {CONFIDENTIAL_ROOT} valt binnen een git-repo ({repo}) — "
             "compartimenten horen buiten versiebeheer")

    created = []

    # ~/Confidential/ zelf (mode 700).
    if not CONFIDENTIAL_ROOT.exists():
        CONFIDENTIAL_ROOT.mkdir(mode=0o700)
        chmod_700(CONFIDENTIAL_ROOT)  # mkdir-mode wordt door umask gemaskeerd → forceer
        created.append(str(CONFIDENTIAL_ROOT))

    # Compartiment + submappen (mode 700).
    target.mkdir(mode=0o700)
    chmod_700(target)
    created.append(str(target))
    for sub in ("raw", "wiki"):
        d = target / sub
        d.mkdir(mode=0o700)
        chmod_700(d)
        created.append(str(d))

    # wiki.toml + guardrail-memo.
    toml_path = target / "wiki.toml"
    toml_path.write_text(WIKI_TOML_TEMPLATE.format(name=name), encoding="utf-8")
    created.append(str(toml_path))

    memo_path = target / "_COMPARTMENT.md"
    memo_path.write_text(COMPARTMENT_MEMO.format(name=name), encoding="utf-8")
    created.append(str(memo_path))

    print(json.dumps({
        "status": "ok",
        "path": str(target),
        "created": created,
        "next": "leg raw/-inhoud neer, daarna: olw ingest <bestand> --vault "
                f"{target} --fast-model mistral-small:22b",
    }))


if __name__ == "__main__":
    main()
