#!/usr/bin/env python3
"""
process_item.py — Privacy-preserving subagent voor ResearchVault.

Neemt een Zotero item key en metadata, haalt de volledige tekst lokaal op,
genereert een gestructureerde literatuurnotitie via Qwen3.5:9b (Ollama),
schrijft het .md-bestand naar literature/ en retourneert een JSON-statusobject.

Gebruik:
    python3 .claude/process_item.py \
        --item-key ITEMKEY \
        --title "Volledige titel" \
        --authors "Achternaam, Voornaam" \
        --year 2024 \
        --journal "Journal of X" \
        --citation-key auteur2024kernwoord \
        --zotero-url "zotero://select/library/1/items/ITEMKEY" \
        --tags "beleid" --tags "zorg" \
        [--status read|unread]

Optioneel: geef metadata als JSON-string via --meta-json voor eenvoudige
aanroep vanuit Claude Code:
    python3 .claude/process_item.py \
        --item-key ITEMKEY \
        --meta-json '{"title": "...", "authors": [...], "year": 2024, ...}'

Output (stdout, JSON):
    {"status": "ok", "path": "literature/auteur2024kernwoord.md"}
    {"status": "error", "message": "..."}

Geen bron-inhoud wordt als output teruggegeven — alleen het statusobject.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# ── Padconfiguratie ───────────────────────────────────────────────────────────

VAULT_ROOT   = Path(__file__).resolve().parent.parent.parent   # ResearchVault/
CLAUDE_DIR   = VAULT_ROOT / ".claude"
PYTHON       = Path(
    os.environ.get(
        "ZOTERO_PYTHON",
        "/Users/pietstam/.local/share/uv/tools/zotero-mcp-server/bin/python3",
    )
)
FETCH_SCRIPT    = CLAUDE_DIR / "fetch-fulltext.py"
GENERATE_SCRIPT = CLAUDE_DIR / "ollama-generate.py"
LITERATURE_DIR  = VAULT_ROOT / "literature"
INBOX_DIR       = VAULT_ROOT / "inbox"

# ── Ollama-prompt ─────────────────────────────────────────────────────────────

LITERATURE_NOTE_PROMPT = """\
You are a research assistant writing structured literature notes for an Obsidian vault \
on health economics and related fields.

Your task: write a literature note for the source text below.

Rules:
- Write in the SAME LANGUAGE as the source text (English source → English note; \
Dutch source → Dutch note).
- Do NOT include YAML frontmatter — that is added separately.
- Use exactly these sections with these Markdown headings (translate the heading \
names to the language of the note):

## Core question and main argument
One paragraph: what question does this work address, and what is the central claim?

## Key findings
3 to 5 bullet points with the most important empirical or theoretical results.

## Methodological notes
Brief description of methods, data, study design, or theoretical framework.

## Relevant quotes
2 to 4 direct quotes that are most relevant to health economics research. \
Keep quotes in the ORIGINAL language of the source, with a page or timestamp \
reference where available.

## Links to related notes
Placeholder: [[related note 1]], [[related note 2]] — Claude Code will fill these in.

Write concisely and precisely. No preamble, no closing remarks.\
"""

# ── Hulpfuncties ──────────────────────────────────────────────────────────────

def ok(path: str) -> None:
    print(json.dumps({"status": "ok", "path": path}, ensure_ascii=False))


def error(message: str) -> None:
    print(json.dumps({"status": "error", "message": message}, ensure_ascii=False))
    sys.exit(1)


def slugify(text: str) -> str:
    """Zet tekst om naar een bestandsnaam-veilige slug (lowercase, koppeltekens)."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:40].strip("-")


def build_filename(citation_key: str, authors: list[str], year: str, title: str) -> str:
    """Bepaal de bestandsnaam voor de literatuurnotitie."""
    if citation_key:
        return f"{citation_key}.md"
    # Auto-genereer: eerste achternaam + jaar + eerste kernwoord titel
    last_name = ""
    if authors:
        # Formaat "Achternaam, Voornaam" of "Voornaam Achternaam"
        first = authors[0]
        if "," in first:
            last_name = slugify(first.split(",")[0])
        else:
            last_name = slugify(first.split()[-1])
    year_str = str(year) if year else "0000"
    # Eerste niet-stopwoord uit de titel
    stop = {"a", "an", "the", "de", "het", "een", "van", "of", "and", "en", "in", "op"}
    words = [w for w in re.split(r"\W+", title.lower()) if w and w not in stop]
    keyword = slugify(words[0]) if words else "item"
    parts = [p for p in [last_name, year_str, keyword] if p]
    return "-".join(parts) + ".md"


def build_frontmatter(
    title: str,
    authors: list[str],
    year: str | int,
    journal: str,
    citation_key: str,
    item_key: str,
    zotero_url: str,
    tags: list[str],
    status: str,
) -> str:
    """Bouw de YAML frontmatter voor een literatuurnotitie."""
    # Verwijder eventuele # uit tags (CLAUDE.md: tags zónder #)
    clean_tags = [t.lstrip("#") for t in tags] if tags else []
    tags_yaml = "[" + ", ".join(clean_tags) + "]" if clean_tags else "[]"

    # Auteurs als YAML-lijst
    authors_yaml = (
        "[" + ", ".join(f'"{a}"' for a in authors) + "]"
        if authors else "[]"
    )

    # Zotero-URL: gebruik opgegeven URL of bouw hem op uit de item key
    zotero_link = zotero_url or f"zotero://select/library/1/items/{item_key}"

    lines = [
        "---",
        f'title: "{title}"',
        f"authors: {authors_yaml}",
        f"year: {year or 'null'}",
        f'journal: "{journal or ""}"',
        f"citation_key: {citation_key or ''}",
        f'zotero: "{zotero_link}"',
        f"tags: {tags_yaml}",
        f"status: {status}",
        "---",
        "",
    ]
    return "\n".join(lines)


def run(cmd: list[str | Path], description: str) -> subprocess.CompletedProcess:
    """Voer een subproces uit; schrijf fouten naar stderr en sluit af bij mislukking."""
    result = subprocess.run(
        [str(c) for c in cmd],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        msg = f"{description} mislukt (exit {result.returncode}): {result.stderr.strip()}"
        error(msg)
    return result


# ── Hoofdprogramma ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Privacy-preserving subagent: Zotero item → Obsidian literatuurnotitie"
    )
    parser.add_argument("--item-key", required=True, help="Zotero item key")
    parser.add_argument("--meta-json", help="Volledige metadata als JSON-string (vervangt losse vlaggen)")
    parser.add_argument("--title",        default="")
    parser.add_argument("--authors",      action="append", default=[])
    parser.add_argument("--year",         default="")
    parser.add_argument("--journal",      default="")
    parser.add_argument("--citation-key", default="")
    parser.add_argument("--zotero-url",   default="")
    parser.add_argument("--tags",         action="append", default=[])
    parser.add_argument("--status",       default="unread", choices=["read", "unread"])
    parser.add_argument("--model",        default="qwen3.5:9b")
    parser.add_argument("--keep-temp",    action="store_true",
                        help="Verwijder tijdelijk inbox-bestand NIET na afronding")
    args = parser.parse_args()

    # ── Metadata samenvoegen ──────────────────────────────────────────────────
    meta: dict = {}
    if args.meta_json:
        try:
            meta = json.loads(args.meta_json)
        except json.JSONDecodeError as exc:
            error(f"Ongeldige --meta-json: {exc}")

    item_key     = args.item_key
    title        = meta.get("title",        args.title)
    authors      = meta.get("authors",      args.authors or [])
    year         = meta.get("year",         args.year)
    journal      = meta.get("journal",      args.journal)
    citation_key = meta.get("citation_key", args.citation_key)
    zotero_url   = meta.get("zotero_url",   args.zotero_url)
    tags         = meta.get("tags",         args.tags or [])
    status       = meta.get("status",       args.status)
    model        = args.model

    if not title:
        error("--title is verplicht (of geef het mee via --meta-json)")

    # ── Bestandsnamen bepalen ─────────────────────────────────────────────────
    filename = build_filename(citation_key, authors, str(year), title)
    temp_input  = INBOX_DIR / f"_tmp_{item_key}.txt"
    output_path = LITERATURE_DIR / filename

    # Zorg dat mappen bestaan
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    LITERATURE_DIR.mkdir(parents=True, exist_ok=True)

    # ── Stap 1: Volledige tekst ophalen ───────────────────────────────────────
    print(f"[1/4] Volledige tekst ophalen voor {item_key}…", file=sys.stderr)
    run(
        [PYTHON, FETCH_SCRIPT, item_key, str(temp_input)],
        "fetch-fulltext",
    )

    # Controleer dat het bestand er is en niet leeg is
    if not temp_input.exists() or temp_input.stat().st_size == 0:
        error(f"Tijdelijk invoerbestand is leeg of ontbreekt: {temp_input}")

    # ── Stap 2: Literatuurnotitie genereren via Qwen3.5:9b ────────────────────
    # Schrijf de note-body naar een tijdelijk uitvoerbestand; frontmatter
    # voegen we daarna toe zodat Qwen er nooit mee wordt belast.
    temp_output = LITERATURE_DIR / f"_tmp_{item_key}.md"
    print(f"[2/4] Notitie genereren via {model}…", file=sys.stderr)
    run(
        [
            PYTHON, GENERATE_SCRIPT,
            "--input",  str(temp_input),
            "--output", str(temp_output),
            "--prompt", LITERATURE_NOTE_PROMPT,
            "--model",  model,
        ],
        "ollama-generate",
    )

    # ── Stap 3: Frontmatter prependen ─────────────────────────────────────────
    print("[3/4] Frontmatter toevoegen…", file=sys.stderr)
    body = temp_output.read_text(encoding="utf-8")
    frontmatter = build_frontmatter(
        title=title,
        authors=authors,
        year=year,
        journal=journal,
        citation_key=citation_key,
        item_key=item_key,
        zotero_url=zotero_url,
        tags=tags,
        status=status,
    )
    output_path.write_text(frontmatter + body, encoding="utf-8")
    temp_output.unlink(missing_ok=True)

    # ── Stap 4: Opruimen ──────────────────────────────────────────────────────
    print("[4/4] Tijdelijke bestanden verwijderen…", file=sys.stderr)
    if not args.keep_temp:
        temp_input.unlink(missing_ok=True)

    # ── Statusoutput (JSON) ───────────────────────────────────────────────────
    relative = str(output_path.relative_to(VAULT_ROOT))
    ok(relative)


if __name__ == "__main__":
    main()
