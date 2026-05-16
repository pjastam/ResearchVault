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
import hashlib
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
WHISPER_MODEL        = "large-v3-turbo"
WHISPER_MODELS_DIR   = Path("/opt/homebrew/share/whisper.cpp/models")

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


# ── Podcast-helpers ───────────────────────────────────────────────────────────

def _load_podcast_cache(url: str) -> dict:
    """Laadt het podcast-cache-bestand op basis van de pagina-URL (of audio-URL)."""
    episode_id = "podcast_" + hashlib.md5(url.encode()).hexdigest()
    cache_file = TRANSCRIPT_CACHE_DIR / f"{episode_id}.json"
    if not cache_file.exists():
        return {}
    try:
        return json.loads(cache_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_podcast_shownotes(url: str) -> str | None:
    """Haalt show notes op uit de feedreader-cache (zelfde MD5-sleutel als feedreader-score.py)."""
    data = _load_podcast_cache(url)
    if data.get("source") == "shownotes" and data.get("text"):
        return data["text"]
    return None


def detect_language_from_text(text: str) -> str:
    """Schat taal in op basis van Nederlandse stopwoorden. Retourneert 'nl' of ''."""
    nl_words = {"de", "het", "een", "van", "voor", "zijn", "met", "dat", "die", "er",
                "op", "te", "in", "is", "als", "ook", "aan", "maar", "om", "bij"}
    words = set(text.lower().split())
    nl_count = len(words & nl_words)
    return "nl" if nl_count >= 3 else ""


def get_podcast_audio_url(url: str) -> str | None:
    """Haalt de directe audio-URL op uit de feedreader-cache (RSS <enclosure> tag).
    Alleen beschikbaar voor episodes die na de feedreader-score.py-update zijn gecachet."""
    data = _load_podcast_cache(url)
    return data.get("audio_url") or None


def download_audio(url: str, dest: Path) -> bool:
    """Download audio via yt-dlp (YouTube e.d.) of directe urllib-download (MP3/M4A-URL)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Directe download voor bekende audio-extensies (geen ffmpeg nodig)
    if re.search(r'\.(mp3|m4a|ogg|flac|wav)(\?|$)', url, re.IGNORECASE):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
                while chunk := r.read(65536):
                    f.write(chunk)
            print(f"  Directe download: {dest.stat().st_size // 1024:,} KB", file=sys.stderr)
            return dest.exists()
        except Exception as e:
            print(f"  Directe download mislukt: {e}", file=sys.stderr)
            return False
    # Overige URLs (YouTube, SoundCloud, etc.) via yt-dlp (vereist ffmpeg)
    result = subprocess.run(
        ["/opt/homebrew/bin/yt-dlp", "-x", "--audio-format", "mp3",
         "-o", str(dest), url],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        print(f"  yt-dlp fout: {stderr[-300:]}", file=sys.stderr)
        if "Unsupported URL" in stderr:
            print("  Tip: deze podcast-host wordt niet ondersteund door yt-dlp. "
                  "Voeg de feed toe aan feedreader-list.txt; na de volgende feedreader-score.py-run "
                  "wordt de directe audio-URL automatisch gecachet en gebruikt.",
                  file=sys.stderr)
        elif "ffprobe and ffmpeg not found" in stderr or "Postprocessing" in stderr:
            print("  Tip: installeer ffmpeg via 'brew install ffmpeg' voor yt-dlp audio-extractie.",
                  file=sys.stderr)
        return False
    return dest.exists()


def transcribe_audio(audio_path: Path, model: str, language: str = "") -> Path | None:
    """Transcribert audio via whisper-cli; retourneert pad naar .txt output."""
    model_path = WHISPER_MODELS_DIR / f"ggml-{model}.bin"
    if not model_path.exists():
        print(f"  Whisper-model niet gevonden: {model_path}", file=sys.stderr)
        print(f"  Download via: brew run whisper-cpp --download-model {model}",
              file=sys.stderr)
        return None
    cmd = ["/opt/homebrew/bin/whisper-cli", "-m", str(model_path), "-otxt", str(audio_path)]
    if language:
        cmd += ["--language", language]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  whisper-cli fout: {result.stderr.strip()[-500:]}", file=sys.stderr)
        return None
    # whisper-cli voegt .txt toe aan de volledige bestandsnaam: audio.mp3 → audio.mp3.txt
    txt_path = Path(str(audio_path) + ".txt")
    return txt_path if txt_path.exists() else None


def zotero_get_abstract(item_key: str) -> str:
    """Haalt de huidige abstractNote op via de lokale Zotero API (geen sync-vertraging)."""
    try:
        req = urllib.request.Request(
            f"http://localhost:23119/api/users/0/items/{item_key}",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read()).get("data", {}).get("abstractNote", "")
    except Exception:
        return ""


def zotero_create_note(item_key: str, title: str, content: str) -> bool:
    """Maakt een child note aan onder het gegeven Zotero item."""
    if not ZOTERO_API_KEY:
        return False
    html = f"<h1>{title}</h1>\n<p>{content.replace(chr(10), '</p><p>')}</p>"
    payload = json.dumps([{
        "itemType":   "note",
        "parentItem": item_key,
        "note":       html,
        "tags":       [],
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
            note_key = next(iter(body.get("successful", {}).values()), {}).get("key", "")
            if note_key:
                print(f"  Child note aangemaakt: {note_key} ({title!r})", file=sys.stderr)
                return True
    except Exception as e:
        print(f"  Child note aanmaken mislukt: {e}", file=sys.stderr)
    return False


def shownotes_note_exists(item_key: str) -> bool:
    """Controleert of er al een 'Shownotes' child note bestaat via de lokale Zotero API.
    Gebruikt localhost zodat net-aangemaakte notes direct zichtbaar zijn (geen sync-vertraging)."""
    try:
        req = urllib.request.Request(
            f"http://localhost:23119/api/users/0/items/{item_key}/children",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            children = json.loads(r.read())
        return any(
            c["data"].get("itemType") == "note"
            and "<h1>Shownotes</h1>" in c["data"].get("note", "")
            for c in children
        )
    except Exception:
        return False


def _add_tag(item_key: str, tag: str) -> bool:
    """Voeg een tag toe aan een Zotero item zonder bestaande tags te overschrijven."""
    if not ZOTERO_API_KEY:
        return False
    req = urllib.request.Request(
        f"{ZOTERO_API_BASE}/items/{item_key}",
        headers={"Zotero-API-Key": ZOTERO_API_KEY, "Zotero-API-Version": "3"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = json.loads(r.read())
            version = raw["data"]["version"]
            existing = raw["data"].get("tags", [])
    except Exception as e:
        print(f"  Tags ophalen mislukt: {e}", file=sys.stderr)
        return False
    if any(t["tag"] == tag for t in existing):
        return True
    payload = json.dumps({"tags": existing + [{"tag": tag}]}).encode("utf-8")
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
    except Exception as e:
        print(f"  Tag toevoegen mislukt: {e}", file=sys.stderr)
        return False


# ── Hoofdprogramma ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Voeg transcript en abstract toe aan Zotero YouTube- of podcast-item"
    )
    parser.add_argument("--item-key",      required=True, help="Zotero item key")
    parser.add_argument("--url",           default="",    help="YouTube- of podcast-URL")
    parser.add_argument("--model",         default="qwen3.5:9b",
                        help="Ollama-model voor abstract (YouTube zonder cache)")
    parser.add_argument("--whisper-model",    default=WHISPER_MODEL,
                        help=f"whisper.cpp-model voor podcast-transcriptie (default: {WHISPER_MODEL})")
    parser.add_argument("--language",         default="",
                        help="Taalcode voor whisper-cli (bijv. 'nl', 'en'); leeg = automatisch")
    parser.add_argument("--force",            action="store_true",
                        help="Overschrijf bestaand transcript")
    args = parser.parse_args()

    item_key = args.item_key
    video_id = extract_video_id(args.url) if args.url else None

    # Sla over als transcript al bestaat (tenzij --force)
    if not args.force and transcript_exists(item_key):
        print(f"  Transcript bestaat al voor {item_key} — overgeslagen", file=sys.stderr)
        ok(item_key)
        return

    if video_id:
        # ── YouTube-pad ───────────────────────────────────────────────────────
        print(f"[1/3] Transcript ophalen (item: {item_key})…", file=sys.stderr)
        raw_text = get_transcript_text(video_id)
        if not raw_text:
            error(f"Geen transcript beschikbaar voor item {item_key} (video_id: {video_id})")

        INBOX_DIR.mkdir(parents=True, exist_ok=True)
        raw_path      = INBOX_DIR / f"_raw_{item_key}.txt"
        abstract_path = INBOX_DIR / f"_abstract_{item_key}.txt"
        raw_path.write_text(raw_text, encoding="utf-8")  # type: ignore[arg-type]

        try:
            print(f"[2/3] Abstract genereren via {args.model}…", file=sys.stderr)
            if not run_qwen(raw_path, abstract_path, ABSTRACT_PROMPT, args.model):
                error("Qwen: abstract genereren mislukt")
            abstract_text = abstract_path.read_text(encoding="utf-8").strip()
        finally:
            raw_path.unlink(missing_ok=True)
            abstract_path.unlink(missing_ok=True)

        print("[3/3] Zotero bijwerken…", file=sys.stderr)
        if abstract_text:
            zotero_patch(item_key, {"abstractNote": abstract_text})
        zotero_add_transcript_attachment(item_key, raw_text)  # type: ignore[arg-type]

    elif args.url:
        # ── Podcast-pad ───────────────────────────────────────────────────────
        INBOX_DIR.mkdir(parents=True, exist_ok=True)
        tmp_mp3 = INBOX_DIR / f"_audio_{item_key}.mp3"
        txt_path = None

        print(f"[1/3] Audio downloaden (item: {item_key})…", file=sys.stderr)
        # Gebruik gecachte directe audio-URL (RSS <enclosure>) als die beschikbaar is
        audio_url = get_podcast_audio_url(args.url) or args.url
        if audio_url != args.url:
            print(f"  Audio-URL uit feedreader-cache: {audio_url[:80]}", file=sys.stderr)
        if not download_audio(audio_url, tmp_mp3):
            error(f"Audio downloaden mislukt voor {audio_url}")

        # Bepaal taal voor whisper: --language heeft voorrang; anders auto-detectie uit show notes
        whisper_language = args.language
        if not whisper_language:
            shownotes_text = get_podcast_shownotes(args.url)
            if shownotes_text:
                whisper_language = detect_language_from_text(shownotes_text)
                if whisper_language:
                    print(f"  Taal gedetecteerd uit show notes: {whisper_language}", file=sys.stderr)

        try:
            lang_label = f", taal: {whisper_language}" if whisper_language else ""
            print(f"[2/3] Transcriberen via whisper-cli ({args.whisper_model}{lang_label})…",
                  file=sys.stderr)
            txt_path = transcribe_audio(tmp_mp3, args.whisper_model, whisper_language)
            if not txt_path:
                error("whisper-cli: transcriptie mislukt")
            raw_text = txt_path.read_text(encoding="utf-8")

            print(f"  Abstract genereren via {args.model}…", file=sys.stderr)
            raw_path      = INBOX_DIR / f"_raw_{item_key}.txt"
            abstract_path = INBOX_DIR / f"_abstract_{item_key}.txt"
            raw_path.write_text(raw_text, encoding="utf-8")
            try:
                if not run_qwen(raw_path, abstract_path, ABSTRACT_PROMPT, args.model):
                    error("Qwen: abstract genereren mislukt")
                abstract_text = abstract_path.read_text(encoding="utf-8").strip()
            finally:
                raw_path.unlink(missing_ok=True)
                abstract_path.unlink(missing_ok=True)

        finally:
            tmp_mp3.unlink(missing_ok=True)
            if txt_path:
                txt_path.unlink(missing_ok=True)
            Path(str(tmp_mp3) + ".vtt").unlink(missing_ok=True)

        print("[3/3] Zotero bijwerken…", file=sys.stderr)
        # Als abstractNote al gevuld is en er nog geen Shownotes-note bestaat:
        # verplaats de bestaande inhoud (show notes) naar een child note.
        existing_abstract = zotero_get_abstract(item_key)
        if existing_abstract.strip() and not shownotes_note_exists(item_key):
            zotero_create_note(item_key, "Shownotes", existing_abstract.strip())
        if abstract_text:
            zotero_patch(item_key, {"abstractNote": abstract_text})
        # Bijlage: overschrijf bestaand bestand op schijf; maak alleen nieuw Zotero-record
        # aan als er nog geen transcript-bijlage bestaat (voorkomt duplicaten bij --force).
        if transcript_exists(item_key):
            dest = TRANSCRIPTS_DIR / f"{item_key}.txt"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(raw_text, encoding="utf-8")  # type: ignore[arg-type]
            print(f"  Transcript overschreven: {dest}", file=sys.stderr)
        else:
            zotero_add_transcript_attachment(item_key, raw_text)  # type: ignore[arg-type]
        _add_tag(item_key, "_enriched-transcript")

    else:
        error("Geen URL opgegeven — gebruik --url voor YouTube- of podcast-URL")

    ok(item_key)


if __name__ == "__main__":
    main()
