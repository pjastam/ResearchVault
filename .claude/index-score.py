#!/usr/bin/env python3
"""
index-score.py — Relevantiescore voor Zotero _inbox items
=========================================================
Vergelijkt elk item in de _inbox collectie met je bestaande Zotero-bibliotheek
en geeft een score (0–100) die aangeeft hoe goed het item past bij je voorkeuren.

Gebruik:
    python3 index-score.py
    python3 index-score.py --json                     # machineleesbaar naar stdout
    python3 index-score.py --snapshot <pad>.json      # voor de batch; zie hieronder

Vereisten:
    - Zotero draait NIET (script maakt een veilige kopie van de SQLite database)
    - chromadb geïnstalleerd: pip install chromadb --break-system-packages
    - numpy geïnstalleerd:    pip install numpy --break-system-packages

Configuratie (pas aan indien nodig):
    ZOTERO_SQLITE   — pad naar Zotero SQLite database
    CHROMA_PATH     — pad naar ChromaDB directory
    VAULT_LIT_PATH  — pad naar literature/ map in Obsidian vault
    INBOX_ID        — collectionID van _inbox in Zotero (standaard 333)
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import chromadb
import numpy as np

from feedreader_core import cosine_similarity, compute_weighted_profile
from zotero_utils import make_sqlite_copy, get_library_keys_with_weights

# ── Configuratie ──────────────────────────────────────────────────────────────

ZOTERO_SQLITE  = Path.home() / "Zotero" / "zotero.sqlite"
CHROMA_PATH    = Path.home() / ".config" / "zotero-mcp" / "chroma_db"
INBOX_ID       = 333   # collectionID van _inbox — zie: SELECT collectionID, collectionName FROM collections

# Score-drempels voor labels
THRESHOLD_GREEN  = 70   # 🟢 Sterk match
THRESHOLD_YELLOW = 40   # 🟡 Mogelijk relevant  (onder 40 = 🔴 Zwak match)

# ── Hulpfuncties ──────────────────────────────────────────────────────────────

def get_inbox_keys(conn: sqlite3.Connection, inbox_id: int) -> list[str]:
    """Haalt item_keys op uit de _inbox collectie, exclusief bijlagen en notes."""
    cur = conn.execute("""
        SELECT i.key
        FROM collectionItems ci
        JOIN items i ON i.itemID = ci.itemID
        JOIN itemTypes it ON it.itemTypeID = i.itemTypeID
        WHERE ci.collectionID = ?
        AND it.typeName NOT IN ('note', 'attachment')
    """, (inbox_id,))
    return [row[0] for row in cur.fetchall()]


def get_embeddings_for_keys(
    collection: chromadb.Collection,
    keys: list[str],
) -> dict[str, np.ndarray]:
    """
    Haalt embeddings op uit ChromaDB voor de gegeven item_keys.
    Retourneert alleen keys waarvoor een embedding beschikbaar is.
    """
    if not keys:
        return {}

    # ChromaDB gebruikt item_key als ID (geverifieerd via db-status output)
    result = collection.get(ids=keys, include=["embeddings"])
    found = {}
    for item_id, embedding in zip(result["ids"], result["embeddings"]):
        found[item_id] = np.array(embedding, dtype=np.float32)
    return found


def score_label(score: int) -> str:
    if score >= THRESHOLD_GREEN:
        return "🟢"
    elif score >= THRESHOLD_YELLOW:
        return "🟡"
    else:
        return "🔴"


def get_item_titles(conn: sqlite3.Connection, keys: list[str]) -> dict[str, str]:
    """Haalt titels op voor de gegeven item_keys."""
    if not keys:
        return {}
    placeholders = ",".join("?" * len(keys))
    cur = conn.execute(f"""
        SELECT i.key, idv.value
        FROM items i
        JOIN itemData id_ ON id_.itemID = i.itemID
        JOIN itemDataValues idv ON idv.valueID = id_.valueID
        JOIN fields f ON f.fieldID = id_.fieldID
        WHERE f.fieldName = 'title'
        AND i.key IN ({placeholders})
    """, keys)
    return {row[0]: row[1] for row in cur.fetchall()}


def get_item_creators(conn: sqlite3.Connection, keys: list[str]) -> dict[str, str]:
    """Haalt eerste auteur op voor de gegeven item_keys."""
    if not keys:
        return {}
    placeholders = ",".join("?" * len(keys))
    cur = conn.execute(f"""
        SELECT i.key, c.lastName
        FROM items i
        JOIN itemCreators ic ON ic.itemID = i.itemID
        JOIN creators c ON c.creatorID = ic.creatorID
        WHERE ic.orderIndex = 0
        AND i.key IN ({placeholders})
    """, keys)
    return {row[0]: row[1] for row in cur.fetchall()}


def get_item_years(conn: sqlite3.Connection, keys: list[str]) -> dict[str, str]:
    """Haalt publicatiejaar op voor de gegeven item_keys."""
    if not keys:
        return {}
    placeholders = ",".join("?" * len(keys))
    cur = conn.execute(f"""
        SELECT i.key, SUBSTR(idv.value, 1, 4)
        FROM items i
        JOIN itemData id_ ON id_.itemID = i.itemID
        JOIN itemDataValues idv ON idv.valueID = id_.valueID
        JOIN fields f ON f.fieldID = id_.fieldID
        WHERE f.fieldName IN ('date', 'year')
        AND i.key IN ({placeholders})
    """, keys)
    return {row[0]: row[1] for row in cur.fetchall()}


# ── Snapshot voor feedreader-server.py ────────────────────────────────────────

def schrijf_snapshot(pad: Path, items: list) -> None:
    """Leg de scores vast in `pad`, atomair en wereld-leesbaar.

    Bestaat omdat `feedreader-server.py` sinds 26 sep 2026 als `_feedreader` draait en
    ChromaDB de collectie read-write opent: dat account kan dit script dus niet zelf
    draaien (`attempt to write a readonly database`). De inbox-pagina las die mislukking
    stil als "geen scores". De batch draait als root en heeft dat probleem niet, dus de
    scoring gebeurt daar en de server leest alleen nog het resultaat.

    Atomair via `.tmp` + `replace()`, want de server kan elk moment lezen; een half
    geschreven bestand komt daar aan als corrupte JSON. `0o644` omdat de batch als root
    schrijft en `_feedreader` moet kunnen lezen.
    """
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "items": items,
    }
    tmp = pad.with_name(pad.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.chmod(0o644)
    tmp.replace(pad)


def _faal(bericht: str, *, hint: str = "", json_uit: bool = False, snapshot: str | None = None):
    """Meld een storing en beëindig het programma.

    In snapshot-modus wordt er **niets** geschreven: een bestaande, goede snapshot
    overschrijven met een lege lijst zou een storing laten lezen als "de _inbox is leeg".
    De exitcode maakt hem zichtbaar voor de batch.
    """
    if snapshot:
        print(bericht, file=sys.stderr)
        sys.exit(1)
    if json_uit:
        print(json.dumps({"error": bericht}))
    else:
        print(f"❌  {bericht}")
        if hint:
            print(f"    {hint}")
    sys.exit(1)


# ── Hoofdprogramma ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Zotero _inbox relevantiescore")
    parser.add_argument("--json", action="store_true", help="Output als JSON (onderdrukt progress)")
    parser.add_argument("--snapshot", metavar="PAD",
                        help="Schrijf de scores atomair naar PAD i.p.v. naar stdout "
                             "(voor de batch; feedreader-server.py leest dit bestand)")
    args = parser.parse_args()

    # --snapshot impliceert machineleesbaar: de voortgangsregels horen niet in een batchlog
    # en de vertakkingen hieronder hangen alle aan args.json.
    if args.snapshot:
        args.json = True

    if not args.json:
        print("\n📚 index-score — Zotero _inbox relevantiescore")
        print("=" * 52)

    # 1. Veilige SQLite-kopie maken
    if not args.json:
        print("\n[1/5] SQLite database kopiëren...")
    if not ZOTERO_SQLITE.exists():
        _faal(f"Zotero database niet gevonden: {ZOTERO_SQLITE}",
              json_uit=args.json, snapshot=args.snapshot)
    tmp_db = make_sqlite_copy(ZOTERO_SQLITE)
    conn = sqlite3.connect(tmp_db)

    try:
        # 2. _inbox keys ophalen
        if not args.json:
            print("[2/5] _inbox items ophalen...")
        inbox_keys = get_inbox_keys(conn, INBOX_ID)
        if not inbox_keys:
            if args.snapshot:
                # Een lege _inbox is een geldige uitkomst, geen storing — dus wél
                # wegschrijven. Zou je dat overslaan, dan blijft de server een oude
                # lijst tonen van items die allang verwerkt zijn.
                schrijf_snapshot(Path(args.snapshot), [])
            elif args.json:
                print(json.dumps([]))
            else:
                print(f"✅  _inbox (ID {INBOX_ID}) is leeg — niets te scoren.")
            return
        if not args.json:
            print(f"     {len(inbox_keys)} items gevonden in _inbox.")

        # 3. Bibliotheek-keys + gewichten ophalen
        if not args.json:
            print("[3/5] Voorkeursprofiel berekenen (bibliotheek buiten _inbox)...")
        lib_weights = get_library_keys_with_weights(conn, INBOX_ID)
        if not args.json:
            print(f"     {len(lib_weights)} bibliotheekitems als voorkeursprofiel.")

        # 4. Embeddings ophalen uit ChromaDB
        if not args.json:
            print("[4/5] Embeddings ophalen uit ChromaDB...")
        chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        chroma_col = chroma_client.get_collection("zotero_library")

        inbox_embeddings = get_embeddings_for_keys(chroma_col, inbox_keys)
        lib_embeddings   = get_embeddings_for_keys(chroma_col, list(lib_weights.keys()))

        if not lib_embeddings:
            _faal("Geen bibliotheek-embeddings in ChromaDB",
                  hint="Voer eerst 'zotero-mcp update-db --fulltext' uit.",
                  json_uit=args.json, snapshot=args.snapshot)

        if not args.json:
            missing = len(inbox_keys) - len(inbox_embeddings)
            if missing > 0:
                print(f"     ⚠️  {missing} inbox-items hebben geen embedding (nog niet geïndexeerd).")

        # 5. Profiel berekenen + scoren
        if not args.json:
            print("[5/5] Scores berekenen...")
        profile = compute_weighted_profile(lib_embeddings, lib_weights)

        # Metadata ophalen voor weergave
        titles   = get_item_titles(conn, inbox_keys)
        creators = get_item_creators(conn, inbox_keys)
        years    = get_item_years(conn, inbox_keys)

        # Scores berekenen
        scored = []
        for key in inbox_keys:
            if key not in inbox_embeddings:
                continue
            sim = cosine_similarity(inbox_embeddings[key], profile)
            score = int(round(sim * 100))
            score = max(0, min(100, score))
            scored.append((score, key))

        scored.sort(reverse=True)

        # ── JSON output ───────────────────────────────────────────────────────
        if args.json:
            result = [
                {
                    "key":    key,
                    "score":  score,
                    "label":  score_label(score),
                    "title":  titles.get(key, ""),
                    "author": creators.get(key, ""),
                    "year":   years.get(key, ""),
                }
                for score, key in scored
            ]
            # Items zonder embedding krijgen score=None
            scored_keys = {key for _, key in scored}
            for key in inbox_keys:
                if key not in scored_keys:
                    result.append({
                        "key": key, "score": None, "label": None,
                        "title": titles.get(key, ""), "author": creators.get(key, ""),
                        "year": years.get(key, ""),
                    })
            if args.snapshot:
                schrijf_snapshot(Path(args.snapshot), result)
            else:
                print(json.dumps(result, ensure_ascii=False))
            return

        # ── Leesbare output ───────────────────────────────────────────────────
        print(f"\n{'=' * 52}")
        print(f"_inbox — {len(scored)} items · gesorteerd op relevantiescore")
        print(f"{'=' * 52}\n")

        for score, key in scored:
            label   = score_label(score)
            title   = titles.get(key, "(geen titel)")
            creator = creators.get(key, "")
            year    = years.get(key, "")

            max_title = 55
            if len(title) > max_title:
                title = title[:max_title - 1] + "…"

            byline = " · ".join(filter(None, [creator, year]))
            if byline:
                print(f"{label}  {score:3d}  {title}")
                print(f"          {byline}")
                print()
            else:
                print(f"{label}  {score:3d}  {title}\n")

        green  = sum(1 for s, _ in scored if s >= THRESHOLD_GREEN)
        yellow = sum(1 for s, _ in scored if THRESHOLD_YELLOW <= s < THRESHOLD_GREEN)
        red    = sum(1 for s, _ in scored if s < THRESHOLD_YELLOW)
        print(f"{'─' * 52}")
        print(f"🟢 {green} sterke matches  "
              f"🟡 {yellow} mogelijk relevant  "
              f"🔴 {red} zwak\n")

    finally:
        conn.close()
        try:
            os.unlink(tmp_db)
        except Exception:
            pass


if __name__ == "__main__":
    main()