#!/usr/bin/env python3
"""
inbox-score.py — Relevantiescore voor Zotero _inbox items
=========================================================
Vergelijkt elk item in de _inbox collectie met je bestaande Zotero-bibliotheek
en geeft een score (0–100) die aangeeft hoe goed het item past bij je voorkeuren.

Gebruik:
    python3 inbox-score.py

Vereisten:
    - Zotero draait NIET (script maakt een veilige kopie van de SQLite database)
    - chromadb geïnstalleerd: pip install chromadb --break-system-packages
    - numpy geïnstalleerd:    pip install numpy --break-system-packages

Configuratie (pas aan indien nodig):
    ZOTERO_SQLITE   — pad naar Zotero SQLite database
    CHROMA_PATH     — pad naar ChromaDB directory
    VAULT_LIT_PATH  — pad naar llm-notes/ map in Obsidian vault
    INBOX_ID        — collectionID van _inbox in Zotero (standaard 333)
"""

import os
import sqlite3
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


# ── Hoofdprogramma ────────────────────────────────────────────────────────────

def main():
    print("\n📚 inbox-score — Zotero _inbox relevantiescore")
    print("=" * 52)

    # 1. Veilige SQLite-kopie maken
    print("\n[1/5] SQLite database kopiëren...")
    if not ZOTERO_SQLITE.exists():
        print(f"❌  Zotero database niet gevonden: {ZOTERO_SQLITE}")
        print("    Pas ZOTERO_SQLITE aan bovenin het script.")
        return
    tmp_db = make_sqlite_copy(ZOTERO_SQLITE)
    conn = sqlite3.connect(tmp_db)

    try:
        # 2. _inbox keys ophalen
        print("[2/5] _inbox items ophalen...")
        inbox_keys = get_inbox_keys(conn, INBOX_ID)
        if not inbox_keys:
            print(f"✅  _inbox (ID {INBOX_ID}) is leeg — niets te scoren.")
            return
        print(f"     {len(inbox_keys)} items gevonden in _inbox.")

        # 3. Bibliotheek-keys + gewichten ophalen
        print("[3/5] Voorkeursprofiel berekenen (bibliotheek buiten _inbox)...")
        lib_weights = get_library_keys_with_weights(conn, INBOX_ID)
        print(f"     {len(lib_weights)} bibliotheekitems als voorkeursprofiel.")

        # 4. Embeddings ophalen uit ChromaDB
        print("[4/5] Embeddings ophalen uit ChromaDB...")
        chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        chroma_col = chroma_client.get_collection("zotero_library")

        inbox_embeddings = get_embeddings_for_keys(chroma_col, inbox_keys)
        lib_embeddings   = get_embeddings_for_keys(chroma_col, list(lib_weights.keys()))

        if not lib_embeddings:
            print("❌  Geen bibliotheek-embeddings gevonden in ChromaDB.")
            print("    Voer eerst 'zotero-mcp update-db --fulltext' uit.")
            return

        missing = len(inbox_keys) - len(inbox_embeddings)
        if missing > 0:
            print(f"     ⚠️  {missing} inbox-items hebben geen embedding (nog niet geïndexeerd).")

        # 5. Profiel berekenen + scoren
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
            # Schaal cosine-similariteit (typisch 0.0–1.0) naar 0–100
            score = int(round(sim * 100))
            score = max(0, min(100, score))
            scored.append((score, key))

        scored.sort(reverse=True)

        # ── Output ────────────────────────────────────────────────────────────
        print(f"\n{'=' * 52}")
        print(f"_inbox — {len(scored)} items · gesorteerd op relevantiescore")
        print(f"{'=' * 52}\n")

        for score, key in scored:
            label   = score_label(score)
            title   = titles.get(key, "(geen titel)")
            creator = creators.get(key, "")
            year    = years.get(key, "")

            # Titel inkorten voor leesbaarheid
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

        # Samenvatting
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