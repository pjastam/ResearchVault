#!/usr/bin/env python3
"""
backfill-scout.py — scoort de back-catalog (historie) van één bron tegen je Zotero-profiel.

De feedreader is een *flow*-instrument (`MAX_AGE_DAYS_DEFAULT = 30`; YouTube-RSS cap ~15) →
de back-catalog (stock) is onzichtbaar. Deze scout speurt per bron de historie af en scoort
elke item met dezelfde methode als de feedreader. Suggesties, geen beslissingen.

**Single-source:** elke run verwerkt precies één bron (geen batch). Rationale: houdt de
YouTube-transcript-fetches per run onder de ~30/IP-grens (met verse VPN per run → nooit
IpBlocked), geeft controle over IP-rotatie, en is uniform over de drie brontypes.

Bronnen (--source):
- youtube : yt-dlp enumereert de catalogus; TWEE-TRAPS — trap 1 titel-only (gratis),
            trap 2 transcript[:3000] voor de top-N (throttled, block-aware).
- podcast : feedparser leest de RSS; score = titel + show notes[:1000] (géén transcript;
            whisper blijft post-Go). Dunne show notes (<200 tekens) → ⚠️-bucket.
- scholar : feedparser + PURE-metadata; score = titel + abstract[:1000].

Privacy: bron-/transcripttekst wordt NOOIT geprint; rapport + stdout bevatten alleen metadata.
stdout = één JSON-object; voortgang naar stderr.

Gebruik:
    PY=~/.local/share/uv/tools/zotero-mcp-server/bin/python3
    $PY .claude/backfill-scout.py --source youtube --target "McElreath" --enrich-top-n 25
    $PY .claude/backfill-scout.py --source podcast --target "In Our Time"
    $PY .claude/backfill-scout.py --source scholar --target "van de Ven"
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT  = SCRIPT_DIR.parent
REPORT_DIR = REPO_ROOT / "vault" / ".cache"          # gitignored
STATE_FILE = SCRIPT_DIR / "backfill_state.json"

YT_LINE_PREFIX = "https://www.youtube.com/feeds/videos.xml?channel_id="
YTDLP_TIMEOUT  = 120
DEFAULT_MAX_ITEMS   = 200
DEFAULT_ENRICH_TOPN = 25
DEFAULT_THROTTLE    = 1.5
NOTRANSCRIPT_CAP    = 15

# Per-bron configuratie. dedupe=False bij scholar: de PURE-RSS toont maar ~50 recente pubs
# (geen diepere historie), en de waarde is een geconsolideerde per-auteur relevantie-ranking —
# niet "nieuwe" items. youtube/podcast deduppen wél tegen score_log (diepe catalogus beschikbaar).
SOURCES = {
    "youtube": {"limit": 3000, "two_stage": True,  "warn": True,  "dedupe": True,
                "content": "transcript", "warn_title": "Titel-only — niet verrijkt"},
    "podcast": {"limit": 1000, "two_stage": False, "warn": True,  "dedupe": True,
                "content": "show notes", "warn_title": "Dunne/geen show notes — titel-only"},
    "scholar": {"limit": 1000, "two_stage": False, "warn": False, "dedupe": False,
                "content": "abstract", "warn_title": ""},
}


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def die(msg: str, code: int = 1) -> None:
    print(json.dumps({"status": "error", "error": msg}, ensure_ascii=False))
    sys.exit(code)


# ── feedreader-score.py als module laden (hyphen → importlib) ──────────────────

def load_feedreader():
    sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(
        "feedreader_score", SCRIPT_DIR / "feedreader-score.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── feedreader-list.txt parsen + doelbron matchen ─────────────────────────────

def parse_feed_lines(feeds_file: Path) -> list[dict]:
    """Lijst van {url, comment}; comment = de ' # naam'-inline-annotatie."""
    out = []
    for raw in feeds_file.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if " #" in s:
            url, comment = s.split(" #", 1)
            out.append({"url": url.strip(), "comment": comment.strip()})
        else:
            out.append({"url": s.split()[0], "comment": ""})
    return out


def _pure_person_name(url: str) -> str:
    m = re.search(r"/persons/([^/]+)/", url)
    return unquote(m.group(1)).replace("-", " ").title() if m else ""


def _norm(s: str) -> str:
    """Lowercase + niet-alfanumeriek → spatie, zodat 'van de ven' matcht op 'van-de-ven'."""
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def match_target(source: str, target: str, lines: list[dict], fr) -> list[dict]:
    """Vind de bron die bij --target hoort (naam-substring of directe id/url)."""
    t = target.strip()
    tl = t.lower()
    nt = _norm(t)

    # Directe id/url — escape hatches
    if source == "youtube" and re.fullmatch(r"UC[\w-]{22}", t):
        return [{"channel_id": t, "name": t, "url": YT_LINE_PREFIX + t}]
    if t.startswith("http"):
        if source == "youtube":
            cid = ""
            if "channel_id=" in t:
                cid = t.split("channel_id=", 1)[1].split("&")[0]
            elif "/channel/" in t:
                cid = t.rstrip("/").split("/channel/", 1)[1].split("/")[0]
            return [{"channel_id": cid, "name": cid or t, "url": t}] if cid else []
        return [{"url": t, "name": t}]

    matches = []
    for L in lines:
        url, c = L["url"], L["comment"]
        if source == "youtube":
            if YT_LINE_PREFIX not in url:
                continue
            cid = url.split("channel_id=", 1)[1] if "channel_id=" in url else ""
            if tl == cid.lower() or (c and nt in _norm(c)):
                matches.append({"channel_id": cid, "name": c or cid, "url": url})
        elif source == "scholar":
            if not fr.is_pure_feed(url):
                continue
            if nt in _norm(url) or (c and nt in _norm(c)):
                matches.append({"url": url, "name": _pure_person_name(url) or c or url})
        elif source == "podcast":
            if YT_LINE_PREFIX in url or fr.is_pure_feed(url) or not c:
                continue
            if nt in _norm(c):
                matches.append({"url": url, "name": c})
    return matches


# ── Zotero-voorkeurprofiel (repliceert feedreader-score.py:612–635) ────────────

def build_profile(fr):
    if not fr.ZOTERO_SQLITE.exists():
        die(f"Zotero database niet gevonden: {fr.ZOTERO_SQLITE}")
    tmp_db = fr.make_sqlite_copy(fr.ZOTERO_SQLITE)
    conn = sqlite3.connect(tmp_db)
    try:
        lib_weights = fr.get_library_keys_with_weights(conn, fr.INBOX_ID)
    finally:
        conn.close()
        os.unlink(tmp_db)
    chroma_col = fr.chromadb.PersistentClient(path=str(fr.CHROMA_PATH)).get_collection("zotero_library")
    lib_embeddings = fr.get_embeddings_for_keys(chroma_col, list(lib_weights.keys()))
    if not lib_embeddings:
        die("Geen bibliotheek-embeddings gevonden. Voer eerst 'update-zotero' uit.")
    profile = fr.compute_weighted_profile(lib_embeddings, lib_weights)
    log(f"     Profiel gebaseerd op {len(lib_embeddings)} bibliotheekitems.")
    return profile


def _embed_and_score(fr, model, profile, items: list[dict], limit: int) -> None:
    """Scoort op titel + _text[:limit]. _text (bron-/transcripttekst) verlaat de functie niet."""
    import numpy as np
    if not items:
        return
    texts = [v["title"] + ((" " + v["_text"][:limit]) if v["_text"] else "") for v in items]
    embs = model.encode(texts, batch_size=32, show_progress_bar=False)
    for v, e in zip(items, embs):
        sim = fr.cosine_similarity(np.array(e, dtype=np.float32), profile)
        v["score"] = fr.bayesian_score(max(0, min(100, int(round(sim * 100)))))


# ── Datum-helper ───────────────────────────────────────────────────────────────

def _entry_date(e) -> str:
    if e.get("published_parsed"):
        try:
            return datetime(*e.published_parsed[:6], tzinfo=timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            pass
    return ""


# ── YouTube-adapter (twee-traps + block-aware) ─────────────────────────────────

def _iso_date(d: str) -> str:
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if d and d.isdigit() and len(d) == 8 else ""


def enum_youtube(channel_id: str, max_items: int) -> tuple[list[dict], bool]:
    url = f"https://www.youtube.com/channel/{channel_id}/videos"
    cmd = ["yt-dlp", "--flat-playlist", "--no-warnings", "--ignore-errors",
           "--playlist-end", str(max_items),
           "--print", "%(id)s\t%(title)s\t%(upload_date)s", url]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=YTDLP_TIMEOUT)
    except subprocess.TimeoutExpired:
        log(f"     ⚠️  yt-dlp timeout na {YTDLP_TIMEOUT}s (VPN? probeer een andere exit-node)")
        return [], False
    if proc.returncode != 0 and not proc.stdout.strip():
        log(f"     ⚠️  yt-dlp faalde: {proc.stderr.strip()[:200]}")
        return [], False
    items = []
    for raw in proc.stdout.splitlines():
        if not raw.strip():
            continue
        parts = raw.split("\t")
        if len(parts) < 2:
            continue
        vid = parts[0].strip()
        if len(vid) != 11:
            continue
        upload = parts[-1].strip() if len(parts) >= 3 else ""
        title = ("\t".join(parts[1:-1]) if len(parts) >= 3 else parts[1]).strip()
        items.append({"video_id": vid, "title": title or "(geen titel)",
                      "date": _iso_date(upload),
                      "url": f"https://www.youtube.com/watch?v={vid}"})
    return items, len(items) >= max_items


def _read_tr_cache(fr, vid: str) -> tuple[bool, str | None]:
    f = fr.TRANSCRIPT_CACHE_DIR / f"{vid}.json"
    if f.exists():
        try:
            return True, json.loads(f.read_text(encoding="utf-8")).get("text")
        except Exception:
            return True, None
    return False, None


def _fetch_tr(fr, item: dict, channel: str, throttle: float, block_flag: dict) -> str | None:
    """Netwerk-fetch (trap 2). Bij IpBlocked: zet flag, breek af, cache NIET."""
    vid = item["video_id"]
    time.sleep(throttle)
    text = None
    try:
        snips = fr.YouTubeTranscriptApi().fetch(vid, languages=["nl", "en", "de", "fr"])
        text = " ".join(s.text for s in snips)
    except Exception as e:
        # Gedeeld met feedreader-score.py: beide schrijven naar dezelfde
        # transcript-cache, dus ze moeten dezelfde blokkade-detectie gebruiken.
        if fr.is_block(e):
            block_flag["blocked"] = True
            log("       ⛔ IpBlocked — trap 2 afgebroken (wissel VPN-exit en draai opnieuw)")
            return None
    (fr.TRANSCRIPT_CACHE_DIR / f"{vid}.json").write_text(json.dumps({
        "video_id": vid, "title": item["title"], "channel": channel, "url": item["url"],
        "published": item["date"], "text": text,
        "fetched_at": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False),
        encoding="utf-8")
    return text


def score_youtube(fr, model, profile, videos, channel_name, existing, enrich_top_n,
                  throttle, block_flag):
    items, skipped = [], 0
    for v in videos:
        # Canonieke URL, niet de ruwe: load_existing_log() geeft sinds 16 aug 2026
        # identiteiten terug. yt-dlp levert geen RSS-guid, dus dit is de enige
        # sleutelvorm die hier te berekenen valt — de set bevat hem ook.
        if fr.canonical_url(v["url"]) in existing:
            skipped += 1
            continue
        cached, text = _read_tr_cache(fr, v["video_id"])
        v.update({"_text": text or "", "has_content": bool(text),
                  "cached_null": cached and not text})
        items.append(v)
    _embed_and_score(fr, model, profile, items, 3000)          # trap 1
    items.sort(key=lambda x: x["score"], reverse=True)

    fetched = 0
    if enrich_top_n > 0 and not block_flag["blocked"]:
        cands = [v for v in items if not v["has_content"] and not v["cached_null"]][:enrich_top_n]
        for v in cands:
            if block_flag["blocked"]:
                break
            text = _fetch_tr(fr, v, channel_name, throttle, block_flag)
            if text:
                v["_text"], v["has_content"] = text, True
                fetched += 1
        if fetched:
            _embed_and_score(fr, model, profile, [v for v in items if v["has_content"]], 3000)
            items.sort(key=lambda x: x["score"], reverse=True)
    return items, skipped, fetched


# ── Podcast- en Scholar-adapters (single-pass) ─────────────────────────────────

def enum_podcast(fr, feed_url, max_items):
    parsed = fr.feedparser.parse(feed_url, request_headers={"User-Agent": "Mozilla/5.0"})
    items = []
    for e in parsed.entries[:max_items]:
        desc = ""
        if e.get("content"):
            desc = fr.strip_html(e["content"][0].get("value", ""))
        elif e.get("summary"):
            desc = fr.strip_html(e.get("summary", ""))
        items.append({"title": fr.strip_html(e.get("title", "(geen titel)")),
                      "url": e.get("link", ""), "date": _entry_date(e),
                      "_text": desc, "has_content": len(desc) >= fr.SHOWNOTES_MIN_LENGTH})
    return items, len(items) >= max_items


def enum_scholar(fr, feed_url, max_items, throttle):
    parsed = fr.feedparser.parse(feed_url, request_headers={"User-Agent": "Mozilla/5.0"})
    items = []
    for e in parsed.entries[:max_items]:
        url = e.get("link", "")
        meta = fr.fetch_pure_metadata(url) if url and fr.is_pure_feed(feed_url) else {}
        abstract = meta.get("abstract", "") if not meta.get("error") else ""
        if url:
            time.sleep(throttle)
        items.append({"title": fr.strip_html(e.get("title", "(geen titel)")),
                      "url": url, "date": meta.get("date_published", "") or _entry_date(e),
                      "_text": abstract, "has_content": bool(abstract)})
    return items, len(items) >= max_items


def score_simple(fr, model, profile, items, existing, limit, dedupe=True):
    # Canonieke URL: zie de toelichting in score_youtube().
    keep = ([v for v in items if fr.canonical_url(v["url"]) not in existing]
            if dedupe else list(items))
    skipped = len(items) - len(keep)
    _embed_and_score(fr, model, profile, keep, limit)
    keep.sort(key=lambda x: x["score"], reverse=True)
    return keep, skipped


# ── Rapport ────────────────────────────────────────────────────────────────────

def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "bron"


def _table(rows, score_header="Score") -> str:
    out = [f"| {score_header} | Titel | Datum | Link |", "|------:|-------|-------|------|"]
    for v in rows:
        out.append(f"| {v['score']} | {v['title'].replace('|', chr(92) + '|')} | "
                   f"{v['date'] or '—'} | {v['url']} |")
    return "\n".join(out)


def write_report(source, target_name, enumerated, items, skipped, truncated, max_items,
                 enrich_top_n, fetched, blocked, gen_date, th_green, th_yellow) -> Path:
    cfg = SOURCES[source]
    content = cfg["content"]
    verified = items if not cfg["warn"] else [v for v in items if v["has_content"]]
    warn     = [] if not cfg["warn"] else [v for v in items if not v["has_content"]]
    green  = [v for v in verified if v["score"] >= th_green]
    yellow = [v for v in verified if th_yellow <= v["score"] < th_green]
    red    = [v for v in verified if v["score"] < th_yellow]

    head = (f"Geënumereerd: **{enumerated}** · nieuw: **{len(items)}** · overgeslagen "
            f"(al gezien): **{skipped}**")
    if source == "youtube":
        head += f" · met transcript: **{len(verified)}** ({fetched} nieuw opgehaald)"

    lines = [f"# Back-catalog scout — {source} — {target_name} — {gen_date}", "", head, ""]
    if source == "youtube":
        lines += [f"> **Twee-traps:** alle video's titel-gescoord; transcript opgehaald voor de "
                  f"top-{enrich_top_n}. 🟢/🟡/🔴 = transcript-geverifieerd (titel + transcript[:3000], "
                  f"feedreader-pariteit). ⚠️ = titel-only. Labels: 🟢 ≥{th_green} · 🟡 "
                  f"{th_yellow}–{th_green-1} · 🔴 <{th_yellow}. Suggesties — zet interessante items "
                  f"handmatig in Zotero."]
    else:
        lines += [f"> Score = titel + {content}[:{cfg['limit']}] (feedreader-pariteit). Labels: "
                  f"🟢 ≥{th_green} · 🟡 {th_yellow}–{th_green-1} · 🔴 <{th_yellow}. "
                  f"Suggesties — zet interessante items handmatig in Zotero."]
        if source == "scholar":
            lines += ["> _De PURE-feed toont ~50 recente publicaties (geen diepere historie); "
                      "dit is een **geconsolideerde per-auteur ranking** t.o.v. je profiel — "
                      "geen dedupe tegen je flow._"]
    if blocked:
        lines += ["", "> ⛔ **IpBlocked tijdens trap 2** — deels verrijkt. Wissel VPN-exit en draai "
                      "opnieuw met `--force`."]
    if truncated:
        lines += ["", f"> ⚠️  Afgekapt op de {max_items} nieuwste items (`--max-items` verhogen)."]

    lines += ["", f"## 🟢 Aanrader (score ≥{th_green}) — {len(green)}",
              _table(green) if green else "_(geen)_"]
    lines += ["", f"## 🟡 Wellicht ({th_yellow}–{th_green-1}) — {len(yellow)}",
              _table(yellow) if yellow else "_(geen)_"]
    lines += ["", f"## 🔴 Waarschijnlijk niet — {len(red)}",
              f"_{len(red)} {content}-geverifieerde items onder de drempel — niet uitgeklapt._"]

    if warn:
        shown = warn[:NOTRANSCRIPT_CAP]
        lines += ["", f"## ⚠️ {cfg['warn_title']} ({len(warn)})",
                  f"_Top {len(shown)} op titel-score; {content} ontbreekt of te dun._",
                  f"_⚠️ De **titel-score** staat op een **andere schaal** dan 🟢/🟡/🔴 en skewt vaak "
                  f"te hoog — niet 1-op-1 vergelijken._",
                  _table(shown, "Titel-score")]
        if len(warn) > len(shown):
            lines += [f"\n_… en {len(warn) - len(shown)} meer titel-only items._"]

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"backfill-{source}-{_slug(target_name)}-{gen_date}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ── State ───────────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            log("⚠️  state-bestand corrupt — begin opnieuw")
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Back-catalog scout (single-source)")
    ap.add_argument("--source", required=True, choices=list(SOURCES),
                    help="brontype")
    ap.add_argument("--target", required=True,
                    help="naam-substring (tegen feedreader-list.txt) of directe id/url")
    ap.add_argument("--max-items", type=int, default=DEFAULT_MAX_ITEMS,
                    help=f"max items, nieuwste eerst (default {DEFAULT_MAX_ITEMS})")
    ap.add_argument("--enrich-top-n", type=int, default=DEFAULT_ENRICH_TOPN,
                    help=f"YouTube trap 2: transcript voor top-N (default {DEFAULT_ENRICH_TOPN}; "
                         f"0 = titel-only). Genegeerd voor podcast/scholar.")
    ap.add_argument("--throttle", type=float, default=DEFAULT_THROTTLE,
                    help=f"seconden tussen netwerk-fetches (default {DEFAULT_THROTTLE})")
    ap.add_argument("--force", action="store_true", help="draaien ook al in de state")
    args = ap.parse_args()

    log(f"📡 backfill-scout — {args.source}: {args.target}")
    fr = load_feedreader()

    lines = parse_feed_lines(fr.FEEDS_FILE)
    matches = match_target(args.source, args.target, lines, fr)
    if not matches:
        die(f"Geen {args.source}-bron gevonden voor '{args.target}' in feedreader-list.txt.")
    if len(matches) > 1:
        names = " | ".join(m["name"] for m in matches[:8])
        die(f"Meerdere matches voor '{args.target}' — wees specifieker: {names}")
    src = matches[0]
    name = src["name"]

    log("[1/3] Voorkeursprofiel laden uit ChromaDB...")
    profile = build_profile(fr)
    # Derde plaats waar het model stond hardgecodeerd (ADR-0007 noemde er twee).
    # Erft nu dezelfde bron als het profiel hierboven: config.json.
    model = fr.maak_embedder()
    existing = fr.load_existing_log(fr.LOG_FILE)
    gen_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    block_flag = {"blocked": False}

    log(f"[2/3] '{name}' enumereren en scoren...")
    fetched = 0
    if args.source == "youtube":
        videos, truncated = enum_youtube(src["channel_id"], args.max_items)
        if not videos:
            die("Geen video's opgehaald (yt-dlp faalde/timeout — probeer een andere VPN-exit).")
        log(f"       {len(videos)} video's; trap 1 (titel) + trap 2 (top-{args.enrich_top_n})...")
        items, skipped, fetched = score_youtube(
            fr, model, profile, videos, name, existing, args.enrich_top_n,
            args.throttle, block_flag)
    else:
        if args.source == "podcast":
            raw, truncated = enum_podcast(fr, src["url"], args.max_items)
        else:
            raw, truncated = enum_scholar(fr, src["url"], args.max_items, args.throttle)
        if not raw:
            die("Geen items opgehaald uit de feed.")
        log(f"       {len(raw)} items; scoren op titel + {SOURCES[args.source]['content']}...")
        items, skipped = score_simple(fr, model, profile, raw, existing,
                                      SOURCES[args.source]["limit"],
                                      dedupe=SOURCES[args.source]["dedupe"])

    enumerated = len(items) + skipped
    report = write_report(args.source, name, enumerated, items, skipped, truncated,
                          args.max_items, args.enrich_top_n, fetched, block_flag["blocked"],
                          gen_date, fr.THRESHOLD_GREEN, fr.THRESHOLD_YELLOW)
    verified = sum(1 for v in items if (args.source == "scholar") or v["has_content"])
    green = sum(1 for v in items if ((args.source == "scholar") or v["has_content"])
                and v["score"] >= fr.THRESHOLD_GREEN)
    log(f"       ✅ {green} 🟢 · {verified} geverifieerd · rapport: {report}")

    log("[3/3] State bijwerken...")
    state = load_state()
    state[f"{args.source}:{name}"] = {
        "source": args.source, "name": name,
        "backfilled_at": datetime.now(timezone.utc).isoformat(),
        "enumerated": enumerated, "scored": len(items),
        "verified": verified, "fetched": fetched, "blocked": block_flag["blocked"]}
    save_state(state)

    print(json.dumps({"status": "ok", "source": args.source, "target": name,
                      "blocked": block_flag["blocked"], "enumerated": enumerated,
                      "scored": len(items), "verified": verified, "fetched": fetched,
                      "green": green, "report": str(report)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
