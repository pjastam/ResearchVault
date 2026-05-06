#!/usr/bin/env python3
"""
summarize_item.py — Privacy-preserving samenvattingsagent voor ResearchVault.

Genereert een compacte samenvatting van een 📖-item voor fase 2 Go/No-go beslissing.
De samenvatting wordt naar een lokaal bestand geschreven; alleen het pad wordt
teruggegeven. Geen afgeleide tekst bereikt Claude Code als tool-output.

Gebruik (paper met abstract — geen modelaanroep):
    python3 .claude/summarize_item.py \\
        --item-key ITEMKEY \\
        --type paper \\
        --title "Titel" \\
        --abstract "Abstract-tekst..."

Gebruik (paper zonder abstract):
    python3 .claude/summarize_item.py \\
        --item-key ITEMKEY \\
        --type paper \\
        --title "Titel" --authors "Achternaam, V." --year 2024

Gebruik (YouTube — video_id uit YouTube-URL):
    python3 .claude/summarize_item.py \\
        --item-key ITEMKEY \\
        --type youtube \\
        --title "Videotitel" \\
        --cache-id VIDEO_ID

Gebruik (podcast — episode_id = MD5-hash van aflevering-URL):
    python3 .claude/summarize_item.py \\
        --item-key ITEMKEY \\
        --type podcast \\
        --title "Afleveringstitel" \\
        --cache-id EPISODE_ID

Output (stdout, JSON):
    {"status": "ok",   "path": ".cache/_summary_ITEMKEY.md"}
    {"status": "error", "message": "..."}

Geen samenvatting of brontekst wordt als output teruggegeven — alleen het pad.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# ── Padconfiguratie ───────────────────────────────────────────────────────────

VAULT_ROOT        = Path(__file__).resolve().parent.parent   # ResearchVault/
CLAUDE_DIR        = VAULT_ROOT / ".claude"
INBOX_DIR         = VAULT_ROOT / "vault" / ".cache"
TRANSCRIPT_CACHE  = CLAUDE_DIR / "transcript_cache"
PYTHON            = Path(
    os.environ.get(
        "ZOTERO_PYTHON",
        "/Users/pietstam/.local/share/uv/tools/zotero-mcp-server/bin/python3",
    )
)
FETCH_SCRIPT      = CLAUDE_DIR / "fetch-fulltext.py"
GENERATE_SCRIPT   = CLAUDE_DIR / "ollama-generate.py"
DEFAULT_MODEL     = "qwen3.5:9b"

# ── Prompts ───────────────────────────────────────────────────────────────────

SUMMARY_PROMPT_PAPER = """\
You are a research assistant. Write a compact structured summary of the source text below.

Rules:
- Write in the SAME LANGUAGE as the source text.
- Use exactly these three sections:

## Introduction
2-3 sentences: what is this paper about and what is the central claim?

## Key findings
4-6 bullet points with the most important results or arguments.

## Relevance
2 sentences: why might this be relevant for health economics research?

Return only the structured text, no preamble or closing remarks.\
"""

SUMMARY_PROMPT_MEDIA = """\
You receive the transcript or show notes of a video or podcast episode.
Write a compact structured summary.

Rules:
- Write in the SAME LANGUAGE as the source text.
- Use exactly these three sections:

## Introduction
2-3 sentences: what is this episode about and what is the main angle?

## Key topics
5-7 bullet points with the key topics, arguments, or findings discussed.

## Relevance
2 sentences: why might this be relevant for health economics research?

Return only the structured text, no preamble or closing remarks.\
"""

# ── Hulpfuncties ──────────────────────────────────────────────────────────────

def ok(path: str) -> None:
    print(json.dumps({"status": "ok", "path": path}, ensure_ascii=False))


def error(message: str) -> None:
    print(json.dumps({"status": "error", "message": message}, ensure_ascii=False))
    sys.exit(1)


def run(cmd: list[str | Path], description: str) -> subprocess.CompletedProcess:
    result = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if result.returncode != 0:
        error(f"{description} mislukt (exit {result.returncode}): {result.stderr.strip()}")
    return result


def write_summary(item_key: str, header: str, body: str) -> Path:
    """Schrijf de samenvatting naar inbox/_summary_{item_key}.md en retourneer het pad."""
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    out = INBOX_DIR / f"_summary_{item_key}.md"
    out.write_text(header + "\n\n" + body.strip(), encoding="utf-8")
    return out


def build_header(title: str, authors: list[str], year: str, item_type: str) -> str:
    lines = [f"# {title}"]
    meta = []
    if authors:
        meta.append(", ".join(authors))
    if year:
        meta.append(str(year))
    if item_type:
        meta.append(item_type)
    if meta:
        lines.append("*" + " · ".join(meta) + "*")
    lines.append("")
    lines.append("---")
    return "\n".join(lines)


# ── Hoofdprogramma ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Privacy-preserving samenvattingsagent voor fase 2 Go/No-go"
    )
    parser.add_argument("--item-key",  required=True, help="Zotero item key")
    parser.add_argument("--type",      required=True, choices=["paper", "youtube", "podcast"])
    parser.add_argument("--title",     default="")
    parser.add_argument("--authors",   action="append", default=[])
    parser.add_argument("--year",      default="")
    parser.add_argument("--abstract",  default="", help="Abstract-tekst (paper); geen modelaanroep nodig")
    parser.add_argument("--cache-id",  default="", help="Video ID (youtube) of episode ID (podcast)")
    parser.add_argument("--model",     default=DEFAULT_MODEL)
    args = parser.parse_args()

    item_key   = args.item_key
    item_type  = args.type
    title      = args.title
    authors    = args.authors or []
    year       = args.year
    abstract   = args.abstract.strip()
    cache_id   = args.cache_id.strip()
    model      = args.model

    header = build_header(title, authors, year, item_type)

    # ── Paper met abstract ─────────────────────────────────────────────────────
    if item_type == "paper" and abstract:
        print("[1/1] Abstract direct wegschrijven (geen modelaanroep)…", file=sys.stderr)
        body = f"## Abstract\n\n{abstract}"
        out = write_summary(item_key, header, body)
        ok(str(out.relative_to(VAULT_ROOT)))
        return

    # ── Paper zonder abstract ──────────────────────────────────────────────────
    if item_type == "paper":
        tmp_input  = INBOX_DIR / f"_tmp_{item_key}.txt"
        tmp_output = INBOX_DIR / f"_tmp_summary_{item_key}.md"

        print(f"[1/3] Volledige tekst ophalen voor {item_key}…", file=sys.stderr)
        run([PYTHON, FETCH_SCRIPT, item_key, str(tmp_input)], "fetch-fulltext")

        if not tmp_input.exists() or tmp_input.stat().st_size == 0:
            error(f"Tijdelijk invoerbestand leeg of ontbreekt: {tmp_input}")

        print(f"[2/3] Samenvatting genereren via {model}…", file=sys.stderr)
        run([
            PYTHON, GENERATE_SCRIPT,
            "--input",  str(tmp_input),
            "--output", str(tmp_output),
            "--prompt", SUMMARY_PROMPT_PAPER,
            "--model",  model,
        ], "ollama-generate")

        print("[3/3] Samenvatting wegschrijven…", file=sys.stderr)
        body = tmp_output.read_text(encoding="utf-8")
        out  = write_summary(item_key, header, body)

        tmp_input.unlink(missing_ok=True)
        tmp_output.unlink(missing_ok=True)
        ok(str(out.relative_to(VAULT_ROOT)))
        return

    # ── YouTube ────────────────────────────────────────────────────────────────
    if item_type == "youtube":
        if not cache_id:
            error("--cache-id (video ID) is verplicht voor type youtube")

        cache_file = TRANSCRIPT_CACHE / f"{cache_id}.json"
        if not cache_file.exists():
            error(f"Geen transcript gevonden in cache: {cache_file}")

        data = json.loads(cache_file.read_text(encoding="utf-8"))
        transcript = data.get("text", "").strip()
        if not transcript:
            error(f"Transcript is leeg in cache: {cache_file}")

        tmp_input  = INBOX_DIR / f"_tmp_{item_key}.txt"
        tmp_output = INBOX_DIR / f"_tmp_summary_{item_key}.md"

        tmp_input.write_text(transcript, encoding="utf-8")

        print(f"[1/2] Samenvatting genereren via {model}…", file=sys.stderr)
        run([
            PYTHON, GENERATE_SCRIPT,
            "--input",  str(tmp_input),
            "--output", str(tmp_output),
            "--prompt", SUMMARY_PROMPT_MEDIA,
            "--model",  model,
        ], "ollama-generate")

        print("[2/2] Samenvatting wegschrijven…", file=sys.stderr)
        body = tmp_output.read_text(encoding="utf-8")
        out  = write_summary(item_key, header, body)

        tmp_input.unlink(missing_ok=True)
        tmp_output.unlink(missing_ok=True)
        ok(str(out.relative_to(VAULT_ROOT)))
        return

    # ── Podcast ────────────────────────────────────────────────────────────────
    if item_type == "podcast":
        if not cache_id:
            error("--cache-id (episode ID) is verplicht voor type podcast")

        cache_file = TRANSCRIPT_CACHE / f"podcast_{cache_id}.json"
        if not cache_file.exists():
            error(f"Geen show notes / transcript gevonden in cache: {cache_file}")

        data = json.loads(cache_file.read_text(encoding="utf-8"))
        text = data.get("text", "").strip()
        if not text:
            error(f"Tekst is leeg in cache: {cache_file}")

        tmp_input  = INBOX_DIR / f"_tmp_{item_key}.txt"
        tmp_output = INBOX_DIR / f"_tmp_summary_{item_key}.md"

        tmp_input.write_text(text, encoding="utf-8")

        print(f"[1/2] Samenvatting genereren via {model}…", file=sys.stderr)
        run([
            PYTHON, GENERATE_SCRIPT,
            "--input",  str(tmp_input),
            "--output", str(tmp_output),
            "--prompt", SUMMARY_PROMPT_MEDIA,
            "--model",  model,
        ], "ollama-generate")

        print("[2/2] Samenvatting wegschrijven…", file=sys.stderr)
        body = tmp_output.read_text(encoding="utf-8")
        out  = write_summary(item_key, header, body)

        tmp_input.unlink(missing_ok=True)
        tmp_output.unlink(missing_ok=True)
        ok(str(out.relative_to(VAULT_ROOT)))
        return


if __name__ == "__main__":
    main()
