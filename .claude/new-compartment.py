#!/usr/bin/env python3
"""new-compartment.py — Fase G/G1: scaffolding voor een vertrouwelijk compartiment.

Maakt één geïsoleerde, volwaardige workspace-vault per compartiment (need-to-know lattice,
Bell-LaPadula "no write-down"). Elk compartiment is een op zichzelf staande Obsidian-vault
met eigen raw/, wiki/, authoring/, .obsidian/, wiki.toml en (na de eerste ingest)
.olw/state.db — fysiek gescheiden van de persoonlijke ResearchVault-vault én van elkaar.
Parallel aan de persoonlijke vault, maar Obsidian-Mac-only (nooit naar mobiel gesynct).

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

De .olw/-map wordt hier voorgemaakt op mode 700 (G4) zodat olw de state (state.db/chroma)
er bij de eerste ingest in schrijft zonder hem op 755 aan te maken.
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

> Vertrouwelijk compartiment (Fase G — need-to-know lattice). Volwaardige workspace-vault,
> **buiten de git-repo**, mode 700. Parallel aan de persoonlijke ResearchVault-vault.

## Lattice-regels (niet onderhandelbaar)

- **No write-down.** Persoonlijk (LAAG) → dit compartiment (HOOG) is toegestaan; uit dit
  compartiment stroomt **niets** terug naar de persoonlijke vault. De scheiding is
  structureel (fysiek gescheiden vault + state), niet policy-based.
- **Nooit `olw maintain` of `olw lint --fix`** op dit compartiment — die willen de
  read-only `wiki/_personal/`-referentie herschrijven. (Netheid, GÉÉN veiligheidsgrens: de
  klonen isoleren personal via eigen inode, dus een per ongeluk uitgevoerde maintain lekt niet
  naar personal; `sync-personal-wiki-ref` herbouwt de subtree schoon.)
- **Privacy-grens (As B).** Vertrouwelijke bron- én afgeleide inhoud komt nooit als
  tool-output in Claude's context. Alle olw-operaties via lokale subagents; de sync-scripts
  doen geen `cat`/`print` op inhoud. **Agent-grens voor authoring is nog OPEN** — Claude/
  Anthropic mag vertrouwelijke inhoud niet lezen, dus confidential authoring vereist t.z.t.
  lokale agents (Ollama). Tot dat besluit valt: geen Anthropic-agents op `authoring/`-inhoud.
- **Één uitzonderingsklep:** `promote-to-wiki` (G3) = de enige toegestane neerwaartse
  stroom, handmatig + bewust ontgevoeligd (algemene methode wél, klant-data niet).

## Structuur (volwaardige workspace-vault)

- `raw/`        — olw-invoerlaag (Zotero-bundels + `raw/notes/` + `raw/_personal-context/`
                  = G2-A synthese-bron: kopieën van persoonlijke wiki-kennis, gemarkeerd)
- `wiki/`       — olw-uitvoer; `wiki/_personal/` (G2-B) = read-only **APFS-klonen** van de
                  persoonlijke wiki, zodat Obsidian-`[[links]]`/backlinks ernaartoe resolveren
- `authoring/`  — vertrouwelijke projecten/rapporten. **ECHTE map, GEEN symlink naar myfiles/**
                  en **nooit naar Syncthing/iPad** — anders lekt vertrouwelijk werk de LAAG-sync in
- `.obsidian/`  — Obsidian opent dit als vault. **Mac-only**: compartimenten worden nooit naar
                  mobiel gesynct; op iPad/iPhone alleen via de thin-client (:8766, G6) als HTML
- `.olw/`       — per-vault state (state.db/chroma). **Voorgemaakt op mode 700** (G4) zodat de
                  afgeleide concepten afgeschermd zijn; olw schrijft de state hierin bij ingest

## Operationeel

- **Laag-1 idle-shutdown dekt compartiment-werk al:** olw-runs op dit compartiment
  (`ingest`/`compile`/`review`) worden gevangen door de idle-shutdown-guards #6/#7 (die matchen
  het olw-proces, ongeacht `--vault`) → de Mac sluit niet af midden in een run. Obsidian-bewerken
  is HID-gedreven (actief = wakker, wegstappen = afsluiten — precies de "dicht als ik weg ben"-bedoeling).

## Backup & Proton-sync (G5 — nog te bouwen)

Proton Route A, **niet** "Available Offline" gepind (dormant = placeholder). Twee noten om
NIET te vergeten bij het inrichten:

- **Mobiel-lek-discipline.** Proton-sync opent een tweede kanaal naar mobiel náást de thin-client
  (:8766). De confidential Proton-categorie **niet** op iPhone/iPad-Proton-apps synchroniseren/openen
  — anders landt vertrouwelijke inhoud op mobiel, tegen de thin-client-only-keuze in. iPad-toegang
  blijft uitsluitend de thin-client.
- **Per-compartiment regelgeving-check.** Het model (platte tekst + FileVault + Laag-1 + Proton-E2E)
  rust op de aanname "geen formele contract-eisen". Compartimenten met gereguleerde/privacygevoelige
  data kunnen formele data-handling-eisen hebben die dit niet dekt →
  **check de data-handling-regels vóór je dit compartiment naar Proton synct.**
- **Sync alleen het niet-regenereerbare deel:** `raw/`, `authoring/`, `wiki.toml`, dit bestand
  (+ evt. `.olw/state.db`); sla `wiki/` en `wiki/_personal/` over (regenereerbaar via olw resp. re-sync).
"""

# .obsidian/app.json — alleen de link-instelling; Obsidian genereert de rest (kern-plugins AAN)
# bij de eerste keer openen. Een kale core-plugins.json zou file-explorer/backlinks/graph juist
# uitzetten, dus die schrijven we bewust NIET.
OBSIDIAN_APP = {"alwaysUpdateLinks": True}


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

    # Compartiment + submappen (mode 700). authoring/ = vertrouwelijke projecten/rapporten
    # (echte map, GEEN symlink naar myfiles/ — dat zou vertrouwelijk werk in de persoonlijke
    # Proton-sync trekken). Volwaardige workspace-vault, parallel aan de persoonlijke vault.
    target.mkdir(mode=0o700)
    chmod_700(target)
    created.append(str(target))
    for sub in ("raw", "wiki", "authoring"):
        d = target / sub
        d.mkdir(mode=0o700)
        chmod_700(d)
        created.append(str(d))

    # .obsidian/ zodat Obsidian de map als vault opent (Mac-only; compartimenten worden
    # nooit naar mobiel gesynct). Alleen app.json met de link-instelling; Obsidian genereert
    # de rest met defaults (kern-plugins AAN) bij de eerste keer openen — een kale
    # core-plugins.json zou die juist uitzetten.
    obs_dir = target / ".obsidian"
    obs_dir.mkdir(mode=0o700)
    chmod_700(obs_dir)
    (obs_dir / "app.json").write_text(json.dumps(OBSIDIAN_APP, indent=2) + "\n", encoding="utf-8")
    created.append(str(obs_dir))

    # .olw/ vooraf op mode 700 (G4-hardening) zodat olw de state-map niet bij de eerste ingest
    # op 755 aanmaakt. olw schrijft state.db/chroma (afgeleide concepten) hierin; de 700-map
    # schermt die af. olw tolereert een bestaande lege .olw/ (het forceert geen eigen init).
    olw_dir = target / ".olw"
    olw_dir.mkdir(mode=0o700)
    chmod_700(olw_dir)
    created.append(str(olw_dir))

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
