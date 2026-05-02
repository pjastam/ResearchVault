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
import socket
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
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
    THRESHOLD_STAR,
    PRIOR_RELEVANCE,
    WEIGHT_DEFAULT,
    WEIGHT_ANNOTATIONS,
    cosine_similarity,
    compute_weighted_profile,
    bayesian_score,
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

_hn = socket.gethostname()
SERVER_HOST = _hn if _hn.endswith(".local") else _hn + ".local"

SCRIPT_DIR    = Path(__file__).parent
FEEDS_FILE    = SCRIPT_DIR / "feedreader-list.txt"
SERVE_DIR     = Path.home() / ".local" / "share" / "feedreader-serve"
LOG_FILE      = SCRIPT_DIR / "score_log.jsonl"
STAR_QUEUE    = Path("/tmp/feedreader-star-queue.txt")
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
PURE_CACHE_DIR       = SCRIPT_DIR / "pure_cache"
PURE_FEED_PATTERNS   = ("pure.eur.nl", "research.vu.nl")
# Minimum show notes length (chars) to be usable for content-based scoring and article generation;
# shorter entries contain too little context for a meaningful embedding.
SHOWNOTES_MIN_LENGTH = 200

# ── Hulpfuncties ──────────────────────────────────────────────────────────────

def is_academic_feed(feed_url: str) -> bool:
    return any(pat in feed_url for pat in ACADEMIC_FEED_PATTERNS)


def is_pure_feed(feed_url: str) -> bool:
    return any(p in feed_url for p in PURE_FEED_PATTERNS)


def _extract_pure_metadata_from_html(html_text: str) -> dict:
    """
    Haalt bibliografische metadata op uit een PURE-publicatiepagina.

    Strategie:
      1. JSON-LD (<script type="application/ld+json">) — betrouwbaar voor
         abstract, auteurs, DOI, tijdschrift, ISSN en publicatiedatum.
      2. HTML-fallback — vangt volume, jaargang en pagina's op die PURE
         doorgaans niet in JSON-LD zet.
    """
    meta: dict = {}

    # ── 1. JSON-LD ────────────────────────────────────────────────────────
    for jld_m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text, re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(jld_m.group(1))
        except json.JSONDecodeError:
            continue

        nodes = (
            data if isinstance(data, list)
            else data.get("@graph", [data]) if isinstance(data, dict)
            else []
        )
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_type = node.get("@type", "")
            scholarly = any(t in node_type for t in (
                "ScholarlyArticle", "Article", "Thesis",
                "Book", "CreativeWork", "Report",
            ))
            if not scholarly:
                continue

            if node.get("description") and not meta.get("abstract"):
                meta["abstract"] = re.sub(r"\s+", " ", str(node["description"])).strip()
            if node.get("name") and not meta.get("title"):
                meta["title"] = node["name"]

            # Auteurs
            if node.get("author") and not meta.get("authors"):
                raw = node["author"]
                if isinstance(raw, dict):
                    raw = [raw]
                meta["authors"] = [
                    a["name"] for a in raw
                    if isinstance(a, dict) and a.get("name")
                ]

            # DOI via sameAs (kan string of lijst zijn)
            same_as = node.get("sameAs", [])
            if isinstance(same_as, str):
                same_as = [same_as]
            for s in same_as:
                m = re.search(r'doi\.org/(10\.[^\s"<>]+)', s)
                if m and not meta.get("doi"):
                    meta["doi"] = m.group(1).rstrip(".,")

            # Tijdschrift + ISSN
            is_part_of = node.get("isPartOf") or {}
            if isinstance(is_part_of, dict):
                if is_part_of.get("name") and not meta.get("journal"):
                    meta["journal"] = is_part_of["name"]
                issn = is_part_of.get("issn") or is_part_of.get("issn-l", "")
                if issn and not meta.get("issn"):
                    meta["issn"] = (issn[0] if isinstance(issn, list) else issn)

            if node.get("datePublished") and not meta.get("date_published"):
                meta["date_published"] = str(node["datePublished"])[:10]

            if node.get("keywords") and not meta.get("keywords"):
                kw = node["keywords"]
                meta["keywords"] = (
                    kw if isinstance(kw, list)
                    else [k.strip() for k in str(kw).split(",")]
                )

    # ── 2. HTML-fallback voor ontbrekende velden ──────────────────────────

    # Abstract
    if not meta.get("abstract"):
        for pat in (
            r'class="[^"]*\brendering_abstractportal\b[^"]*"[^>]*>(.*?)</div>',
            r'class="[^"]*\babstract\b[^"]*"[^>]*>(.*?)</(?:div|section)>',
            r'<h[23][^>]*>\s*Abstract\s*</h[23]>\s*<p[^>]*>(.*?)</p>',
        ):
            m = re.search(pat, html_text, re.DOTALL | re.IGNORECASE)
            if m:
                candidate = strip_html(m.group(1))
                if len(candidate) > 50:
                    meta["abstract"] = candidate
                    break

    # DOI
    if not meta.get("doi"):
        m = re.search(r'https?://doi\.org/(10\.[^\s"<>]+)', html_text)
        if m:
            meta["doi"] = m.group(1).rstrip(".,")

    # Volume — eerst PURE span-klasse, daarna vrije tekst
    if not meta.get("volume"):
        m = re.search(
            r'<[^>]+class="[^"]*\bvolume\b[^"]*"[^>]*>\s*(\d+)\s*</',
            html_text, re.IGNORECASE,
        )
        if not m:
            m = re.search(r'\bvol(?:ume)?\.?\s+(\d+)', html_text, re.IGNORECASE)
        if m:
            meta["volume"] = m.group(1)

    # Issue/number
    if not meta.get("issue"):
        m = re.search(
            r'<[^>]+class="[^"]*\b(?:issue|number)\b[^"]*"[^>]*>\s*(\d+)\s*</',
            html_text, re.IGNORECASE,
        )
        if not m:
            m = re.search(r'\bno\.?\s*(\d+)', html_text, re.IGNORECASE)
        if m:
            meta["issue"] = m.group(1)

    # Pagina's — span-klasse of pp.-notatie
    if not meta.get("pages"):
        m = re.search(
            r'<[^>]+class="[^"]*\bpages\b[^"]*"[^>]*>\s*([\d]+\s*[-–]\s*[\d]+)\s*</',
            html_text, re.IGNORECASE,
        )
        if not m:
            m = re.search(r'\bpp?\.?\s*([\d]+\s*[-–]\s*[\d]+)', html_text, re.IGNORECASE)
        if m:
            meta["pages"] = re.sub(r"\s", "", m.group(1))

    return meta


def fetch_pure_metadata(url: str) -> dict:
    """
    Haalt bibliografische metadata op van een PURE-publicatiepagina en
    cachet het resultaat in pure_cache/{url_hash}.json.

    Bij een netwerk- of parsefout wordt alsnog een cache-bestand geschreven
    (met 'error'-sleutel) om herhaalde pogingen te voorkomen. Geeft
    altijd een dict terug — leeg bij fatale fout.
    """
    cache_key  = hashlib.md5(url.encode()).hexdigest()
    cache_file = PURE_CACHE_DIR / f"{cache_key}.json"

    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass  # beschadigd bestand — opnieuw ophalen

    meta: dict = {
        "url":        url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; feedreader-score/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            html_text = resp.read().decode("utf-8", errors="replace")
        meta.update(_extract_pure_metadata_from_html(html_text))
    except Exception as exc:
        meta["error"] = str(exc)

    PURE_CACHE_DIR.mkdir(exist_ok=True)
    cache_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


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

    Toont alleen tekstinhoud per brontype (transcript, show notes of lange
    beschrijving). Geen actieknoppen — NNW-sterren dienen als enige
    in-app signaal; de leerloop leest de ster-status via de GReader API.

    De content wordt als CDATA ingebed zodat geen dubbele XML-escaping nodig is.
    """
    source_type = item.get("source_type", "web")
    parts = []

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

    content = "\n".join(parts)
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

            # PURE-verrijking: abstract + bibliografische velden ophalen van de publicatiepagina.
            # PURE-feeds leveren alleen een titel; de pagina zelf bevat abstract, auteurs,
            # DOI, tijdschrift, volume, jaargang en pagina's.
            pure_meta: dict = {}
            if source_type == "web" and is_pure_feed(feed_url):
                _cache_path  = PURE_CACHE_DIR / f"{hashlib.md5(url.encode()).hexdigest()}.json"
                _was_cached  = _cache_path.exists()
                pure_meta    = fetch_pure_metadata(url)
                if not _was_cached and not pure_meta.get("error"):
                    time.sleep(0.3)  # beleefd wachten bij nieuwe HTTP-requests
                abstract = pure_meta.get("abstract", "")
                if abstract:
                    description = abstract          # vult de anders-lege feed-beschrijving
                    score_text  = title + " " + abstract[:1000]

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
                "episode_id":          episode_id,
                "has_shownotes":       has_shownotes,
                "transcript_snippet":  transcript_snippet,
                "pure_meta":           pure_meta,
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
        sim             = cosine_similarity(np.array(emb, dtype=np.float32), profile)
        raw             = max(0, min(100, int(round(sim * 100))))
        item["score_raw"] = raw
        item["score"]     = bayesian_score(raw)


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

    # Deduplicatiefilter: alleen items tonen die nog niet eerder zijn gezien
    all_items = [i for i in all_items if i["url"] not in existing_urls]

    # Log alleen wat daadwerkelijk in de output terechtkomt (na leeftijds- en deduplicatiefilter)
    new_log_entries = [
        {
            "url":             item["url"],
            "title":           item["title"],
            "score":           item["score"],
            "score_raw":       item["score_raw"],
            "feed_name":       item["feed_name"],
            "source_type":     item["source_type"],
            "timestamp":       now.isoformat(),
            "text_length":     len(item["score_text"]),
            "added_to_zotero": None,
        }
        for item in all_items
        if item["url"]
    ]

    # 4b. Star-kandidaten opslaan voor verwerking in feedreader-learn.py (na freshrss actualize)
    star_candidates = [i["url"] for i in all_items if i.get("score", 0) >= THRESHOLD_STAR and i.get("url")]
    if star_candidates:
        STAR_QUEUE.write_text("\n".join(star_candidates) + "\n", encoding="utf-8")
        print(f"     ⭐ {len(star_candidates)} item(s) met score ≥{THRESHOLD_STAR} opgeslagen in star-queue.")
    else:
        print("     Geen star-kandidaten.")

    # 5. Atom-feeds schrijven
    print("[5/5] Atom-feeds genereren...")

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
    print(f"   XML Web:       http://localhost:8765/filtered-webpage.xml\n")


if __name__ == "__main__":
    main()
