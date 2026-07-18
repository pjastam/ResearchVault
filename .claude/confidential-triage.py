#!/usr/bin/env python3
"""
confidential-triage.py — Vlag vertrouwelijke notities en verplaats ze naar een compartiment.

De ontbrekende INKOMENDE classificatiestap (personal LAAG → compartiment HOOG) van de
Fase-G-lattice. Twee subcommando's:

    scan   Read-only. Scant een notitie-boom tegen een LOKALE seed-config (per organisatie
           een lijst zoektermen) en schrijft een vlag-rapport naar een lokaal bestand.
           Verplaatst niets. Stdout = alleen een JSON-statusobject met tellingen.

    move   Verplaatst de door jou BEVESTIGDE notities (+ hun co-located bijlagen) naar
           ~/Confidential/<org>/authoring/notes/, met behoud van de relatieve mapstructuur
           en een omkeerbaar move-manifest. Dry-run is de default; --apply voert echt uit.

Gebruik:
    python3 .claude/confidential-triage.py scan  [--root PAD] [--seeds PAD] [--report PAD]
    python3 .claude/confidential-triage.py move  --org NAAM --manifest PAD [--root PAD] [--apply]

PRIVACY (niet-onderhandelbaar): dit script leest notitie-inhoud UITSLUITEND lokaal en print
die NOOIT. Stdout bevat alleen een JSON-statusobject (tellingen + paden). Het vlag-rapport is
een lokaal bestand; de "gematchte termen" die het toont komen uit jóuw seed-config, niet uit de
notitie-inhoud. Ontwikkeld + getest met synthetische data.

Het script bevat GEEN hardcoded organisatienamen — die staan uitsluitend in de lokale
seed-config (die klanten noemt en dus NOOIT in de repo hoort). Het script zelf is generiek.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

# ── Padconfiguratie ───────────────────────────────────────────────────────────

VAULT_ROOT       = Path(__file__).resolve().parent.parent
VAULT_DIR        = VAULT_ROOT / "vault"
DEFAULT_ROOT     = VAULT_DIR / "authoring" / "notes"        # symlink → Proton/Notes
# Compartiment-root: productie = ~/Confidential; overschrijfbaar via env (alleen voor tests).
CONFIDENTIAL_ROOT = Path(os.environ.get("TRIAGE_CONFIDENTIAL_ROOT",
                                        str(Path.home() / "Confidential"))).expanduser()
DEFAULT_SEEDS    = CONFIDENTIAL_ROOT / "_triage-seeds.toml"
DEFAULT_REPORT   = VAULT_DIR / ".cache" / "_confidential-scan.md"

ORG_NAME_RE      = re.compile(r"^[A-Za-z0-9_-]+$")
ASSET_EXTS       = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".pdf",
                    ".xlsx", ".xlsm", ".csv", ".docx", ".pptx"}
# Sterk-drempel: bestandsnaam-treffer, of ≥2 distincte termen, of ≥3 body-treffers.
STRONG_BODY_HITS   = 3
FILENAME_WEIGHT    = 5


def _stderr(msg: str) -> None:
    print(msg, file=sys.stderr)


def _ok(**fields) -> None:
    print(json.dumps({"status": "ok", **fields}, ensure_ascii=False))
    sys.exit(0)


def _error(msg: str, **extra) -> None:
    print(json.dumps({"status": "error", "message": msg, **extra}, ensure_ascii=False))
    sys.exit(1)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# ── Seed-config laden ──────────────────────────────────────────────────────────

def load_seeds(path: Path) -> dict[str, list[str]]:
    """Leest de TOML-seed-config: één tabel per organisatie met een `terms`-lijst.

        [Talma]
        terms = ["Talma", "Talma Instituut", "Prikkels in de Zorg"]
    """
    if not path.is_file():
        _error(f"seed-config niet gevonden: {path}. Kopieer het sjabloon en vul termen in.")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        _error(f"seed-config niet leesbaar (TOML-fout): {exc}")

    seeds: dict[str, list[str]] = {}
    for org, table in data.items():
        if not ORG_NAME_RE.match(org):
            _error(f"ongeldige org-naam '{org}' (alleen letters/cijfers/_/-).")
        terms = table.get("terms") if isinstance(table, dict) else None
        if not isinstance(terms, list) or not all(isinstance(t, str) for t in terms):
            _error(f"[{org}] mist een geldige `terms`-lijst van strings.")
        cleaned = [t.strip() for t in terms if t.strip()]
        if cleaned:
            seeds[org] = cleaned
    if not seeds:
        _error("seed-config bevat geen bruikbare organisaties/termen.")
    return seeds


def compile_matchers(seeds: dict[str, list[str]]) -> dict[str, list[tuple[str, re.Pattern]]]:
    """Bouwt per org een lijst (term, gecompileerde case-insensitive regex). Termen die met
    een woordkarakter beginnen/eindigen krijgen \\b-grenzen (heel-woord); overige worden
    letterlijk gezocht."""
    matchers: dict[str, list[tuple[str, re.Pattern]]] = {}
    for org, terms in seeds.items():
        compiled = []
        for term in terms:
            esc = re.escape(term)
            left = r"\b" if term[:1].isalnum() else ""
            right = r"\b" if term[-1:].isalnum() else ""
            compiled.append((term, re.compile(f"{left}{esc}{right}", re.IGNORECASE)))
        matchers[org] = compiled
    return matchers


# ── SCAN ───────────────────────────────────────────────────────────────────────

def scan_note(text: str, stem: str,
              matchers: dict[str, list[tuple[str, re.Pattern]]]) -> dict[str, dict]:
    """Scant één notitie. Retourneert per gematchte org: {terms: {term: count},
    body_hits, filename_hits, distinct_terms, score, tier}. GEEN inhoud in de output."""
    result: dict[str, dict] = {}
    for org, compiled in matchers.items():
        term_counts: dict[str, int] = {}
        filename_hits = 0
        for term, rx in compiled:
            body_n = len(rx.findall(text))
            fn_n = len(rx.findall(stem))
            if body_n or fn_n:
                term_counts[term] = body_n + fn_n
            filename_hits += fn_n
        if not term_counts:
            continue
        body_hits = sum(term_counts.values()) - filename_hits
        distinct = len(term_counts)
        score = filename_hits * FILENAME_WEIGHT + body_hits
        if filename_hits or distinct >= 2 or body_hits >= STRONG_BODY_HITS:
            tier = "strong"
        else:
            tier = "medium"
        result[org] = {"terms": term_counts, "body_hits": body_hits,
                       "filename_hits": filename_hits, "distinct_terms": distinct,
                       "score": score, "tier": tier}
    return result


def cmd_scan(args) -> None:
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        _error(f"notitie-boom niet gevonden: {root}")
    seeds = load_seeds(Path(args.seeds).expanduser())
    matchers = compile_matchers(seeds)

    scanned = 0
    unreadable = 0
    # per notitie: (relpath, {org: metrics})   ·   per map: {folder: {org: [n, strong]}}
    flagged: list[tuple[str, dict]] = []
    folder_agg: dict[str, dict[str, list[int]]] = {}
    counts_per_org: dict[str, int] = {org: 0 for org in seeds}

    for path in sorted(root.rglob("*.md")):
        if not path.is_file():
            continue
        scanned += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            unreadable += 1
            continue
        hits = scan_note(text, path.stem, matchers)
        if not hits:
            continue
        rel = str(path.relative_to(root))
        flagged.append((rel, hits))
        folder = str(path.parent.relative_to(root)) or "."
        for org, m in hits.items():
            counts_per_org[org] += 1
            slot = folder_agg.setdefault(folder, {}).setdefault(org, [0, 0])
            slot[0] += 1
            if m["tier"] == "strong":
                slot[1] += 1

    report_path = Path(args.report).expanduser()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_report(report_path, root, seeds, scanned, unreadable, flagged, folder_agg, counts_per_org)

    _ok(command="scan", root=str(root), scanned=scanned, unreadable=unreadable,
        flagged_total=len(flagged), counts_per_org=counts_per_org,
        report_path=str(report_path))


def _write_report(path: Path, root: Path, seeds, scanned, unreadable,
                  flagged, folder_agg, counts_per_org) -> None:
    """Schrijft het lokale vlag-rapport (markdown). Bevat paden + gematchte SEED-termen +
    tellingen — nooit notitie-inhoud."""
    L: list[str] = []
    L.append("# Vertrouwelijkheids-scan — vlag-rapport")
    L.append("")
    L.append(f"> Gegenereerd: {_now_iso()} · root: `{root}`")
    L.append(f"> Gescand: {scanned} `.md` · gevlagd: {len(flagged)} · onleesbaar: {unreadable}")
    L.append(">")
    L.append("> **Privacy:** dit rapport toont paden + door jóu opgegeven seed-termen + "
             "tellingen; géén notitie-inhoud. Beoordeel de notitie zelf in je editor.")
    L.append("")
    L.append("Per organisatie gevlagd: " +
             " · ".join(f"**{o}**: {n}" for o, n in counts_per_org.items()))
    L.append("")

    # ── 1. Per-map aggregaat (bulk-triage) ─────────────────────────────────────
    L.append("## 1. Per-map aggregaat (triageer hele mappen eerst)")
    L.append("")
    L.append("| Map | Organisatie | #notities | #sterk |")
    L.append("| --- | --- | ---: | ---: |")
    for folder in sorted(folder_agg):
        for org in sorted(folder_agg[folder]):
            n, strong = folder_agg[folder][org]
            L.append(f"| `{folder}` | {org} | {n} | {strong} |")
    L.append("")

    # ── 2. Per-notitie ─────────────────────────────────────────────────────────
    L.append("## 2. Per-notitie (gesorteerd per org, sterkste eerst)")
    L.append("")
    by_org: dict[str, list[tuple[str, dict]]] = {org: [] for org in seeds}
    for rel, hits in flagged:
        for org, m in hits.items():
            by_org[org].append((rel, m))
    for org in seeds:
        rows = by_org[org]
        if not rows:
            continue
        rows.sort(key=lambda r: (-r[1]["score"], r[0]))
        L.append(f"### {org} ({len(rows)})")
        L.append("")
        for rel, m in rows:
            terms = ", ".join(f"{t}×{c}" for t, c in sorted(m["terms"].items(),
                                                            key=lambda x: -x[1]))
            marker = "🔴" if m["tier"] == "strong" else "🟡"
            L.append(f"- {marker} `{rel}` — score {m['score']} — termen: {terms}")
        L.append("")

    L.append("---")
    L.append("*Maak van de bevestigde regels een manifest (één relatief pad per regel, "
             "map of bestand) en draai:* `confidential-triage.py move --org <NAAM> "
             "--manifest <bestand>` *(dry-run; voeg `--apply` toe om echt te verplaatsen).*")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


# ── MOVE ─────────────────────────────────────────────────────────────────────

LOCAL_LINK_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")            # ![alt](path)
WIKI_EMBED_RE = re.compile(r"!\[\[([^\]|#]+)")                    # ![[embed]]


def find_local_assets(note: Path, root: Path) -> tuple[set[Path], int]:
    """Zoekt lokaal-gerefereerde bijlagen (afbeeldingen e.d.) in een notitie. Retourneert
    (bestaande asset-paden binnen root, aantal onopgeloste referenties). Alleen lokaal; leest
    de notitie maar print niets."""
    try:
        text = note.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return set(), 0
    targets: list[str] = []
    for m in LOCAL_LINK_RE.finditer(text):
        targets.append(m.group(1).split()[0] if m.group(1).strip() else "")
    for m in WIKI_EMBED_RE.finditer(text):
        targets.append(m.group(1).strip())

    found: set[Path] = set()
    unresolved = 0
    search_dirs = [note.parent, note.parent / "assets", note.parent / "attachments", root]
    for raw in targets:
        raw = raw.strip()
        if not raw or raw.startswith(("http://", "https://", "#", "mailto:")):
            continue
        cand = raw.split("#")[0].split("|")[0].strip()
        if not cand:
            continue
        ext = Path(cand).suffix.lower()
        if ext and ext not in ASSET_EXTS:
            continue  # link naar een andere .md e.d. — niet als bijlage meeverhuizen
        resolved = None
        # absoluut/relatief pad
        for base in (note.parent, root):
            p = (base / cand).resolve()
            if p.is_file() and _within(p, root):
                resolved = p
                break
        # kale bestandsnaam → zoek in de gebruikelijke asset-mappen
        if resolved is None and "/" not in cand:
            for d in search_dirs:
                p = (d / cand)
                if p.is_file() and _within(p.resolve(), root):
                    resolved = p.resolve()
                    break
        if resolved is None:
            unresolved += 1
        else:
            found.add(resolved)
    return found, unresolved


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def collect_move_set(manifest_paths: list[str], root: Path) -> tuple[list[Path], list[Path], int, list[str]]:
    """Verzamelt notitie- en bijlage-bestanden uit de manifest-regels (bestand of map).
    Retourneert (notes, assets, unresolved_refs, warnings)."""
    notes: set[Path] = set()
    warnings: list[str] = []
    for line in manifest_paths:
        rel = line.strip()
        if not rel or rel.startswith("#"):
            continue
        target = (root / rel).resolve()
        if not _within(target, root):
            warnings.append(f"buiten root, overgeslagen: {rel}")
            continue
        if target.is_dir():
            for p in target.rglob("*"):
                if p.is_file():
                    notes.add(p.resolve())
        elif target.is_file():
            notes.add(target.resolve())
        else:
            warnings.append(f"niet gevonden, overgeslagen: {rel}")

    md_notes = sorted(p for p in notes if p.suffix.lower() == ".md")
    other = sorted(p for p in notes if p.suffix.lower() != ".md")  # bv. hele map incl. assets
    assets: set[Path] = set(other)
    unresolved = 0
    for note in md_notes:
        found, unres = find_local_assets(note, root)
        assets |= found
        unresolved += unres
    # assets die al als 'notes' zitten niet dubbel tellen
    assets = {a for a in assets if a.suffix.lower() != ".md"}
    return md_notes, sorted(assets), unresolved, warnings


def cmd_move(args) -> None:
    org = args.org
    if not ORG_NAME_RE.match(org):
        _error(f"ongeldige org-naam '{org}' (alleen letters/cijfers/_/-).")
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        _error(f"notitie-boom niet gevonden: {root}")

    compartment = CONFIDENTIAL_ROOT / org
    if not compartment.is_dir():
        _error(f"compartiment bestaat niet: {compartment}. Draai eerst "
               f"new-compartment.py {org} (scaffold vóór verplaatsen).")
    dest_base = compartment / "authoring" / "notes"

    manifest_file = Path(args.manifest).expanduser()
    if not manifest_file.is_file():
        _error(f"manifest niet gevonden: {manifest_file}")
    lines = manifest_file.read_text(encoding="utf-8").splitlines()

    md_notes, assets, unresolved, warnings = collect_move_set(lines, root)
    all_files = md_notes + assets
    if not all_files:
        _error("manifest leverde geen te verplaatsen bestanden op.", warnings=warnings)

    # Behoud de relatieve mapstructuur onder dest (relatieve links blijven werken).
    plan = []
    for src in all_files:
        rel = src.relative_to(root)
        plan.append((src, dest_base / rel))

    if not args.apply:
        _ok(command="move", mode="dry-run", org=org, dest=str(dest_base),
            notes=len(md_notes), assets=len(assets),
            unresolved_refs=unresolved, warnings=warnings,
            note="Voeg --apply toe om echt te verplaatsen.")

    # ── Echt verplaatsen ────────────────────────────────────────────────────────
    manifest_log = compartment / ".triage-move-manifest.jsonl"
    moved = 0
    collisions = []
    ts = _now_iso()
    with open(manifest_log, "a", encoding="utf-8") as mlog:
        for src, dest in plan:
            if not src.exists():
                continue
            if dest.exists():
                collisions.append(str(dest.relative_to(dest_base)))
                continue
            dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.move(str(src), str(dest))
            mlog.write(json.dumps({"src": str(src), "dest": str(dest), "ts": ts},
                                  ensure_ascii=False) + "\n")
            moved += 1

    _ok(command="move", mode="apply", org=org, dest=str(dest_base),
        moved=moved, collisions=collisions, unresolved_refs=unresolved,
        warnings=warnings, manifest=str(manifest_log),
        reminder="Leeg daarna de Proton-prullenbak; controleer onopgeloste bijlage-refs.")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Vlag + verplaats vertrouwelijke notities.")
    sub = ap.add_subparsers(dest="command", required=True)

    ps = sub.add_parser("scan", help="Read-only: vlag notities tegen de seed-config.")
    ps.add_argument("--root", default=str(DEFAULT_ROOT), help="Notitie-boom (default authoring/notes).")
    ps.add_argument("--seeds", default=str(DEFAULT_SEEDS), help="TOML-seed-config (LOKAAL).")
    ps.add_argument("--report", default=str(DEFAULT_REPORT), help="Uitvoer-rapportpad (lokaal).")
    ps.set_defaults(func=cmd_scan)

    pm = sub.add_parser("move", help="Verplaats bevestigde notities naar een compartiment.")
    pm.add_argument("--org", required=True, help="Doel-compartiment (moet bestaan).")
    pm.add_argument("--manifest", required=True, help="Bestand: één relatief pad per regel.")
    pm.add_argument("--root", default=str(DEFAULT_ROOT), help="Notitie-boom (default authoring/notes).")
    pm.add_argument("--apply", action="store_true", help="Voer echt uit (default: dry-run).")
    pm.set_defaults(func=cmd_move)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
