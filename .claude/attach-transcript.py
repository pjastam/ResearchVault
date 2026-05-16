#!/usr/bin/env python3
"""
attach-transcript.py — Voeg cleaned transcript en abstract toe aan Zotero YouTube-item.

Stappen:
1. Transcript ophalen uit .claude/transcript_cache/ of via YouTubeTranscriptApi
2. Qwen: transcript opschonen (transformatie, geen samenvatting)
3. Qwen: abstract 3-5 zinnen
4. Zotero: abstractNote bijwerken via Web API
5. Zotero: cleaned transcript toevoegen als note (tag: _transcript)

Gebruik:
    python3 .claude/attach-transcript.py \
        --item-key ITEMKEY \
        [--url "https://youtube.com/watch?v=VIDEO_ID"] \
        [--model qwen3.5:9b]

Output (stdout, JSON):
    {"status": "ok", "item_key": "ITEMKEY"}
    {"status": "error", "message": "..."}

Geen transcriptinhoud bereikt Claude Code — alleen het statusobject.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

# ── Padconfiguratie ───────────────────────────────────────────────────────────

VAULT_ROOT           = Path(__file__).resolve().parent.parent
CLAUDE_DIR           = VAULT_ROOT / ".claude"
TRANSCRIPT_CACHE_DIR = CLAUDE_DIR / "transcript_cache"
TRANSCRIPTS_DIR      = Path.home() / "Zotero" / "Transcripts"
INBOX_DIR            = VAULT_ROOT / "inbox"
PYTHON               = Path(os.environ.get(
    "ZOTERO_PYTHON",
    "/Users/pietstam/.local/share/uv/tools/zotero-mcp-server/bin/python3",
))
GENERATE_SCRIPT      = CLAUDE_DIR / "ollama-generate.py"

# ── Zotero Web API ────────────────────────────────────────────────────────────

def _load_api_key() -> str:
    key = os.environ.get("ZOTERO_API_KEY", "")
    if key:
        return key
    zprofile = Path.home() / ".zprofile"
    if zprofile.exists():
        for line in zprofile.read_text().splitlines():
            line = line.strip()
            if line.startswith("export ZOTERO_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


ZOTERO_API_KEY  = _load_api_key()
ZOTERO_USER_ID  = "24775"
ZOTERO_API_BASE = f"https://api.zotero.org/users/{ZOTERO_USER_ID}"

# ── Prompts ───────────────────────────────────────────────────────────────────

ABSTRACT_PROMPT = """\
Write a concise abstract (3-5 sentences) for this video transcript. \
Cover: (1) the central question or topic, (2) the main argument or findings, \
(3) relevance to academic research. \
Write in the SAME LANGUAGE as the source text. \
Output only the abstract text, no preamble or closing remarks.\
"""

# ── Hulpfuncties ──────────────────────────────────────────────────────────────

def ok(item_key: str) -> None:
    print(json.dumps({"status": "ok", "item_key": item_key}, ensure_ascii=False))


def error(msg: str) -> None:
    print(json.dumps({"status": "error", "message": msg}, ensure_ascii=False))
    sys.exit(1)


def extract_video_id(url: str) -> str | None:
    m = re.search(r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})', url)
    return m.group(1) if m else None


def get_transcript_text(video_id: str | None) -> str | None:
    """Haalt transcript op uit cache of via YouTubeTranscriptApi."""
    if video_id:
        cache_file = TRANSCRIPT_CACHE_DIR / f"{video_id}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                text = data.get("text", "")
                if text:
                    print(f"  Transcript uit cache: {len(text):,} tekens", file=sys.stderr)
                    return text
            except Exception:
                pass

    if not video_id:
        return None

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        snippets = YouTubeTranscriptApi().fetch(video_id)
        text = " ".join(s.text for s in snippets)
        print(f"  Transcript via YouTubeTranscriptApi: {len(text):,} tekens", file=sys.stderr)
        return text
    except Exception as e:
        print(f"  Transcript ophalen mislukt: {e}", file=sys.stderr)
        return None


def run_qwen(input_path: Path, output_path: Path, prompt: str, model: str) -> bool:
    """Roept ollama-generate.py aan; retourneert True bij succes."""
    result = subprocess.run(
        [str(PYTHON), str(GENERATE_SCRIPT),
         "--input",  str(input_path),
         "--output", str(output_path),
         "--prompt", prompt,
         "--model",  model],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  Qwen fout: {result.stderr.strip()}", file=sys.stderr)
        return False
    return True


def _get_item_version(item_key: str) -> int | None:
    """Haalt het huidige versienummer van een Zotero item op (vereist voor PATCH)."""
    req = urllib.request.Request(
        f"{ZOTERO_API_BASE}/items/{item_key}",
        headers={"Zotero-API-Key": ZOTERO_API_KEY, "Zotero-API-Version": "3"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
            return data.get("data", {}).get("version")
    except Exception as e:
        print(f"  Versie ophalen mislukt: {e}", file=sys.stderr)
        return None


def zotero_patch(item_key: str, fields: dict) -> bool:
    """Patchet een Zotero item met de opgegeven velden."""
    if not ZOTERO_API_KEY:
        print("  ZOTERO_API_KEY niet beschikbaar — abstractNote niet bijgewerkt", file=sys.stderr)
        return False
    version = _get_item_version(item_key)
    if version is None:
        print("  Versienummer onbekend — PATCH overgeslagen", file=sys.stderr)
        return False
    payload = json.dumps(fields).encode("utf-8")
    req = urllib.request.Request(
        f"{ZOTERO_API_BASE}/items/{item_key}",
        data=payload,
        headers={
            "Zotero-API-Key":              ZOTERO_API_KEY,
            "Zotero-API-Version":          "3",
            "Content-Type":                "application/json",
            "If-Unmodified-Since-Version": str(version),
        },
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()
            return True
    except urllib.error.HTTPError as e:
        print(f"  PATCH mislukt: {e.code} {e.reason}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  PATCH mislukt: {e}", file=sys.stderr)
        return False


def zotero_add_transcript_attachment(item_key: str, transcript_text: str) -> bool:
    """Slaat ruwe transcript op als .txt bestand en koppelt als linked_file aan Zotero item."""
    if not ZOTERO_API_KEY:
        return False
    dest = TRANSCRIPTS_DIR / f"{item_key}.txt"
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(transcript_text, encoding="utf-8")
    except Exception as e:
        print(f"  Transcript opslaan mislukt: {e}", file=sys.stderr)
        return False
    payload = json.dumps([{
        "itemType":    "attachment",
        "linkMode":    "linked_file",
        "title":       "Transcript",
        "parentItem":  item_key,
        "contentType": "text/plain",
        "path":        str(dest),
    }]).encode("utf-8")
    req = urllib.request.Request(
        f"{ZOTERO_API_BASE}/items",
        data=payload,
        headers={
            "Zotero-API-Key":     ZOTERO_API_KEY,
            "Zotero-API-Version": "3",
            "Content-Type":       "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = json.loads(r.read())
            att_key = next(iter(body.get("successful", {}).values()), {}).get("key", "")
            print(f"  Transcript-bijlage aangemaakt: {att_key} ({dest})", file=sys.stderr)
            return bool(att_key)
    except Exception as e:
        print(f"  Bijlage aanmaken mislukt: {e}", file=sys.stderr)
        return False


def transcript_exists(item_key: str, retries: int = 3, delay: float = 5.0) -> bool:
    """Controleert of er al een transcript bestaat (linked_file bijlage of oudere note-vorm).

    Probeert meerdere keren met een wachttijd om read-after-write consistency
    van de Zotero cloud API op te vangen.
    """
    import time as _time
    if not ZOTERO_API_KEY:
        return False
    for attempt in range(retries):
        req = urllib.request.Request(
            f"{ZOTERO_API_BASE}/items/{item_key}/children",
            headers={"Zotero-API-Key": ZOTERO_API_KEY, "Zotero-API-Version": "3"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                children = json.loads(r.read())
            found = any(
                # nieuwe vorm: linked_file text/plain
                (c["data"].get("itemType") == "attachment"
                 and c["data"].get("contentType") == "text/plain"
                 and c["data"].get("linkMode") == "linked_file")
                or
                # oude vorm: note met _transcript tag
                (c["data"].get("itemType") == "note"
                 and any(t["tag"] == "_transcript" for t in c["data"].get("tags", [])))
                for c in children
            )
            if found:
                return True
        except Exception:
            pass
        if attempt < retries - 1:
            _time.sleep(delay)
    return False


# ── Hoofdprogramma ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Voeg cleaned transcript en abstract toe aan Zotero YouTube-item"
    )
    parser.add_argument("--item-key",  required=True, help="Zotero item key")
    parser.add_argument("--url",       default="",    help="YouTube URL voor video_id extractie")
    parser.add_argument("--model",     default="qwen3.5:9b")
    parser.add_argument("--force",     action="store_true",
                        help="Overschrijf bestaande transcript-note")
    args = parser.parse_args()

    item_key = args.item_key
    video_id = extract_video_id(args.url) if args.url else None

    # Sla over als transcript al bestaat (tenzij --force)
    if not args.force and transcript_exists(item_key):
        print(f"  Transcript bestaat al voor {item_key} — overgeslagen", file=sys.stderr)
        ok(item_key)
        return

    # ── Stap 1: Transcript ophalen ────────────────────────────────────────────
    print(f"[1/3] Transcript ophalen (item: {item_key})…", file=sys.stderr)
    raw_text = get_transcript_text(video_id)
    if not raw_text:
        error(f"Geen transcript beschikbaar voor item {item_key} (video_id: {video_id})")

    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    raw_path      = INBOX_DIR / f"_raw_{item_key}.txt"
    abstract_path = INBOX_DIR / f"_abstract_{item_key}.txt"
    raw_path.write_text(raw_text, encoding="utf-8")  # type: ignore[arg-type]

    try:
        # ── Stap 2: Abstract genereren ────────────────────────────────────────
        print(f"[2/3] Abstract genereren via {args.model}…", file=sys.stderr)
        if not run_qwen(raw_path, abstract_path, ABSTRACT_PROMPT, args.model):
            error("Qwen: abstract genereren mislukt")

        # Lees output intern (Python — bereikt Claude Code niet)
        abstract_text = abstract_path.read_text(encoding="utf-8").strip()

    finally:
        # Tijdelijke bestanden opruimen
        raw_path.unlink(missing_ok=True)
        abstract_path.unlink(missing_ok=True)

    # ── Stap 3: Zotero bijwerken ──────────────────────────────────────────────
    print("[3/3] Zotero bijwerken…", file=sys.stderr)

    if abstract_text:
        zotero_patch(item_key, {"abstractNote": abstract_text})

    zotero_add_transcript_attachment(item_key, raw_text)  # type: ignore[arg-type]

    ok(item_key)


if __name__ == "__main__":
    main()
