#!/usr/bin/env python3
"""
feedreader-score.py — RSS-feeds scoren en gefilterde Atom-feed genereren
=========================================================================
Haalt alle feeds op uit feedreader-list.txt, scoort elk item op relevantie
aan de hand van het ChromaDB-voorkeursprofiel, en schrijft gesorteerde
Atom-feeds naar feedreader-serve/ (per type: webpage, youtube, podcast).

Gebruik:
    python3 feedreader-score.py

Vereisten:
    feedparser, chromadb, numpy, sentence_transformers

Configuratie (pas aan indien nodig):
    FEEDS_FILE      — pad naar de lijst van feed-URLs
    SERVE_DIR       — map waar de gefilterde feeds worden weggeschreven
    LOG_FILE        — pad naar het score-logboek (score_log.jsonl)
    CHROMA_PATH     — pad naar ChromaDB directory
    ZOTERO_SQLITE   — pad naar Zotero SQLite database
    INBOX_ID        — collectionID van _inbox in Zotero
    WEIGHT_*        — gewichten voor het voorkeursprofiel
"""

import fcntl
import hashlib
import html
import html.parser
import json
import os
import re
import sqlite3
import sys
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import chromadb
import feedparser
import numpy as np
import logging
os.environ.setdefault("HF_HUB_OFFLINE", "1")
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
from sentence_transformers import SentenceTransformer

from feedreader_core import (
    THRESHOLD_GREEN,
    THRESHOLD_YELLOW,
    WEIGHT_DEFAULT,
    WEIGHT_ANNOTATIONS,
    cosine_similarity,
    compute_weighted_profile,
    score_label,
    detect_source_type,
    extract_snippet,
    make_item_summary,
)
from zotero_utils import make_sqlite_copy, get_library_keys_with_weights

# optionele afhankelijkheid — transcript-verrijking werkt alleen als dit pakket geïnstalleerd is
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    _YT_API_OK = True
except ImportError:
    _YT_API_OK = False

# ── Configuratie ──────────────────────────────────────────────────────────────

SCRIPT_DIR    = Path(__file__).parent
FEEDS_FILE    = SCRIPT_DIR / "feedreader-list.txt"
SERVE_DIR     = Path.home() / ".local" / "share" / "feedreader-serve"
LOG_FILE      = SCRIPT_DIR / "score_log.jsonl"
CHROMA_PATH   = Path.home() / ".config" / "zotero-mcp" / "chroma_db"
ZOTERO_SQLITE = Path.home() / "Zotero" / "zotero.sqlite"
INBOX_ID      = 333

FEED_TIMEOUT = 15  # seconden per feed
MAX_FEED_ITEMS = 300  # max items per type in de Atom-feed (sortering op score, dus top-N)
MAX_AGE_DAYS_DEFAULT  = 30   # max leeftijd voor web/podcast/YouTube-items
MAX_AGE_DAYS_ACADEMIC = 365  # max leeftijd voor academische publicaties

ACADEMIC_FEED_PATTERNS = (
    "pure.eur.nl",
    "research.vu.nl",
    "pubs.aeaweb.org",
    "healthaffairs.org",
    "biomedcentral.com",
    "link.springer.com",
    "journals.lww.com",
    "rss.sciencedirect.com",
    "onlinelibrary.wiley.com",
    "rand.org/topics/health-and-health-care",
    "esb.nu",
    "mejudice.nl",
)
TRANSCRIPT_CACHE_DIR = SCRIPT_DIR / "transcript_cache"
# Minimum show notes length (chars) to be usable for content-based scoring and article generation;
# shorter entries contain too little context for a meaningful embedding.
SHOWNOTES_MIN_LENGTH = 200

# ── Hulpfuncties ──────────────────────────────────────────────────────────────

def is_academic_feed(feed_url: str) -> bool:
    return any(pat in feed_url for pat in ACADEMIC_FEED_PATTERNS)


def within_max_age(published: str, max_age_days: int, now: datetime) -> bool:
    """Geeft True als het item binnen de maximale leeftijd valt, of als er geen datum is."""
    if not published:
        return True
    try:
        dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        return (now - dt).days <= max_age_days
    except ValueError:
        return True

class _HTMLStripper(html.parser.HTMLParser):
    """Strips HTML tags; handle_data is called with already-decoded entities."""
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
    def handle_data(self, d: str) -> None:
        self._parts.append(d)
    def get_data(self) -> str:
        return " ".join(self._parts)


def strip_html(text: str) -> str:
    """Verwijdert HTML-tags en decodeert HTML-entiteiten."""
    s = _HTMLStripper()
    s.feed(text)
    return re.sub(r"\s+", " ", s.get_data()).strip()


def load_feeds(path: Path) -> list[str]:
    """Leest feed-URLs uit het configuratiebestand."""
    urls = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Strip inline commentaar (spatie + # + tekst)
        if " #" in line:
            line = line[:line.index(" #")].strip()
        if line:
            urls.append(line)
    return urls


def get_embeddings_for_keys(collection, keys: list[str]) -> dict[str, np.ndarray]:
    if not keys:
        return {}
    result = collection.get(ids=keys, include=["embeddings", "documents"])
    out = {}
    skipped = 0
    for item_id, emb, doc in zip(result["ids"], result["embeddings"], result["documents"]):
        text = (doc or "").strip()
        if len(text) < 30 or "No authors listed" in text:
            skipped += 1
            continue
        out[item_id] = np.array(emb, dtype=np.float32)
    if skipped:
        print(f"     {skipped} items zonder bruikbare tekst uitgesloten van profiel.")
    return out




def load_existing_log(path: Path) -> set[str]:
    """Geeft de set van URLs die al in het logboek staan."""
    seen = set()
    if not path.exists():
        return seen
    for line in path.read_text().splitlines():
        try:
            entry = json.loads(line)
            if "url" in entry:
                seen.add(entry["url"])
        except json.JSONDecodeError:
            pass
    return seen


def append_log(path: Path, entries: list[dict]) -> None:
    """Voegt nieuwe entries toe aan het JSONL-logboek (exclusief vergrendeld)."""
    with path.open("a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def extract_video_id(url: str) -> str | None:
    """Extraheert het YouTube video-ID uit een watch-URL."""
    m = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', url)
    return m.group(1) if m else None


def fetch_and_cache_transcript(
    video_id: str, title: str, channel: str, url: str, published: str
) -> str | None:
    """
    Haalt het transcript op via YouTubeTranscriptApi en slaat het op in de cache.
    Schrijft ook bij mislukking een cache-bestand om herhaalde API-pogingen te vermijden.
    """
    TRANSCRIPT_CACHE_DIR.mkdir(exist_ok=True)
    cache_file = TRANSCRIPT_CACHE_DIR / f"{video_id}.json"

    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8")).get("text")
        except Exception as e:
            print(f"⚠️  transcript-cache corrupt, opnieuw ophalen: {cache_file.name}: {e}", file=sys.stderr)

    if not _YT_API_OK:
        return None

    text = None
    try:
        snippets = YouTubeTranscriptApi().fetch(
            video_id, languages=["nl", "en", "de", "fr"]
        )
        text = " ".join(s.text for s in snippets)
    except Exception:
        pass  # geen transcript beschikbaar; cache toch om herhaalde pogingen te voorkomen

    cache_file.write_text(json.dumps({
        "video_id":   video_id,
        "title":      title,
        "channel":    channel,
        "url":        url,
        "published":  published,
        "text":       text,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }, ensure_ascii=False))
    return text


def cache_podcast_shownotes(
    episode_id: str, title: str, channel: str, url: str, published: str, text: str
) -> None:
    """
    Slaat podcast show notes op in de transcript_cache map (prefix: podcast_).
    Schrijft alleen als er nog geen cache-bestand bestaat.
    """
    TRANSCRIPT_CACHE_DIR.mkdir(exist_ok=True)
    cache_file = TRANSCRIPT_CACHE_DIR / f"{episode_id}.json"
    if not cache_file.exists():
        cache_file.write_text(json.dumps({
            "episode_id": episode_id,
            "title":      title,
            "channel":    channel,
            "url":        url,
            "published":  published,
            "text":       text,
            "source":     "shownotes",
            "cached_at":  datetime.now(timezone.utc).isoformat(),
        }, ensure_ascii=False))



def atom_escape(text: str) -> str:
    """Escapet tekst voor gebruik in XML."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def score_to_fake_date(score: int, generated_at: datetime) -> str:
    """
    Zet score (0–100) om naar een tijdstip op de dag van generated_at zodat
    NetNewsWire op tijdstip kan sorteren (= sorteren op relevantie), terwijl
    alle items als 'vandaag' worden getoond.
    Score 100 → 23:59:00, score 0 → 00:00:00.
    """
    day_start = generated_at.replace(hour=0, minute=0, second=0, microsecond=0)
    seconds = int(score * 86340 / 100)  # 86340 = 23u59m in seconden
    return (day_start + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_atom_content_html(item: dict) -> str:
    """
    Genereert HTML-content voor het Atom <content type="html">-element.

    Structuur:
      - Tekst per brontype (transcript, show notes of lange beschrijving)
      - Scheidingslijn
      - Actieknoppen: ✅ Zotero · 📖 Later lezen · 👎 Overslaan
        (links naar GET /action op de lokale server)

    De content wordt als CDATA ingebed zodat geen dubbele XML-escaping nodig is.
    """
    url_enc     = urllib.parse.quote(item["url"], safe="")
    source_type = item.get("source_type", "web")

    parts = []

    # Tekst content per brontype
    text_content = None
    if source_type == "youtube" and item.get("has_transcript"):
        text_content = item.get("transcript_snippet", "") or None
    elif source_type == "podcast" and item.get("has_shownotes"):
        text_content = item.get("description", "") or None
    else:
        desc = item.get("description", "")
        if len(desc) > 600:
            text_content = desc

    if text_content:
        for para in text_content.split("\n\n"):
            para = para.strip()
            if para:
                parts.append(f"<p>{html.escape(para)}</p>")

    # Actieknoppen onderin — via image-trick (geen browsertabblad, vereist JS)
    title_enc  = urllib.parse.quote(item.get("title", ""), safe="")
    stype_enc  = urllib.parse.quote(source_type, safe="")
    source_enc = urllib.parse.quote(item.get("feed_name", ""), safe="")
    date_enc   = urllib.parse.quote(item.get("published", "")[:10], safe="")  # YYYY-MM-DD
    action_base = (
        f"http://localhost:8765/action"
        f"?url={url_enc}&title={title_enc}&stype={stype_enc}"
        f"&source={source_enc}&date={date_enc}&type="
    )
    btn_style = (
        "cursor:pointer;border:1px solid #ccc;border-radius:5px;"
        "background:#f5f5f5;padding:.25rem .6rem;font-size:.85em;"
    )
    script = (
        f'<script>'
        f'function rvAct(t,b){{'
        f'b.disabled=true;b.style.opacity=".5";'
        f'var i=new Image();'
        f'i.onload=function(){{b.textContent="✓ Klaar";}};'
        f'i.onerror=function(){{b.textContent="⚠️ Fout";}};'
        f'i.src="{action_base}"+t;'
        f'}}'
        f'</script>'
    )
    parts.append(
        '<hr style="margin:1.5em 0;border:none;border-top:1px solid #ccc">'
        '<p style="font-size:.85em;color:#666">'
        f'<button style="{btn_style}" onclick="rvAct(\'zotero\',this)">✅ Zotero</button>'
        '&nbsp;'
        f'<button style="{btn_style}" onclick="rvAct(\'read\',this)">📖 Later lezen</button>'
        '&nbsp;'
        f'<button style="{btn_style}" onclick="rvAct(\'skip\',this)">👎 Overslaan</button>'
        f'</p>{script}'
    )

    content = "\n".join(parts)
    # ]]> mag niet voorkomen in CDATA
    return content.replace("]]>", "]]&gt;")


def generate_atom(items: list[dict], generated_at: datetime, feed_title: str = "Feedreader — Gefilterde RSS-feed") -> str:
    """Genereert een Atom 1.0 feed als string.

    Bevat per item:
      <summary>  — schone teaser per brontype (transcript, show notes of gefilterde tekst)
      <content>  — volledigere tekst indien beschikbaar
      <rv:score> — relevantiescore (0–100)
      <rv:type>  — brontype (youtube | podcast | web)
    """
    ts = generated_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    entries = []
    for item in items:
        label     = score_label(item["score"])
        title     = atom_escape(f"{label} {item['score']:3d} | {item['title']}")
        link      = atom_escape(item["url"])
        feed_name = atom_escape(item["feed_name"])
        summary   = atom_escape(make_item_summary(item, max_len=400))
        entry_id  = atom_escape(item.get("url", str(uuid.uuid4())))
        updated   = score_to_fake_date(item["score"], generated_at)
        source_type = item.get("source_type", "web")

        content_html = _make_atom_content_html(item)
        content_xml  = f"\n    <content type=\"html\"><![CDATA[{content_html}]]></content>"

        entries.append(f"""  <entry>
    <title>{title}</title>
    <link href="{link}"/>
    <id>{entry_id}</id>
    <updated>{updated}</updated>
    <author><name>{feed_name}</name></author>
    <category term="{feed_name}"/>
    <rv:score>{item['score']}</rv:score>
    <rv:type>{source_type}</rv:type>
    <summary>{summary}</summary>{content_xml}
  </entry>""")

    entries_xml = "\n".join(entries)
    return f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:rv="urn:researchvault:feedreader:1">
  <title>{atom_escape(feed_title)}</title>
  <id>urn:feedreader:filtered-feed</id>
  <updated>{ts}</updated>
  <author><name>feedreader-score.py</name></author>
{entries_xml}
</feed>
"""


def generate_html(items: list[dict], generated_at: datetime) -> str:
    """Genereert een HTML-pagina met twee-paneel layout (lijst + lezer), à la NetNewsWire."""
    import json as _json

    date_str = generated_at.strftime("%-d %b %Y, %H:%M")

    data = _json.dumps([
        {
            "url":        item["url"],
            "href":       item["url"],
            "title":      item["title"],
            "score":      item["score"],
            "label":      score_label(item["score"]),
            "source":     item["feed_name"],
            "type":       item["source_type"],
            "snippet":    make_item_summary(item, max_len=250),
            "content":    (item.get("transcript_snippet") or item.get("description", ""))
                          if item["source_type"] == "youtube"
                          else item.get("description", ""),
            "published":  item.get("published", ""),
            "video_id":   item.get("video_id") or "",
            "episode_id": item.get("episode_id") or "",
        }
        for item in items
    ], ensure_ascii=False).replace("</", "<\\/")

    green  = sum(1 for i in items if i["score"] >= THRESHOLD_GREEN)
    yellow = sum(1 for i in items if THRESHOLD_YELLOW <= i["score"] < THRESHOLD_GREEN)
    red    = sum(1 for i in items if i["score"] < THRESHOLD_YELLOW)

    return f"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Phase 0 — RSS</title>
<style>
  :root {{
    --green:  #1a7f4b;
    --yellow: #9a6c00;
    --red:    #c0392b;
    --bg:     #f9f9f7;
    --card:   #ffffff;
    --border: #e0e0da;
    --text:   #1a1a1a;
    --muted:  #6b6b6b;
    --read-op: 0.45;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg:    #1c1c1e;
      --card:  #2c2c2e;
      --border:#3a3a3c;
      --text:  #f2f2f7;
      --muted: #98989e;
    }}
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: 15px;
    background: var(--bg);
    color: var(--text);
    padding: 0;
    overflow: hidden;
  }}
  header {{
    position: sticky; top: 0; z-index: 10;
    background: var(--card);
    border-bottom: 1px solid var(--border);
    padding: .75rem 1rem;
    display: flex; align-items: center; gap: .75rem; flex-wrap: wrap;
  }}
  header h1 {{ font-size: 1rem; font-weight: 600; flex: 1; }}
  .stats {{ font-size: .8rem; color: var(--muted); }}
  .tabs {{ display: flex; gap: .25rem; }}
  .tabs button {{
    border: 1px solid var(--border); border-radius: 6px;
    background: var(--bg); color: var(--text);
    padding: .3rem .7rem; font-size: .8rem; cursor: pointer;
  }}
  .tabs button.active {{
    background: var(--text); color: var(--bg); border-color: var(--text);
  }}
  .type-filter {{ display: flex; gap: .25rem; }}
  .type-filter button {{
    border: 1px solid var(--border); border-radius: 6px;
    background: var(--bg); color: var(--text);
    padding: .3rem .7rem; font-size: .8rem; cursor: pointer;
  }}
  .type-filter button.active {{
    background: var(--text); color: var(--bg); border-color: var(--text);
  }}
  .toggle-read {{
    font-size: .8rem; color: var(--muted);
    background: none; border: none; cursor: pointer; text-decoration: underline;
  }}
  /* ── two-panel layout ── */
  #layout {{
    display: flex; height: calc(100vh - 44px);
  }}
  #list-panel {{
    width: 300px; flex-shrink: 0; overflow-y: auto;
    border-right: 1px solid var(--border);
  }}
  #reader-panel {{
    flex: 1; overflow-y: auto; min-width: 0;
    background: var(--card);
    padding: 1.5rem 2rem;
  }}
  #reader-empty {{
    height: 100%; display: flex; align-items: center; justify-content: center;
    color: var(--muted); font-size: .9rem;
  }}
  #reader-content {{ display: none; max-width: 680px; margin: 0 auto; }}
  #reader-content.visible {{ display: block; }}
  #reader-title {{
    font-size: 1.15rem; font-weight: 700; line-height: 1.4; margin-bottom: .5rem;
  }}
  #reader-title a {{ color: var(--text); text-decoration: none; }}
  #reader-title a:hover {{ text-decoration: underline; }}
  #reader-meta {{
    font-size: .8rem; color: var(--muted); margin-bottom: 1rem;
    display: flex; align-items: center; gap: .4rem; flex-wrap: wrap;
  }}
  .reader-badge {{
    font-size: .72rem; font-weight: 700; padding: .1rem .3rem; border-radius: 4px;
  }}
  .reader-badge.green  {{ background: #d4f0e2; color: var(--green); }}
  .reader-badge.yellow {{ background: #fef3cd; color: var(--yellow); }}
  .reader-badge.red    {{ background: #fde8e8; color: var(--red); }}
  @media (prefers-color-scheme: dark) {{
    .reader-badge.green  {{ background: #0d3d25; }}
    .reader-badge.yellow {{ background: #3d2e00; }}
    .reader-badge.red    {{ background: #3d0f0f; }}
  }}
  #reader-body {{
    font-size: .9rem; line-height: 1.65;
    white-space: pre-wrap; word-break: break-word;
    border-top: 1px solid var(--border); padding-top: 1rem; margin-bottom: .75rem;
  }}
  #reader-actions {{
    display: flex; gap: .4rem; flex-wrap: wrap;
    border-top: 1px solid var(--border); padding-top: .75rem;
  }}
  #reader-actions button {{
    border: 1px solid var(--border); border-radius: 6px;
    background: var(--bg); color: var(--text);
    padding: .3rem .65rem; font-size: .82rem; cursor: pointer;
  }}
  #reader-actions button:hover {{ background: var(--border); }}
  /* ── terminal panel ── */
  #terminal-panel {{
    display: none; flex-shrink: 0; width: 45%;
    border-left: 1px solid var(--border); background: #1e1e1e;
  }}
  #terminal-panel.visible {{ display: flex; flex-direction: column; }}
  #terminal-panel iframe {{ flex: 1; border: none; width: 100%; height: 100%; }}
  @media (max-width: 800px) {{
    #layout {{ flex-direction: column; height: auto; }}
    body {{ overflow: auto; }}
    #list-panel {{ width: 100%; height: 55vh; border-right: none; border-bottom: 1px solid var(--border); }}
    #reader-panel {{ min-height: 50vh; padding: 1rem; }}
    #terminal-panel {{ width: 100%; height: 55vh; border-left: none; border-top: 1px solid var(--border); }}
  }}
  .view {{ display: none; padding: .5rem .6rem; }}
  .view.active {{ display: block; }}
  .source-group {{ margin-bottom: 1.25rem; }}
  .source-heading {{
    font-size: .7rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: .05em; color: var(--muted);
    padding: .4rem .25rem .2rem; border-bottom: 1px solid var(--border);
    margin-bottom: .35rem;
  }}
  .item {{
    display: flex; gap: .5rem; align-items: flex-start;
    padding: .4rem .35rem; border-radius: 7px;
    cursor: pointer; transition: background .1s;
  }}
  .item:hover {{ background: var(--border); }}
  .item.selected {{ background: var(--border); }}
  .item.read .item-title {{ font-weight: 400; }}
  .item.read {{ opacity: var(--read-op); }}
  .item.read.hidden {{ display: none; }}
  .item.skipped {{ opacity: var(--read-op); }}
  .item.skipped .item-title {{ text-decoration: line-through; }}
  .item.skipped.hidden {{ display: none; }}
  .skip-btn {{
    flex-shrink: 0; background: none; border: none;
    cursor: pointer; font-size: .8rem;
    padding: .2rem .3rem; border-radius: 5px;
    opacity: 0.15; line-height: 1; transition: opacity .15s;
  }}
  .skip-btn:hover {{ opacity: 0.9; background: var(--border); }}
  .item.skipped .skip-btn {{ display: none; }}
  .badge {{
    flex-shrink: 0; min-width: 2.1rem;
    font-size: .7rem; font-weight: 700;
    padding: .12rem .28rem; border-radius: 5px;
    text-align: center; margin-top: .15rem;
  }}
  .badge.green  {{ background: #d4f0e2; color: var(--green); }}
  .badge.yellow {{ background: #fef3cd; color: var(--yellow); }}
  .badge.red    {{ background: #fde8e8; color: var(--red); }}
  @media (prefers-color-scheme: dark) {{
    .badge.green  {{ background: #0d3d25; }}
    .badge.yellow {{ background: #3d2e00; }}
    .badge.red    {{ background: #3d0f0f; }}
  }}
  .item-body {{ flex: 1; min-width: 0; }}
  .item-title {{
    font-size: .85rem; line-height: 1.3; font-weight: 600;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }}
  .item-meta {{ font-size: .7rem; color: var(--muted); margin-top: .1rem; }}
  a {{ color: inherit; text-decoration: none; }}
</style>
</head>
<body>
<header>
  <h1>Phase 0</h1>
  <span class="stats">🟢 {green} &nbsp;🟡 {yellow} &nbsp;🔴 {red} &nbsp;·&nbsp; {date_str}</span>
  <div class="type-filter">
    <button class="active" onclick="setType('all', this)">Alles</button>
    <button onclick="setType('web', this)" title="RSS">📄</button>
    <button onclick="setType('youtube', this)" title="YouTube">▶️</button>
    <button onclick="setType('podcast', this)" title="Podcast">🎙️</button>
  </div>
  <div class="tabs">
    <button class="active" onclick="switchView('score', this)">Op score</button>
    <button onclick="switchView('source', this)">Op bron</button>
    <button onclick="switchView('date', this)">Op datum</button>
  </div>
  <button class="toggle-read" onclick="toggleRead()">verberg gelezen / overgeslagen</button>
  <button class="toggle-read" onclick="toggleTerminal()" id="term-btn">⌨️ terminal</button>
</header>

<div id="layout">
  <div id="list-panel">
    <div id="view-score" class="view active"></div>
    <div id="view-source" class="view"></div>
    <div id="view-date" class="view"></div>
  </div>
  <div id="reader-panel">
    <div id="reader-empty">← Selecteer een item om te lezen</div>
    <div id="reader-content">
      <div id="reader-title"></div>
      <div id="reader-meta"></div>
      <div id="reader-body"></div>
      <div id="reader-actions"></div>
    </div>
  </div>
  <div id="terminal-panel">
    <iframe id="term-iframe" src="about:blank"></iframe>
  </div>
</div>

<script>
const ITEMS = {data};
const READ_KEY  = "feedreader_read";
const SKIP_KEY  = "feedreader_skipped";
const ACT_BASE  = "http://localhost:8765/action";

function getRead() {{
  try {{ return new Set(JSON.parse(localStorage.getItem(READ_KEY) || "[]")); }}
  catch {{ return new Set(); }}
}}
function markRead(url) {{
  const s = getRead(); s.add(url);
  localStorage.setItem(READ_KEY, JSON.stringify([...s]));
}}
function getSkipped() {{
  try {{ return new Set(JSON.parse(localStorage.getItem(SKIP_KEY) || "[]")); }}
  catch {{ return new Set(); }}
}}
function markSkippedLocal(url) {{
  const s = getSkipped(); s.add(url);
  localStorage.setItem(SKIP_KEY, JSON.stringify([...s]));
}}

let currentType = "all";
let selectedUrl = null;
let hideRead    = false;

function setType(type, btn) {{
  currentType = type;
  document.querySelectorAll(".type-filter button").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  renderAll();
}}
function visibleItems() {{
  return currentType === "all" ? ITEMS : ITEMS.filter(i => i.type === currentType);
}}
function fmtDate(iso) {{
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return "";
  return d.toLocaleDateString("nl-NL", {{ day: "numeric", month: "short", year: "numeric" }});
}}
function badgeClass(score) {{
  if (score >= {THRESHOLD_GREEN}) return "green";
  if (score >= {THRESHOLD_YELLOW}) return "yellow";
  return "red";
}}
function escHtml(s) {{
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}}

/* ── Reader ── */
function rvAct(type, item, btn) {{
  btn.disabled = true; btn.style.opacity = ".5";
  var src = ACT_BASE
    + "?url="    + encodeURIComponent(item.url)
    + "&title="  + encodeURIComponent(item.title)
    + "&stype="  + encodeURIComponent(item.type)
    + "&source=" + encodeURIComponent(item.source)
    + "&date="   + encodeURIComponent((item.published || "").substring(0, 10))
    + "&type="   + type;
  var img = new Image();
  img.onload = function() {{ btn.textContent = "✓ Klaar"; }};
  img.onerror = function() {{ btn.textContent = "⚠️ Fout"; }};
  img.src = src;
  if (type === "skip") {{
    document.querySelectorAll(".item[data-url]").forEach(function(el) {{
      if (el.dataset.url === item.url) {{
        el.classList.add("skipped");
        if (hideRead) el.classList.add("hidden");
      }}
    }});
    markSkippedLocal(item.url);
    fetch("/skip", {{
      method: "POST",
      headers: {{"Content-Type": "application/json"}},
      body: JSON.stringify({{url: item.url, title: item.title, timestamp: new Date().toISOString()}})
    }}).catch(function() {{}});
  }}
}}

function showReader(item) {{
  selectedUrl = item.url;
  document.querySelectorAll(".item").forEach(function(el) {{
    el.classList.toggle("selected", el.dataset.url === item.url);
  }});
  document.getElementById("reader-empty").style.display = "none";
  var rc = document.getElementById("reader-content");
  rc.classList.add("visible");

  var titleEl = document.getElementById("reader-title");
  titleEl.innerHTML = "";
  var a = document.createElement("a");
  a.href = item.url; a.target = "_blank"; a.rel = "noopener";
  a.textContent = item.title;
  titleEl.appendChild(a);

  var metaEl = document.getElementById("reader-meta");
  metaEl.innerHTML = "";
  var bc = badgeClass(item.score);
  metaEl.innerHTML = escHtml(item.source)
    + (item.published ? " &nbsp;&middot;&nbsp; " + escHtml(fmtDate(item.published)) : "")
    + " &nbsp;&middot;&nbsp; <span class='reader-badge " + bc + "'>" + item.score + "</span>";

  document.getElementById("reader-body").textContent = item.content || item.snippet || "";


  var actEl = document.getElementById("reader-actions");
  actEl.innerHTML = "";
  [["zotero","✅ Zotero"],["read","📖 Later lezen"],["skip","👎 Overslaan"]].forEach(function(pair) {{
    var btn = document.createElement("button");
    btn.textContent = pair[1];
    btn.addEventListener("click", (function(t, b) {{
      return function() {{ rvAct(t, item, b); }};
    }})(pair[0], btn));
    actEl.appendChild(btn);
  }});

  var btnU = document.createElement("button");
  btnU.textContent = "↩ Ongelezen";
  btnU.addEventListener("click", function() {{
    var s = getRead(); s.delete(item.url);
    localStorage.setItem(READ_KEY, JSON.stringify([...s]));
    document.querySelectorAll(".item[data-url]").forEach(function(el) {{
      if (el.dataset.url === item.url) el.classList.remove("read");
    }});
  }});
  actEl.appendChild(btnU);
}}

/* ── List rendering ── */
function makeItem(item, read, skipped) {{
  const isRead    = read.has(item.url);
  const isSkipped = skipped.has(item.url);
  const div = document.createElement("div");
  div.className = "item"
    + (isRead    ? " read"     : "")
    + (isSkipped ? " skipped"  : "")
    + (item.url === selectedUrl ? " selected" : "");
  div.dataset.url = item.url;

  var badge = document.createElement("span");
  badge.className = "badge " + badgeClass(item.score);
  badge.textContent = item.score;
  div.appendChild(badge);

  var body = document.createElement("div");
  body.className = "item-body";
  var titleDiv = document.createElement("div");
  titleDiv.className = "item-title";
  titleDiv.textContent = item.title;
  body.appendChild(titleDiv);
  var metaDiv = document.createElement("div");
  metaDiv.className = "item-meta";
  metaDiv.textContent = item.source + (item.published ? " · " + fmtDate(item.published) : "");
  body.appendChild(metaDiv);
  div.appendChild(body);

  var skipBtn = document.createElement("button");
  skipBtn.className = "skip-btn";
  skipBtn.title = "Overslaan";
  skipBtn.textContent = "👎";
  skipBtn.addEventListener("click", function(e) {{
    e.stopPropagation();
    markSkippedLocal(item.url);
    div.classList.add("skipped");
    if (hideRead) div.classList.add("hidden");
    fetch("/skip", {{
      method: "POST",
      headers: {{"Content-Type": "application/json"}},
      body: JSON.stringify({{url: item.url, title: item.title, timestamp: new Date().toISOString()}})
    }}).catch(function() {{}});
  }});
  div.appendChild(skipBtn);

  div.addEventListener("click", function() {{
    if (!div.classList.contains("skipped")) {{
      div.classList.add("read");
      markRead(item.url);
      showReader(item);
    }}
  }});
  return div;
}}

function renderScore() {{
  var el = document.getElementById("view-score");
  el.innerHTML = "";
  var read = getRead(), skipped = getSkipped();
  visibleItems().forEach(function(item) {{ el.appendChild(makeItem(item, read, skipped)); }});
}}
function renderSource() {{
  var el = document.getElementById("view-source");
  el.innerHTML = "";
  var read = getRead(), skipped = getSkipped(), groups = {{}};
  visibleItems().forEach(function(item) {{
    if (!groups[item.source]) groups[item.source] = [];
    groups[item.source].push(item);
  }});
  Object.keys(groups).sort().forEach(function(src) {{
    var grp = document.createElement("div");
    grp.className = "source-group";
    var h = document.createElement("div");
    h.className = "source-heading";
    h.textContent = src + " (" + groups[src].length + ")";
    grp.appendChild(h);
    groups[src].forEach(function(item) {{ grp.appendChild(makeItem(item, read, skipped)); }});
    el.appendChild(grp);
  }});
}}
function renderDate() {{
  var el = document.getElementById("view-date");
  el.innerHTML = "";
  var read = getRead(), skipped = getSkipped();
  var sorted = visibleItems().slice().sort(function(a, b) {{
    if (!a.published) return 1;
    if (!b.published) return -1;
    return b.published.localeCompare(a.published);
  }});
  sorted.forEach(function(item) {{ el.appendChild(makeItem(item, read, skipped)); }});
}}
function renderAll() {{ renderScore(); renderSource(); renderDate(); }}

function switchView(name, btn) {{
  document.querySelectorAll(".view").forEach(function(v) {{ v.classList.remove("active"); }});
  document.querySelectorAll(".tabs button").forEach(function(b) {{ b.classList.remove("active"); }});
  document.getElementById("view-" + name).classList.add("active");
  btn.classList.add("active");
}}
function toggleRead() {{
  hideRead = !hideRead;
  document.querySelectorAll(".item.read, .item.skipped").forEach(function(el) {{
    el.classList.toggle("hidden", hideRead);
  }});
  document.querySelector(".toggle-read").textContent =
    hideRead ? "toon alles" : "verberg gelezen / overgeslagen";
}}
function toggleTerminal() {{
  var panel  = document.getElementById("terminal-panel");
  var iframe = document.getElementById("term-iframe");
  var btn    = document.getElementById("term-btn");
  var open   = panel.classList.toggle("visible");
  btn.style.fontWeight = open ? "700" : "";
  if (open && iframe.src === "about:blank") {{
    iframe.src = "http://" + window.location.hostname + ":7681/?";
  }}
}}

renderAll();
</script>
</body>
</html>
"""


# ── Hoofdprogramma ────────────────────────────────────────────────────────────

def main():
    print("\n📡 feedreader-score — RSS-feeds scoren")
    print("=" * 52)

    # Serveermap aanmaken indien nodig
    SERVE_DIR.mkdir(exist_ok=True)

    # 1. Feeds laden
    if not FEEDS_FILE.exists():
        print(f"❌  {FEEDS_FILE} niet gevonden.")
        return
    feed_urls = load_feeds(FEEDS_FILE)
    if not feed_urls:
        print("⚠️  Geen feed-URLs gevonden in feedreader-list.txt.")
        return
    print(f"\n[1/5] {len(feed_urls)} feed(s) geladen.")

    # 2. ChromaDB-profiel opbouwen
    print("[2/5] Voorkeursprofiel laden uit ChromaDB...")
    if not ZOTERO_SQLITE.exists():
        print(f"❌  Zotero database niet gevonden: {ZOTERO_SQLITE}")
        return

    tmp_db = make_sqlite_copy(ZOTERO_SQLITE)
    conn = sqlite3.connect(tmp_db)
    try:
        lib_weights = get_library_keys_with_weights(conn, INBOX_ID)
    finally:
        conn.close()
        os.unlink(tmp_db)

    chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    chroma_col    = chroma_client.get_collection("zotero_library")
    lib_embeddings = get_embeddings_for_keys(chroma_col, list(lib_weights.keys()))

    if not lib_embeddings:
        print("❌  Geen bibliotheek-embeddings gevonden. Voer eerst 'update-zotero' uit.")
        return

    profile = compute_weighted_profile(lib_embeddings, lib_weights)
    print(f"     Profiel gebaseerd op {len(lib_embeddings)} bibliotheekitems.")

    # 3. Feeds ophalen en items verzamelen
    print("[3/5] Feeds ophalen...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    existing_urls = load_existing_log(LOG_FILE)
    all_items = []
    new_log_entries = []

    for feed_url in feed_urls:
        try:
            parsed = feedparser.parse(feed_url, request_headers={"User-Agent": "Mozilla/5.0"})
            feed_name = parsed.feed.get("title", feed_url)
            entries   = parsed.entries[:50]  # max 50 items per feed
            print(f"     {feed_name}: {len(entries)} items")
        except Exception as e:
            print(f"     ⚠️  Fout bij ophalen {feed_url}: {e}")
            continue

        for entry in entries:
            url   = entry.get("link", "")
            title = strip_html(entry.get("title", "(geen titel)"))

            # Beschrijving: probeer zo veel mogelijk tekst te pakken
            description = ""
            if entry.get("content"):
                description = strip_html(entry["content"][0].get("value", ""))
            elif entry.get("summary"):
                description = strip_html(entry.get("summary", ""))

            # Publicatiedatum
            published = ""
            if entry.get("published_parsed"):
                try:
                    dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    published = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                except Exception:
                    pass

            source_type = detect_source_type(feed_url, entry)
            score_text = title
            transcript_snippet = ""
            if description:
                score_text += " " + description[:1000]

            # YouTube-transcriptverrijking voor betere scoring
            video_id = None
            has_transcript = False
            if source_type == "youtube":
                video_id = extract_video_id(url)
                if video_id:
                    transcript = fetch_and_cache_transcript(
                        video_id, title, feed_name, url, published
                    )
                    if transcript:
                        score_text += " " + transcript[:3000]
                        has_transcript = True
                        transcript_snippet = transcript[:2000]

            # Podcast show notes cachen voor artikelgeneratie
            episode_id = None
            has_shownotes = False
            if source_type == "podcast" and len(description) >= SHOWNOTES_MIN_LENGTH:
                episode_id = "podcast_" + hashlib.md5(url.encode()).hexdigest()
                cache_podcast_shownotes(episode_id, title, feed_name, url, published, description)
                has_shownotes = True

            all_items.append({
                "url":            url,
                "title":          title,
                "description":    description,
                "feed_name":      feed_name,
                "feed_url":       feed_url,
                "published":      published,
                "source_type":    source_type,
                "score_text":     score_text,
                "video_id":       video_id,
                "has_transcript": has_transcript,
                "episode_id":     episode_id,
                "has_shownotes":       has_shownotes,
                "transcript_snippet": transcript_snippet,
            })

    if not all_items:
        print("⚠️  Geen items gevonden in de feeds.")
        return

    # 4. Scoren
    yt_transcripts = sum(1 for i in all_items if i.get("has_transcript"))
    if yt_transcripts:
        print(f"     {yt_transcripts} YouTube-transcript(en) beschikbaar voor verrijkte scoring")
    print(f"[4/5] {len(all_items)} items scoren...")
    texts = [item["score_text"] for item in all_items]
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=False)

    now = datetime.now(timezone.utc)
    for item, emb in zip(all_items, embeddings):
        sim   = cosine_similarity(np.array(emb, dtype=np.float32), profile)
        score = max(0, min(100, int(round(sim * 100))))
        item["score"] = score

        # Log alleen nieuwe items (op basis van URL)
        if item["url"] and item["url"] not in existing_urls:
            new_log_entries.append({
                "url":             item["url"],
                "title":           item["title"],
                "score":           score,
                "feed_name":       item["feed_name"],
                "source_type":     item["source_type"],
                "timestamp":       now.isoformat(),
                "text_length":     len(item["score_text"]),
                "added_to_zotero": None,
            })

    # Sorteren op score descending
    all_items.sort(key=lambda x: x["score"], reverse=True)

    # Datumfilter: academisch max 365 dagen, overig max 30 dagen
    all_items = [
        i for i in all_items
        if within_max_age(
            i["published"],
            MAX_AGE_DAYS_ACADEMIC if is_academic_feed(i["feed_url"]) else MAX_AGE_DAYS_DEFAULT,
            now,
        )
    ]

    # 5. Atom-feed en HTML-pagina schrijven
    print("[5/5] Atom-feed en HTML-pagina genereren...")

    # Type-gefilterde feeds voor NetNewsWire
    for source_type, filename, label, emoji in [
        ("youtube", "youtube",  "YouTube-video's", "▶️"),
        ("podcast", "podcast",  "Podcasts",        "🎙️"),
        ("web",     "webpage",  "Webartikelen",   "📄"),
    ]:
        subset = [i for i in all_items if i["source_type"] == source_type][:MAX_FEED_ITEMS]
        path   = SERVE_DIR / f"filtered-{filename}.xml"
        path.write_text(
            generate_atom(subset, now, feed_title=f"Feedreader {emoji} {label}"),
            encoding="utf-8",
        )

    html_str  = generate_html(all_items, now)
    html_path = SERVE_DIR / "filtered.html"
    html_path.write_text(html_str, encoding="utf-8")

    # Logboek bijwerken
    if new_log_entries:
        append_log(LOG_FILE, new_log_entries)

    # ── Samenvatting ──────────────────────────────────────────────────────────
    green  = sum(1 for i in all_items if i["score"] >= THRESHOLD_GREEN)
    yellow = sum(1 for i in all_items if THRESHOLD_YELLOW <= i["score"] < THRESHOLD_GREEN)
    red    = sum(1 for i in all_items if i["score"] < THRESHOLD_YELLOW)

    print(f"\n{'=' * 52}")
    print(f"✅  {len(all_items)} items verwerkt")
    print(f"🟢 {green} sterk  🟡 {yellow} mogelijk  🔴 {red} zwak")
    print(f"📝 {len(new_log_entries)} nieuwe items toegevoegd aan score_log.jsonl")
    print(f"\n   XML YouTube:   http://localhost:8765/filtered-youtube.xml")
    print(f"   XML Podcasts:  http://localhost:8765/filtered-podcast.xml")
    print(f"   XML Web:       http://localhost:8765/filtered-webpage.xml")
    print(f"   HTML:          http://localhost:8765/filtered.html\n")


if __name__ == "__main__":
    main()
