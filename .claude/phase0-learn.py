#!/usr/bin/env python3
"""
phase0-learn.py — Leerloop voor drempelkalibratie
==================================================
Matcht recent aan Zotero toegevoegde items tegen het score-logboek,
markeert ze als added_to_zotero: true/false, en geeft een drempeladvies
zodra er voldoende gelabelde voorbeelden zijn.

Gebruik:
    python3 phase0-learn.py

Configuratie:
    LOG_FILE        — pad naar score_log.jsonl
    ZOTERO_SQLITE   — pad naar Zotero SQLite database
    INBOX_ID        — collectionID van _inbox in Zotero
    LABEL_AFTER_DAYS — na hoeveel dagen een niet-gematch item als 'false' wordt gelabeld
    MIN_POSITIVES   — minimum aantal positieven voor een drempeladvies
"""

import json
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Configuratie ──────────────────────────────────────────────────────────────

SCRIPT_DIR      = Path(__file__).parent
LOG_FILE        = SCRIPT_DIR / "score_log.jsonl"
ZOTERO_SQLITE   = Path.home() / "Zotero" / "zotero.sqlite"
INBOX_ID        = 333
LABEL_AFTER_DAYS = 3   # items ouder dan N dagen zonder match krijgen added_to_zotero: false
MIN_POSITIVES    = 30  # minimum positieven voor drempeladvies

# ── Hulpfuncties ──────────────────────────────────────────────────────────────

def make_sqlite_copy(source: Path) -> Path:
    tmp = tempfile.mktemp(suffix=".sqlite")
    shutil.copy2(source, tmp)
    return Path(tmp)


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


def load_log(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries = []
    for line in path.read_text().splitlines():
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return entries


def save_log(path: Path, entries: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── Hoofdprogramma ────────────────────────────────────────────────────────────

def main():
    print("\n🎓 phase0-learn — Drempelkalibratie")
    print("=" * 52)

    if not LOG_FILE.exists():
        print("⚠️  score_log.jsonl niet gevonden. Voer eerst phase0-score.py uit.")
        return

    # Zotero-URLs ophalen
    print("\n[1/3] Zotero-URLs ophalen...")
    tmp_db = make_sqlite_copy(ZOTERO_SQLITE)
    conn   = sqlite3.connect(tmp_db)
    try:
        zotero_urls = get_zotero_urls(conn)
    finally:
        conn.close()
        os.unlink(tmp_db)
    print(f"     {len(zotero_urls)} URL(s) gevonden in Zotero.")

    # Logboek laden en labelen
    print("[2/3] Logboek bijwerken...")
    entries  = load_log(LOG_FILE)
    now      = datetime.now(timezone.utc)
    cutoff   = now - timedelta(days=LABEL_AFTER_DAYS)

    newly_true  = 0
    newly_false = 0

    for entry in entries:
        if entry.get("added_to_zotero") is not None:
            continue  # al gelabeld

        url = entry.get("url", "")
        if url in zotero_urls:
            entry["added_to_zotero"] = True
            newly_true += 1
        else:
            # Labelen als false zodra de wachttijd verstreken is
            try:
                ts = datetime.fromisoformat(entry["timestamp"])
                if ts < cutoff:
                    entry["added_to_zotero"] = False
                    newly_false += 1
            except (KeyError, ValueError):
                pass

    save_log(LOG_FILE, entries)
    print(f"     ✅ toegevoegd aan Zotero: {newly_true} nieuw gelabeld")
    print(f"     ❌ niet toegevoegd (>{LABEL_AFTER_DAYS}d): {newly_false} nieuw gelabeld")

    # Drempeladvies
    print("[3/3] Drempeladvies berekenen...")
    positives = [e["score"] for e in entries if e.get("added_to_zotero") is True]
    negatives = [e["score"] for e in entries if e.get("added_to_zotero") is False]
    unlabeled = [e for e in entries if e.get("added_to_zotero") is None]

    print(f"\n{'=' * 52}")
    print(f"Gelabelde dataset:")
    print(f"  ✅ positieven (toegevoegd aan Zotero): {len(positives)}")
    print(f"  ❌ negatieven (niet toegevoegd):       {len(negatives)}")
    print(f"  ⏳ nog niet gelabeld:                  {len(unlabeled)}")

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
    print(f"  Activeer de filter in phase0-score.py via SCORE_THRESHOLD = {p10:.0f}\n")


if __name__ == "__main__":
    main()
