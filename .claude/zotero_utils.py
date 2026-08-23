#!/usr/bin/env python3
"""
zotero_utils.py — Gedeelde Zotero SQLite-hulpfuncties
=====================================================
Gedeeld door feedreader-score.py, feedreader-learn.py en index-score.py.
"""

import shutil
import sqlite3
import tempfile
from pathlib import Path

from feedreader_core import WEIGHT_DEFAULT, WEIGHT_ANNOTATIONS


def make_sqlite_copy(source: Path) -> Path:
    """
    Maakt een tijdelijke kopie van de Zotero SQLite database.
    Zotero vergrendelt het origineel tijdens gebruik; een kopie voorkomt conflicten.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    shutil.copy2(source, tmp.name)
    return Path(tmp.name)


def get_library_keys_with_weights(
    conn: sqlite3.Connection,
    inbox_id: int,
) -> dict[str, float]:
    """
    Haalt alle item_keys op die NIET in _inbox zitten, met gewichten:
      - WEIGHT_DEFAULT voor elk item
      - WEIGHT_ANNOTATIONS (niet: erbovenop) als het item PDF-annotaties heeft

    De twee constanten zijn een paar absolute gewichten, geen basis plus opslag.
    Tot 23 aug 2026 stond hier `+=`, wat een geannoteerd item op 4 zette terwijl
    `feedreader_core.py` zijn eigen constante becommentarieert als "3x weight vs.
    unannotated" en `CLAUDE.md` "gewicht 3 vs. 1" zegt. De tegenspraak zat al in de
    commit die de constante introduceerde (bcf6736, 24 mrt 2026); er is dus nooit
    een refactor geweest die de betekenis verschoof. Gemeten effect: geen — in
    ronde 1 van de embedding-bake-off was de ongewogen variant niet te
    onderscheiden van de gewogen.

    Retourneert een dict {item_key: gewicht}.
    """
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
            all_keys[row[0]] = float(WEIGHT_ANNOTATIONS)

    return all_keys
