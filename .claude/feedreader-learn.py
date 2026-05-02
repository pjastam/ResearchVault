#!/usr/bin/env python3
"""
feedreader-learn.py — Leerloop voor drempelkalibratie
======================================================
Matcht recent aan Zotero toegevoegde items tegen het score-logboek,
markeert ze als added_to_zotero: true/false, en geeft een drempeladvies
zodra er voldoende gelabelde voorbeelden zijn.

Gebruik:
    python3 feedreader-learn.py

Configuratie:
    LOG_FILE        — pad naar score_log.jsonl
    ZOTERO_SQLITE   — pad naar Zotero SQLite database
    INBOX_ID        — collectionID van _inbox in Zotero
    LABEL_AFTER_DAYS — na hoeveel dagen een niet-gematch item als 'false' wordt gelabeld
    MIN_POSITIVES   — minimum aantal positieven voor een drempeladvies
"""

import fcntl
import json
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from freshrss_utils import (
    load_freshrss_creds,
    freshrss_auth,
    freshrss_star_by_urls,
    freshrss_starred_urls,
    freshrss_read_urls,
)
from zotero_utils import make_sqlite_copy

# ── Configuratie ──────────────────────────────────────────────────────────────

SCRIPT_DIR      = Path(__file__).parent
LOG_FILE        = SCRIPT_DIR / "score_log.jsonl"
SKIP_QUEUE      = SCRIPT_DIR / "skip_queue.jsonl"
STAR_QUEUE      = Path("/tmp/feedreader-star-queue.txt")
ZOTERO_SQLITE   = Path.home() / "Zotero" / "zotero.sqlite"
INBOX_ID        = 333
LABEL_AFTER_DAYS     = 3  # items ouder dan N dagen zonder match krijgen added_to_zotero: false
NNW_READ_LABEL_AFTER_DAYS = 1  # gelezen in NNW maar niet in Zotero → na 1 dag negatief labelen
MIN_POSITIVES    = 30  # minimum positieven voor drempeladvies

# ── Hulpfuncties ──────────────────────────────────────────────────────────────

def get_zotero_urls(conn: sqlite3.Connection) -> set[str]:
    """Haalt alle bekende URLs op uit Zotero (bijlagen)."""
    cur = conn.execute("""
        SELECT DISTINCT ia.path
        FROM itemAttachments ia
        WHERE ia.path LIKE 'http%'
          AND ia.itemID NOT IN (SELECT itemID FROM deletedItems)
    """)
    urls = set()
    for (path,) in cur.fetchall():
        if path:
            urls.add(path.strip())
    return urls


def normalize_title(title: str) -> str:
    """Normaliseert een titel voor vergelijking: lowercase + genormaliseerde whitespace."""
    return " ".join(title.lower().split())


MIN_TITLE_LENGTH = 15  # kortere titels worden niet gebruikt voor titelmatching


def get_zotero_titles(conn: sqlite3.Connection) -> set[str]:
    """Haalt genormaliseerde titels op van alle Zotero-items (geen bijlagen)."""
    cur = conn.execute("""
        SELECT DISTINCT idv.value
        FROM itemData id
        JOIN fields f ON f.fieldID = id.fieldID
        JOIN itemDataValues idv ON idv.valueID = id.valueID
        JOIN items i ON i.itemID = id.itemID
        WHERE f.fieldName = 'title'
          AND i.itemTypeID NOT IN (SELECT itemTypeID FROM itemTypes WHERE typeName = 'attachment')
          AND id.itemID NOT IN (SELECT itemID FROM deletedItems)
    """)
    titles = set()
    for (title,) in cur.fetchall():
        if title and len(title) >= MIN_TITLE_LENGTH:
            titles.add(normalize_title(title))
    return titles


def load_log(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries = []
    with path.open("r", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            for line in f:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    return entries


def save_log(path: Path, entries: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def process_skip_queue(entries: list[dict]) -> int:
    """
    Verwerkt skip_queue.jsonl: zoekt elk URL op in entries en zet skipped=True.
    Leegt de queue atomair (lezen + truncate binnen één exclusieve lock) zodat
    geen skip-signalen verloren gaan als feedreader-server.py gelijktijdig schrijft.
    """
    if not SKIP_QUEUE.exists():
        return 0
    queue = []
    with SKIP_QUEUE.open("r+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            for line in f:
                try:
                    queue.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
            f.seek(0)
            f.truncate()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    if not queue:
        return 0
    skip_urls = {e["url"] for e in queue if "url" in e}
    count = 0
    for entry in entries:
        if entry.get("url") in skip_urls and not entry.get("skipped"):
            entry["skipped"] = True
            count += 1
    return count


# ── Hoofdprogramma ────────────────────────────────────────────────────────────

def main():
    print("\n🎓 feedreader-learn — Drempelkalibratie")
    print("=" * 52)

    if not LOG_FILE.exists():
        print("⚠️  score_log.jsonl niet gevonden. Voer eerst feedreader-score.py uit.")
        return

    # Log-rotatie: archiveer als het bestand groter is dan 10 MB
    log_size = LOG_FILE.stat().st_size
    if log_size > 10 * 1024 * 1024:
        archive = LOG_FILE.with_name(f"score_log.{date.today():%Y-%m-%d}.jsonl")
        LOG_FILE.rename(archive)
        print(f"[rotatie] score_log.jsonl gearchiveerd als {archive.name} ({log_size // 1024} KB)")
        LOG_FILE.touch()

    # Logboek laden + skip-queue verwerken
    entries = load_log(LOG_FILE)
    print(f"\n[1/4] Skip-queue verwerken...")
    newly_skipped = process_skip_queue(entries)
    if newly_skipped:
        save_log(LOG_FILE, entries)
        print(f"     👎 {newly_skipped} item(s) als 'skipped' gemarkeerd.")
    else:
        print(f"     Geen nieuwe skip-signalen.")

    # Zotero-URLs en -titels + FreshRSS-signalen ophalen
    print("[2/4] Zotero-URLs en -titels + FreshRSS-signalen ophalen...")
    tmp_db = make_sqlite_copy(ZOTERO_SQLITE)
    conn   = sqlite3.connect(tmp_db)
    try:
        zotero_urls   = get_zotero_urls(conn)
        zotero_titles = get_zotero_titles(conn)
    finally:
        conn.close()
        os.unlink(tmp_db)
    print(f"     {len(zotero_urls)} URL(s) gevonden in Zotero.")
    print(f"     {len(zotero_titles)} titel(s) gevonden in Zotero.")

    # FreshRSS GReader-signalen: gestefd (positief) en gelezen (negatief)
    fr_starred: set[str] = set()
    fr_read:    set[str] = set()
    fr_creds = load_freshrss_creds()
    if all(fr_creds.values()):
        fr_auth, fr_post = freshrss_auth(fr_creds)
        if fr_auth:
            if STAR_QUEUE.exists():
                queue_urls = [u for u in STAR_QUEUE.read_text(encoding="utf-8").splitlines() if u]
                if queue_urls:
                    starred = freshrss_star_by_urls(fr_creds["url"], fr_auth, fr_post, queue_urls)
                    print(f"     ⭐ {starred}/{len(queue_urls)} item(s) gestefd via star-queue.")
                STAR_QUEUE.unlink()
            fr_starred = freshrss_starred_urls(fr_creds["url"], fr_auth)
            fr_read    = freshrss_read_urls(fr_creds["url"], fr_auth)
            print(f"     ⭐ {len(fr_starred)} gestefd, 📖 {len(fr_read)} gelezen in FreshRSS.")
        else:
            print("     ⚠️  FreshRSS GReader auth mislukt; FreshRSS-signalen overgeslagen.")
    else:
        print("     ℹ️  FRESHRSS_API_WACHTWOORD niet ingesteld; FreshRSS-signalen overgeslagen.")

    # Logboek labelen
    print("[3/4] Logboek bijwerken...")
    now          = datetime.now(timezone.utc)
    cutoff       = now - timedelta(days=LABEL_AFTER_DAYS)
    nnw_cutoff   = now - timedelta(days=NNW_READ_LABEL_AFTER_DAYS)

    newly_true_url     = 0
    newly_true_title   = 0
    newly_true_starred = 0
    newly_false        = 0
    newly_false_nnw    = 0

    for entry in entries:
        if entry.get("added_to_zotero") is not None:
            continue  # al gelabeld

        url = entry.get("url", "")

        # Positief signaal 1: gestefd in FreshRSS/NNW
        if url in fr_starred:
            entry["added_to_zotero"] = True
            entry["starred_in_freshrss"] = True
            newly_true_starred += 1
            continue

        # Positief signaal 2: toegevoegd aan Zotero (URL-match)
        if url in zotero_urls:
            entry["added_to_zotero"] = True
            newly_true_url += 1
            continue

        # Positief signaal 3: titelmatching
        raw_title = entry.get("title", "")
        if len(raw_title) >= MIN_TITLE_LENGTH and normalize_title(raw_title) in zotero_titles:
            entry["added_to_zotero"] = True
            newly_true_title += 1
            continue

        try:
            ts = datetime.fromisoformat(entry["timestamp"])
        except (KeyError, ValueError):
            continue

        # Negatief signaal 1 (sterk, change D): gelezen in NNW maar niet in Zotero
        if url in fr_read and ts < nnw_cutoff:
            entry["added_to_zotero"] = False
            entry["read_in_nnw"] = True
            newly_false_nnw += 1
            continue

        # Negatief signaal 2 (sterkste, change F): timeout — genegeerd zonder enige actie
        if ts < cutoff:
            entry["added_to_zotero"] = False
            newly_false += 1

    save_log(LOG_FILE, entries)
    print(f"     ⭐ via FreshRSS-ster: {newly_true_starred} nieuw gelabeld")
    print(f"     ✅ via URL:           {newly_true_url} nieuw gelabeld")
    print(f"     ✅ via titel:         {newly_true_title} nieuw gelabeld")
    print(f"     📖 NNW gelezen/geen Zotero (>{NNW_READ_LABEL_AFTER_DAYS}d): {newly_false_nnw} nieuw gelabeld")
    print(f"     ❌ genegeerd, timeout (>{LABEL_AFTER_DAYS}d): {newly_false} nieuw gelabeld")

    # Drempeladvies
    print("[4/4] Drempeladvies berekenen...")
    positives        = [e["score"] for e in entries if e.get("added_to_zotero") is True]
    skipped          = [e["score"] for e in entries if e.get("skipped") is True]
    negatives_nnw    = [e["score"] for e in entries
                        if e.get("added_to_zotero") is False and e.get("read_in_nnw")]
    negatives_timeout = [e["score"] for e in entries
                         if e.get("added_to_zotero") is False and not e.get("read_in_nnw")]
    negatives        = negatives_timeout + negatives_nnw
    unlabeled        = [e for e in entries if e.get("added_to_zotero") is None]

    print(f"\n{'=' * 52}")
    print(f"Gelabelde dataset:")
    print(f"  ✅ positieven (Zotero of NNW-ster):              {len(positives)}")
    print(f"  ❌ sterkste negatief (timeout, genegeerd):       {len(negatives_timeout)}")
    print(f"  📖 sterk negatief (NNW gelezen, niet Zotero):   {len(negatives_nnw)}")
    print(f"  👎 expliciet afgewezen (skip-knop):              {len(skipped)}")
    print(f"  ⏳ nog niet gelabeld:                            {len(unlabeled)}")

    if len(positives) < MIN_POSITIVES:
        print(f"\n⏳ Nog niet genoeg data voor een betrouwbaar drempeladvies.")
        print(f"   Nog {MIN_POSITIVES - len(positives)} positieven nodig (minimaal {MIN_POSITIVES}).")
        print(f"   Blijf de feed gebruiken en voer dit script dagelijks uit.\n")
        return

    import statistics
    pos_sorted = sorted(positives)
    p10 = pos_sorted[max(0, len(pos_sorted) // 10)]
    p25 = pos_sorted[max(0, len(pos_sorted) // 4)]
    p50 = statistics.median(pos_sorted)

    neg_sorted = sorted(negatives, reverse=True) if negatives else []
    neg_p75    = neg_sorted[max(0, len(neg_sorted) // 4)] if negatives else "n.v.t."

    print(f"\nScoreverdelingen:")
    print(f"  Positieven — mediaan: {p50:.0f}  P25: {p25:.0f}  P10 (conservatief): {p10:.0f}")
    if negatives:
        print(f"  Negatieven — P75 (top 25%): {neg_p75:.0f}")

    print(f"\n📊 Drempeladvies:")
    print(f"  Conservatief (weinig false negatives): drempel = {p10:.0f}")
    print(f"  Gebalanceerd:                          drempel = {p25:.0f}")
    print(f"  Strikt (minder items, hogere precisie): drempel = {p50:.0f}")
    print(f"\n  Aanbeveling: begin met {p10:.0f} en verhoog geleidelijk.")
    print(f"  Activeer de filter in feedreader-score.py via SCORE_THRESHOLD = {p10:.0f}\n")


def cleanup_transcript_cache(max_age_days: int = 90) -> None:
    """Verwijder transcript- en artikel-cache-bestanden ouder dan max_age_days dagen."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    removed = 0
    for cache_dir in [SCRIPT_DIR / "transcript_cache", SCRIPT_DIR / "article_cache"]:
        if not cache_dir.exists():
            continue
        for cache_file in cache_dir.glob("*"):
            if not cache_file.is_file():
                continue
            try:
                if cache_file.suffix == ".json":
                    data = json.loads(cache_file.read_text(encoding="utf-8"))
                    ts_str = data.get("fetched_at") or data.get("cached_at")
                    if ts_str:
                        ts = datetime.fromisoformat(ts_str)
                        # Zorg dat de timestamp timezone-aware is voor de vergelijking;
                        # fromisoformat() geeft een naive datetime als de string geen
                        # tijdzone bevat, wat een TypeError geeft bij vergelijking met
                        # de timezone-aware cutoff.
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                        if ts < cutoff:
                            cache_file.unlink()
                            removed += 1
                        continue
                # Fallback voor HTML en andere bestanden: gebruik bestandsmodificatietijd
                mtime = datetime.fromtimestamp(cache_file.stat().st_mtime, tz=timezone.utc)
                if mtime < cutoff:
                    cache_file.unlink()
                    removed += 1
            except Exception as e:
                print(f"⚠️  cache-bestand overgeslagen: {cache_file.name}: {e}", file=sys.stderr)
    if removed:
        print(f"[cache] {removed} cache-bestand(en) verwijderd (ouder dan {max_age_days} dagen)")


if __name__ == "__main__":
    main()
    cleanup_transcript_cache()
