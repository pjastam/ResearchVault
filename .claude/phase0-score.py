#!/usr/bin/env python3
"""
phase0-score.py — RSS-feeds scoren en gefilterde Atom-feed genereren
=====================================================================
Haalt alle feeds op uit phase0-feeds.txt, scoort elk item op relevantie
aan de hand van het ChromaDB-voorkeursprofiel, en schrijft een gesorteerde
Atom-feed naar phase0-serve/filtered.xml.

Gebruik:
    python3 phase0-score.py

Vereisten:
    feedparser, chromadb, numpy, sentence_transformers

Configuratie (pas aan indien nodig):
    FEEDS_FILE      — pad naar de lijst van feed-URLs
    SERVE_DIR       — map waar filtered.xml wordt weggeschreven
    LOG_FILE        — pad naar het score-logboek (score_log.jsonl)
    CHROMA_PATH     — pad naar ChromaDB directory
    ZOTERO_SQLITE   — pad naar Zotero SQLite database
    INBOX_ID        — collectionID van _inbox in Zotero
    WEIGHT_*        — gewichten voor het voorkeursprofiel
"""

import hashlib
import html
import json
import os
import re
import shutil
import sqlite3
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import chromadb
import feedparser
import numpy as np
from sentence_transformers import SentenceTransformer

from phase0_core import (
    THRESHOLD_GREEN,
    THRESHOLD_YELLOW,
    WEIGHT_DEFAULT,
    WEIGHT_ANNOTATIONS,
    cosine_similarity,
    compute_weighted_profile,
    score_label,
    detect_source_type,
)

# optionele afhankelijkheid — transcript-verrijking werkt alleen als dit pakket geïnstalleerd is
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    _YT_API_OK = True
except ImportError:
    _YT_API_OK = False

# ── Configuratie ──────────────────────────────────────────────────────────────

SCRIPT_DIR    = Path(__file__).parent
FEEDS_FILE    = SCRIPT_DIR / "phase0-feeds.txt"
SERVE_DIR     = Path.home() / ".local" / "share" / "phase0-serve"
LOG_FILE      = SCRIPT_DIR / "score_log.jsonl"
CHROMA_PATH   = Path.home() / ".config" / "zotero-mcp" / "chroma_db"
ZOTERO_SQLITE = Path.home() / "Zotero" / "zotero.sqlite"
INBOX_ID      = 333

FEED_TIMEOUT = 15  # seconden per feed
TRANSCRIPT_CACHE_DIR = SCRIPT_DIR / "transcript_cache"
SHOWNOTES_MIN_LENGTH = 200  # minimale tekenlengte voor podcast show notes om artikel te genereren

# ── Hulpfuncties ──────────────────────────────────────────────────────────────

def strip_html(text: str) -> str:
    """Verwijdert HTML-tags en decodeert HTML-entiteiten."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


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


def make_sqlite_copy(source: Path) -> Path:
    tmp = tempfile.mktemp(suffix=".sqlite")
    shutil.copy2(source, tmp)
    return Path(tmp)


def get_library_keys_with_weights(conn: sqlite3.Connection, inbox_id: int) -> dict[str, float]:
    cur = conn.execute("""
        SELECT DISTINCT i.key
        FROM items i
        WHERE i.itemID NOT IN (
            SELECT itemID FROM collectionItems WHERE collectionID = ?
        )
        AND i.itemID NOT IN (SELECT itemID FROM deletedItems)
        AND i.itemTypeID NOT IN (
            SELECT itemTypeID FROM itemTypes WHERE typeName IN ('note', 'attachment')
        )
    """, (inbox_id,))
    all_keys = {row[0]: float(WEIGHT_DEFAULT) for row in cur.fetchall()}

    if not all_keys:
        return all_keys

    cur = conn.execute("""
        SELECT DISTINCT i.key
        FROM items i
        JOIN itemAttachments ia ON ia.parentItemID = i.itemID
        JOIN itemAnnotations ann ON ann.parentItemID = ia.itemID
        WHERE i.key IN ({})
    """.format(",".join("?" * len(all_keys))), list(all_keys.keys()))
    for row in cur.fetchall():
        if row[0] in all_keys:
            all_keys[row[0]] += WEIGHT_ANNOTATIONS

    return all_keys


def get_embeddings_for_keys(collection, keys: list[str]) -> dict[str, np.ndarray]:
    if not keys:
        return {}
    result = collection.get(ids=keys, include=["embeddings"])
    return {
        item_id: np.array(emb, dtype=np.float32)
        for item_id, emb in zip(result["ids"], result["embeddings"])
    }




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
    """Voegt nieuwe entries toe aan het JSONL-logboek."""
    with path.open("a", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


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
        except Exception:
            pass

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
    Zet score (0–100) om naar een nep-publicatiedatum zodat NetNewsWire
    op datum kan sorteren, wat overeenkomt met sorteren op relevantie.
    Score 100 → generated_at, score 0 → generated_at - 100 dagen.
    """
    offset_days = 100 - score
    dt = generated_at - timedelta(days=offset_days)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_atom(items: list[dict], generated_at: datetime) -> str:
    """Genereert een Atom 1.0 feed als string."""
    ts = generated_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    entries = []
    for item in items:
        label     = score_label(item["score"])
        title     = atom_escape(f"{label} {item['score']:3d} | {item['title']}")
        link      = atom_escape(item["url"])
        feed_name = atom_escape(item["feed_name"])
        summary   = atom_escape(item.get("description", "")[:500])
        entry_id  = atom_escape(item.get("url", str(uuid.uuid4())))
        updated   = score_to_fake_date(item["score"], generated_at)

        entries.append(f"""  <entry>
    <title>{title}</title>
    <link href="{link}"/>
    <id>{entry_id}</id>
    <updated>{updated}</updated>
    <category term="{feed_name}"/>
    <summary>{summary}</summary>
  </entry>""")

    entries_xml = "\n".join(entries)
    return f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Phase 0 — Gefilterde RSS-feed</title>
  <id>urn:phase0:filtered-feed</id>
  <updated>{ts}</updated>
  <author><name>phase0-score.py</name></author>
{entries_xml}
</feed>
"""


def generate_html(items: list[dict], generated_at: datetime) -> str:
    """Genereert een zelfstandige HTML-pagina met score- en bronweergave."""
    import json as _json

    date_str = generated_at.strftime("%-d %b %Y, %H:%M")

    # Gegevens als JSON voor JavaScript — alleen wat de UI nodig heeft
    data = _json.dumps([
        {
            "url":       item["url"],
            "href":      (
                f"/article/{item['video_id']}" if item.get("has_transcript")
                else f"/article/podcast/{item.get('episode_id', '')}" if item.get("has_shownotes")
                else item["url"]
            ),
            "title":     item["title"],
            "score":     item["score"],
            "label":     score_label(item["score"]),
            "source":    item["feed_name"],
            "type":      item["source_type"],
            "desc":      item.get("description", "")[:200],
            "published": item.get("published", ""),
        }
        for item in items
    ], ensure_ascii=False)

    green  = sum(1 for i in items if i["score"] >= THRESHOLD_GREEN)
    yellow = sum(1 for i in items if THRESHOLD_YELLOW <= i["score"] < THRESHOLD_GREEN)
    red    = sum(1 for i in items if i["score"] < THRESHOLD_YELLOW)
    total  = len(items)

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
    --read-op: 0.35;
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
  #layout {{
    display: flex; height: calc(100vh - 48px);
  }}
  #content-panel {{
    flex: 1; overflow-y: auto; min-width: 0;
  }}
  #terminal-panel {{
    display: none; flex-shrink: 0; width: 45%;
    border-left: 1px solid var(--border);
    background: #1e1e1e;
  }}
  #terminal-panel.visible {{ display: flex; flex-direction: column; }}
  #terminal-panel iframe {{
    flex: 1; border: none; width: 100%; height: 100%;
  }}
  @media (max-width: 800px) {{
    #layout {{ flex-direction: column; height: auto; }}
    #terminal-panel {{ width: 100%; height: 60vh; border-left: none; border-top: 1px solid var(--border); }}
  }}
  .view {{ display: none; padding: .75rem 1rem; max-width: 720px; margin: 0 auto; }}
  .view.active {{ display: block; }}
  .source-group {{ margin-bottom: 1.5rem; }}
  .source-heading {{
    font-size: .75rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: .05em; color: var(--muted);
    padding: .5rem 0 .25rem; border-bottom: 1px solid var(--border);
    margin-bottom: .5rem;
  }}
  .item {{
    display: flex; gap: .6rem; align-items: flex-start;
    padding: .55rem .5rem; border-radius: 8px;
    cursor: pointer; transition: background .1s;
  }}
  .item:hover {{ background: var(--border); }}
  .item.read {{ opacity: var(--read-op); }}
  .item.read.hidden {{ display: none; }}
  .item.skipped {{ opacity: var(--read-op); }}
  .item.skipped .item-title {{ text-decoration: line-through; }}
  .item.skipped.hidden {{ display: none; }}
  .skip-btn {{
    flex-shrink: 0; background: none; border: none;
    cursor: pointer; font-size: .85rem;
    padding: .25rem .4rem; border-radius: 5px;
    opacity: 0.2; line-height: 1;
    transition: opacity .15s;
  }}
  .skip-btn:hover {{ opacity: 0.9; background: var(--border); }}
  .item.skipped .skip-btn {{ display: none; }}
  .badge {{
    flex-shrink: 0; min-width: 2.4rem;
    font-size: .75rem; font-weight: 700;
    padding: .15rem .35rem; border-radius: 5px;
    text-align: center; margin-top: .1rem;
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
    font-size: .9rem; line-height: 1.35;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }}
  .item-meta {{ font-size: .75rem; color: var(--muted); margin-top: .1rem; }}
  a {{ color: inherit; text-decoration: none; }}
</style>
</head>
<body>
<header>
  <h1>Phase 0</h1>
  <span class="stats">
    🟢 {green} &nbsp;🟡 {yellow} &nbsp;🔴 {red} &nbsp;·&nbsp; {date_str}
  </span>
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
  <div id="content-panel">
    <div id="view-score" class="view active"></div>
    <div id="view-source" class="view"></div>
    <div id="view-date" class="view"></div>
  </div>
  <div id="terminal-panel">
    <iframe id="term-iframe" src="about:blank"></iframe>
  </div>
</div>

<script>
const ITEMS = {data};
const READ_KEY = "phase0_read";

function getRead() {{
  try {{ return new Set(JSON.parse(localStorage.getItem(READ_KEY) || "[]")); }}
  catch {{ return new Set(); }}
}}
function markRead(url) {{
  const s = getRead(); s.add(url);
  localStorage.setItem(READ_KEY, JSON.stringify([...s]));
}}
const SKIP_KEY = "phase0_skipped";
function getSkipped() {{
  try {{ return new Set(JSON.parse(localStorage.getItem(SKIP_KEY) || "[]")); }}
  catch {{ return new Set(); }}
}}
function markSkippedLocal(url) {{
  const s = getSkipped(); s.add(url);
  localStorage.setItem(SKIP_KEY, JSON.stringify([...s]));
}}
function skipItem(url, title, el) {{
  markSkippedLocal(url);
  el.classList.add("skipped");
  if (hideRead) el.classList.add("hidden");
  fetch("/skip", {{
    method: "POST",
    headers: {{"Content-Type": "application/json"}},
    body: JSON.stringify({{url, title, timestamp: new Date().toISOString()}})
  }}).catch(() => {{}});
}}

let currentType = "all";
function setType(type, btn) {{
  currentType = type;
  document.querySelectorAll(".type-filter button").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  renderScore();
  renderSource();
  renderDate();
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

function makeItem(item, read, skipped) {{
  const isRead    = read.has(item.url);
  const isSkipped = skipped.has(item.url);
  const div = document.createElement("div");
  div.className = "item" + (isRead ? " read" : "") + (isSkipped ? " skipped" : "");
  div.dataset.url = item.url;
  div.innerHTML = `
    <span class="badge ${{badgeClass(item.score)}}">${{item.score}}</span>
    <div class="item-body">
      <div class="item-title">
        <a href="${{item.href}}" target="_blank" rel="noopener">${{escHtml(item.title)}}</a>
      </div>
      <div class="item-meta">${{escHtml(item.source)}}${{item.published ? " · " + fmtDate(item.published) : ""}}</div>
    </div>`;
  div.querySelector("a").addEventListener("click", (e) => {{
    e.stopPropagation();
    div.classList.add("read");
    markRead(item.url);
  }});
  const btn = document.createElement("button");
  btn.className = "skip-btn";
  btn.title = "Niet interessant";
  btn.textContent = "👎";
  btn.addEventListener("click", (e) => {{
    e.stopPropagation();
    skipItem(item.url, item.title, div);
  }});
  div.appendChild(btn);
  div.addEventListener("click", () => {{
    if (!div.classList.contains("skipped")) {{
      div.classList.add("read");
      markRead(item.url);
      window.open(item.href, "_blank", "noopener");
    }}
  }});
  return div;
}}

function escHtml(s) {{
  return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}}

function renderScore() {{
  const el = document.getElementById("view-score");
  el.innerHTML = "";
  const read    = getRead();
  const skipped = getSkipped();
  visibleItems().forEach(item => el.appendChild(makeItem(item, read, skipped)));
}}

function renderSource() {{
  const el = document.getElementById("view-source");
  el.innerHTML = "";
  const read    = getRead();
  const skipped = getSkipped();
  const groups  = {{}};
  visibleItems().forEach(item => {{
    if (!groups[item.source]) groups[item.source] = [];
    groups[item.source].push(item);
  }});
  Object.entries(groups).sort().forEach(([src, items]) => {{
    const grp = document.createElement("div");
    grp.className = "source-group";
    const h = document.createElement("div");
    h.className = "source-heading";
    h.textContent = src + " (" + items.length + ")";
    grp.appendChild(h);
    items.forEach(item => grp.appendChild(makeItem(item, read, skipped)));
    el.appendChild(grp);
  }});
}}

function renderDate() {{
  const el = document.getElementById("view-date");
  el.innerHTML = "";
  const read    = getRead();
  const skipped = getSkipped();
  const sorted  = [...visibleItems()].sort((a, b) => {{
    if (!a.published) return 1;
    if (!b.published) return -1;
    return b.published.localeCompare(a.published);
  }});
  sorted.forEach(item => el.appendChild(makeItem(item, read, skipped)));
}}

function switchView(name, btn) {{
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
  document.querySelectorAll(".tabs button").forEach(b => b.classList.remove("active"));
  document.getElementById("view-" + name).classList.add("active");
  btn.classList.add("active");
}}

let hideRead = false;
function toggleRead() {{
  hideRead = !hideRead;
  document.querySelectorAll(".item.read, .item.skipped").forEach(el => {{
    el.classList.toggle("hidden", hideRead);
  }});
  document.querySelector(".toggle-read").textContent =
    hideRead ? "toon alles" : "verberg gelezen / overgeslagen";
}}

renderScore();
renderSource();
renderDate();

function toggleTerminal() {{
  const panel = document.getElementById("terminal-panel");
  const iframe = document.getElementById("term-iframe");
  const btn    = document.getElementById("term-btn");
  const open   = panel.classList.toggle("visible");
  btn.style.fontWeight = open ? "700" : "";
  if (open && iframe.src === "about:blank") {{
    iframe.src = "http://" + window.location.hostname + ":7681/?";
  }}
}}
</script>
</body>
</html>
"""


# ── Hoofdprogramma ────────────────────────────────────────────────────────────

def main():
    print("\n📡 phase0-score — RSS-feeds scoren")
    print("=" * 52)

    # Serveermap aanmaken indien nodig
    SERVE_DIR.mkdir(exist_ok=True)

    # 1. Feeds laden
    if not FEEDS_FILE.exists():
        print(f"❌  {FEEDS_FILE} niet gevonden.")
        return
    feed_urls = load_feeds(FEEDS_FILE)
    if not feed_urls:
        print("⚠️  Geen feed-URLs gevonden in phase0-feeds.txt.")
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

            # Podcast show notes cachen voor artikelgeneratie
            episode_id = None
            has_shownotes = False
            if source_type == "podcast" and len(description) >= SHOWNOTES_MIN_LENGTH:
                episode_id = "podcast_" + hashlib.md5(url.encode()).hexdigest()[:16]
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
                "has_shownotes":  has_shownotes,
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

    # 5. Atom-feed en HTML-pagina schrijven
    print("[5/5] Atom-feed en HTML-pagina genereren...")
    atom_xml  = generate_atom(all_items, now)
    feed_path = SERVE_DIR / "filtered.xml"
    feed_path.write_text(atom_xml, encoding="utf-8")

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
    print(f"\n   XML:  http://localhost:8765/filtered.xml  (NetNewsWire)")
    print(f"   HTML: http://localhost:8765/filtered.html (browser)\n")


if __name__ == "__main__":
    main()
