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
import urllib.request
from pathlib import Path

# ── Padconfiguratie ───────────────────────────────────────────────────────────

VAULT_ROOT   = Path(__file__).resolve().parent.parent   # ResearchVault/
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

_LITERATURE_NOTE_PROMPT_TEMPLATE = """\
You are a research assistant writing structured literature notes for an Obsidian vault \
on health economics and related fields.

Your task: write a literature note for the source text below.

Rules:
- Write the entire note in the SAME LANGUAGE as the source text: \
  English source → English note; Dutch source → Dutch note.
- Translate the section headings below to match the language of the source text.
- Do NOT include YAML frontmatter — that is added separately.

## TLDR
One short paragraph (2-3 sentences): what question does this work address, and what is the central claim? \
Used by the LLM to decide whether the full note needs to be read.

## Key findings
3 to 5 bullet points with the most important empirical or theoretical results.

## Methodological notes
Brief description of methods, data, study design, or theoretical framework.

{relevant_quotes_section}## Related notes
Placeholder: [[related note 1]], [[related note 2]] — Claude Code will fill these in.

## Flashcards

#flashcard
[Question about a key concept or finding]
?
[Short, precise answer]

Maximum 3 flashcards. Write flashcards in the SAME LANGUAGE as the note.

Write concisely and precisely. No preamble, no closing remarks.\
"""


def build_literature_note_prompt(
    citation_key: str,
    title: str,
    authors: list[str],
    year: str | int,
    journal: str,
    tags: list[str],
) -> str:
    """Bouw de dynamische Qwen-prompt voor een literatuurnotitie."""
    is_av = any(t in (tags or []) for t in ["video", "youtube", "podcast"])
    if is_av:
        relevant_quotes_section = ""
    else:
        relevant_quotes_section = (
            "## Relevant quotes\n"
            "2 to 4 direct quotes most relevant to health economics research. "
            "Always in the ORIGINAL language of the source. "
            "Include page number or timestamp reference where available.\n\n"
        )
    return _LITERATURE_NOTE_PROMPT_TEMPLATE.format(
        relevant_quotes_section=relevant_quotes_section,
    )

# ── Hulpfuncties ──────────────────────────────────────────────────────────────

def ok(path: str) -> None:
    """Niet meer direct gebruikt — zie main() voor de uitgebreide JSON-output."""
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
    """Bepaal de bestandsnaam voor de literatuurnotitie.

    Altijd formaat: achternaam-jaar-kernwoord.md (met koppeltekens).
    De citation_key is metadata in de frontmatter, niet de bestandsnaam.
    """
    # Altijd auto-genereren: eerste achternaam + jaar + eerste kernwoord titel
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
    stop = {"a", "an", "the", "this", "that", "these", "those", "de", "het", "een", "dit", "dat", "van", "of", "and", "en", "in", "op"}
    words = [w for w in re.split(r"\W+", title.lower()) if w and w not in stop]
    keyword = slugify(words[0]) if words else "item"
    parts = [p for p in [last_name, year_str, keyword] if p]
    return "-".join(parts) + ".md"


def generate_filename_keywords(title: str, tldr: str, model: str) -> str:
    """Vraag Qwen om 2-4 zelfstandige naamwoorden voor de bestandsnaam.

    Primair op basis van de titel; TLDR als aanvullende context.
    Geeft een koppelteken-gescheiden string terug, bijv. 'mcp-consensus-onderzoek'.
    Bij mislukking: lege string (fallback naar build_filename).
    """
    source = f"Title: {title}"
    if tldr:
        source += f"\nTLDR: {tldr[:400]}"

    prompt = (
        "/no_think\n"
        "Output exactly 2 to 4 nouns (lowercase, space-separated) that best capture "
        "the topic of this source for use as filename keywords. "
        "Use the SAME language as the title "
        "(English title → English nouns; Dutch title → Dutch nouns). "
        "Output ONLY the nouns, no explanation, no punctuation.\n\n"
        + source
    )

    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = json.loads(resp.read()).get("response", "").strip().lower()
            words = [slugify(w) for w in re.split(r"[\s,;]+", raw) if w]
            words = [w for w in words if len(w) > 1][:4]
            return "-".join(words)
    except Exception as _e:
        print(f"  Bestandsnaam-keywords ophalen mislukt: {_e}", file=sys.stderr)
        return ""


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
    zotero_link = zotero_url or f"zotero://select/library/items/{item_key}"

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


def extract_frontmatter_tags(content: str) -> list[str]:
    """Extraheer tags uit YAML frontmatter van een Obsidian-note."""
    m = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return []
    tags_m = re.search(r"^tags:\s*\[([^\]]*)\]", m.group(1), re.MULTILINE)
    if not tags_m:
        return []
    return [t.strip().strip("\"'") for t in tags_m.group(1).split(",") if t.strip()]


def extract_section(content: str, heading: str) -> str:
    """Extraheer een sectie uit een Markdown-note op basis van de koptekst."""
    m = re.search(
        rf"##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##|\Z)",
        content, re.DOTALL | re.IGNORECASE,
    )
    return m.group(1).strip() if m else ""


def suggest_craft_update(
    lit_note_path: Path,
    lit_tags: list[str],
    lit_title: str,
    vault_root: Path,
    item_key: str,
    model: str,
) -> str | None:
    """
    Zoek craft-notes met overlappende tags en vraag Qwen om een updatevoorstel.

    Schrijft het voorstel naar inbox/_craft_suggestion_<item_key>.md.
    Geeft het pad terug, of None als er geen relevante match is.
    Geen bron-inhoud bereikt Claude Code — alleen het pad wordt teruggegeven.
    """
    craft_dir = vault_root / "craft"
    if not craft_dir.exists():
        return None

    # Verzamel craft-notes met overlappende tags
    matches: list[tuple[Path, set[str]]] = []
    for subdir in ("dev", "methods"):
        d = craft_dir / subdir
        if not d.exists():
            continue
        for f in sorted(d.glob("*.md")):
            craft_tags = set(extract_frontmatter_tags(f.read_text(encoding="utf-8")))
            overlap = set(lit_tags) & craft_tags
            if overlap:
                matches.append((f, overlap))

    if not matches:
        print("  [craft] Geen overlappende craft-notes gevonden.", file=sys.stderr)
        return None

    # Neem de top-3 op aantal overlappende tags
    matches.sort(key=lambda x: len(x[1]), reverse=True)
    top = matches[:3]

    # Lees relevante secties uit de literatuurnotitie (niet de volledige tekst)
    lit_content = lit_note_path.read_text(encoding="utf-8")
    tldr = extract_section(lit_content, "TLDR") or extract_section(lit_content, "Kernvraag en hoofdargument")
    findings = extract_section(lit_content, "Key findings") or extract_section(lit_content, "Kernbevindingen")

    suggestions: list[str] = []
    for craft_path, overlap in top:
        craft_content = craft_path.read_text(encoding="utf-8")
        craft_title_m = re.search(r'^title:\s*"?(.+?)"?\s*$', craft_content, re.MULTILINE)
        craft_title = craft_title_m.group(1) if craft_title_m else craft_path.stem
        # Lees de meest relevante sectie (Hoe / Implementatie / Wanneer gebruiken)
        craft_body = (
            extract_section(craft_content, "Hoe")
            or extract_section(craft_content, "Implementatie")
            or extract_section(craft_content, "Wanneer gebruiken")
        )

        prompt = (
            f'Nieuwe literatuurnotitie: "{lit_title}"\n\n'
            f"TLDR: {tldr[:400]}\n\n"
            f"Kernbevindingen: {findings[:400]}\n\n"
            f'Bestaande craft-note: "{craft_title}"\n'
            f"Overlappende tags: {', '.join(overlap)}\n"
            f"Huidige inhoud (fragment):\n{craft_body[:600]}\n\n"
            "Taak: beschrijf in 3-5 Nederlandse zinnen welke nieuwe inzichten uit "
            "de literatuurnotitie toegevoegd kunnen worden aan de craft-note. "
            "Wees specifiek: welke sectie, wat precies toevoegen. "
            'Als er niets nuttigs toe te voegen is, schrijf dan alleen: "Geen aanvulling nodig."'
        )
        payload = json.dumps({
            "model": model,
            "prompt": prompt,
            "think": False,
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 300},
        }).encode("utf-8")
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                suggestion_text = json.loads(resp.read()).get("response", "").strip()
        except Exception as e:
            print(f"  [craft] Qwen-aanroep mislukt voor {craft_path.name}: {e}", file=sys.stderr)
            suggestion_text = "(fout bij genereren suggestie)"

        suggestions.append(
            f"### [[craft/{craft_path.parent.name}/{craft_path.stem}]]\n"
            f"**Overlappende tags:** {', '.join(sorted(overlap))}\n\n"
            f"{suggestion_text}\n"
        )

    # Schrijf alle suggesties naar één bestand in inbox/
    suggestion_path = vault_root / "inbox" / f"_craft_suggestion_{item_key}.md"
    header = (
        f"# Craft-update suggesties voor: {lit_title}\n\n"
        f"> Gegenereerd door process_item.py op basis van tag-overlap.\n"
        f"> Beoordeeld door Qwen ({model}). Pas handmatig toe of negeer.\n\n"
    )
    suggestion_path.write_text(header + "\n---\n\n".join(suggestions), encoding="utf-8")
    print(f"  [craft] Suggestie geschreven: {suggestion_path.name}", file=sys.stderr)
    return str(suggestion_path.relative_to(vault_root))


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
    parser.add_argument("--output-dir",   default=None,
                        help="Uitvoermap voor de notitie (standaard: literature/). "
                             "Gebruik 'meta/candidates/' voor de candidate buffer.")
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

    # ── Citation key ophalen uit Zotero als niet meegegeven ──────────────────
    if not citation_key:
        try:
            if not os.environ.get("ZOTERO_API_KEY"):
                env_file = VAULT_ROOT / ".env"
                if env_file.exists():
                    from dotenv import load_dotenv
                    load_dotenv(env_file)
            from zotero_mcp.server import get_zotero_client
            _client = get_zotero_client()
            _data = _client.item(item_key).get("data", {})
            citation_key = _data.get("citationKey", "")
            if citation_key:
                print(f"  Citation key uit Zotero: {citation_key}", file=sys.stderr)
        except Exception as _e:
            print(f"  Zotero metadata ophalen mislukt: {_e}", file=sys.stderr)
    tags         = meta.get("tags",         args.tags or [])
    status       = meta.get("status",       args.status)
    model        = args.model

    if not title:
        error("--title is verplicht (of geef het mee via --meta-json)")

    # ── Uitvoermap bepalen ────────────────────────────────────────────────────
    temp_input = INBOX_DIR / f"_tmp_{item_key}.txt"
    if args.output_dir:
        output_dir = VAULT_ROOT / args.output_dir
    else:
        output_dir = LITERATURE_DIR

    # Zorg dat mappen bestaan
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

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
    temp_output = output_dir / f"_tmp_{item_key}.md"
    print(f"[2/4] Notitie genereren via {model}…", file=sys.stderr)
    prompt = build_literature_note_prompt(
        citation_key=citation_key,
        title=title,
        authors=authors,
        year=year,
        journal=journal,
        tags=tags,
    )
    run(
        [
            PYTHON, GENERATE_SCRIPT,
            "--input",  str(temp_input),
            "--output", str(temp_output),
            "--prompt", prompt,
            "--model",  model,
        ],
        "ollama-generate",
    )

    # ── Bestandsnaam bepalen op basis van gegenereerde notitie ────────────────
    body = temp_output.read_text(encoding="utf-8")
    tldr_match = re.search(r"##\s+TLDR\s*\n(.*?)(?=\n##|\Z)", body, re.DOTALL | re.IGNORECASE)
    tldr = tldr_match.group(1).strip() if tldr_match else ""
    print("[2b] Bestandsnaam bepalen via Qwen…", file=sys.stderr)
    keywords = generate_filename_keywords(title, tldr, model)
    if keywords:
        last_name = ""
        if authors:
            first = authors[0]
            last_name = slugify(first.split(",")[0] if "," in first else first.split()[-1])
        filename = "-".join(p for p in [last_name, str(year) if year else "0000", keywords] if p) + ".md"
    else:
        filename = build_filename(citation_key, authors, str(year), title)
    output_path = output_dir / filename

    # ── Stap 3: Frontmatter prependen ─────────────────────────────────────────
    print("[3/4] Frontmatter toevoegen…", file=sys.stderr)
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

    # ── Stap 5: Craft-update suggestie ───────────────────────────────────────
    print("[5/5] Craft-notes scannen op overlappende tags…", file=sys.stderr)
    craft_suggestion = suggest_craft_update(
        lit_note_path=output_path,
        lit_tags=tags,
        lit_title=title,
        vault_root=VAULT_ROOT,
        item_key=item_key,
        model=model,
    )

    # ── Statusoutput (JSON) ───────────────────────────────────────────────────
    relative = str(output_path.relative_to(VAULT_ROOT))
    result: dict = {"status": "ok", "path": relative}
    if craft_suggestion:
        result["craft_suggestion"] = craft_suggestion
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
