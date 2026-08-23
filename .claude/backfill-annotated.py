#!/usr/bin/env python3
"""
backfill-annotated.py — Stock-intake driver voor de geannoteerde back-catalog (Golf 0).

De feedreader-flow verwerkt nieuwe items één-voor-één via de Go-knop. Voor de *stock*
(back-catalog) is er geen driver: `build-zotero-bundle.py` neemt precies één `--item-key`
en kent geen batch of skip. Dit script vult die leemte voor **curated stock** — de eigen
Zotero-bibliotheek, die fase 2 (Filter) al gehad heeft (bewaren = impliciete Go):

  1. SELECTEREN  — leest de Zotero-DB read-only, neemt de items buiten `_inbox` met
                   gewicht > WEIGHT_DEFAULT (= items mét PDF-annotaties; de 277 uit de meting).
  2. IDEMPOTENT  — bestaat er al een `raw/*__{itemKey}.md`-bundle? → overslaan.
  3. SEQUENCEN   — anders `build-zotero-bundle.py --item-key KEY` als subproces (continue-on-error).

GEEN scoring / Go-No-go: curated stock is al gefilterd. Dit is puur selectie + sequencing —
de stock-tegenhanger van de per-item feedreader-Go.

Gebruik:
    PY=~/.local/share/uv/tools/zotero-mcp-server/bin/python3
    $PY .claude/backfill-annotated.py --dry-run            # alleen tellen, niets bouwen
    $PY .claude/backfill-annotated.py --limit 5            # bake-off: eerste 5 bundels
    $PY .claude/backfill-annotated.py                      # hele Golf 0 (277)

Vereist een bereikbare Zotero (default ZOTERO_ACCESS=local → Zotero desktop draait;
of ZOTERO_ACCESS=web met ZOTERO_API_KEY voor headless).

Output (stdout, JSON-only — geen broninhoud):
    {"status":"ok","selected":N,"skipped_existing":K,"built":M,"failed":F,"failed_keys":[...]}

Privacy: broninhoud verschijnt nooit op stdout; build-zotero-bundle.py geeft zelf alleen
JSON terug en print voortgang naar stderr. Dit script aggregeert alleen tellingen.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parent
VAULT_ROOT = CLAUDE_DIR.parent
RAW_DIR = VAULT_ROOT / "vault" / "raw"
BUILD_SCRIPT = CLAUDE_DIR / "build-zotero-bundle.py"

sys.path.insert(0, str(CLAUDE_DIR))
from zotero_utils import make_sqlite_copy, get_library_keys_with_weights  # noqa: E402
from feedreader_core import WEIGHT_DEFAULT  # noqa: E402

ZOTERO_SQLITE = Path.home() / "Zotero" / "zotero.sqlite"
INBOX_ID = 333


def annotated_keys() -> list[str]:
    """Item-keys uit de bibliotheek (buiten _inbox) mét PDF-annotaties, deterministisch gesorteerd."""
    tmp = make_sqlite_copy(ZOTERO_SQLITE)
    try:
        conn = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
        weights = get_library_keys_with_weights(conn, INBOX_ID)
        conn.close()
    finally:
        Path(tmp).unlink(missing_ok=True)
    # gewicht > WEIGHT_DEFAULT ⇒ item heeft annotaties (dan geldt WEIGHT_ANNOTATIONS)
    keys = [k for k, w in weights.items() if w > WEIGHT_DEFAULT]
    return sorted(keys)  # stabiele volgorde → reproduceerbare --limit-selectie


def bundle_exists(item_key: str) -> bool:
    """Bestaat er al een raw-bundle voor deze item-key? (naam = {citekey}__{itemKey}.md of {itemKey}.md)"""
    if not RAW_DIR.exists():
        return False
    return any(RAW_DIR.glob(f"*__{item_key}.md")) or (RAW_DIR / f"{item_key}.md").exists()


def build_one(item_key: str) -> tuple[bool, str]:
    """Roep build-zotero-bundle.py aan voor één key. Retourneert (ok, message)."""
    proc = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--item-key", item_key],
        capture_output=True, text=True,
    )
    # build-zotero-bundle.py geeft JSON op stdout ({"status":"ok"|"error", ...}).
    try:
        result = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return False, f"onparseerbare output (rc={proc.returncode})"
    return result.get("status") == "ok", result.get("message", "")


def main() -> None:
    ap = argparse.ArgumentParser(description="Stock-intake driver: geannoteerde back-catalog → raw/")
    ap.add_argument("--limit", type=int, default=None, help="bouw hooguit N bundels (bake-off/golf)")
    ap.add_argument("--dry-run", action="store_true", help="alleen tellen, niets bouwen")
    args = ap.parse_args()

    keys = annotated_keys()
    total_annotated = len(keys)
    if args.limit is not None:
        keys = keys[: args.limit]

    to_build = [k for k in keys if not bundle_exists(k)]
    skipped = len(keys) - len(to_build)

    if args.dry_run:
        print(json.dumps({
            "status": "ok", "dry_run": True,
            "total_annotated": total_annotated,
            "selected": len(keys), "skipped_existing": skipped,
            "would_build": len(to_build),
        }))
        return

    built, failed_keys = 0, []
    for i, key in enumerate(to_build, 1):
        print(f"[{i}/{len(to_build)}] bundle bouwen: {key}", file=sys.stderr)
        ok, msg = build_one(key)
        if ok:
            built += 1
        else:
            failed_keys.append(key)
            print(f"  ⚠️  mislukt ({key}): {msg}", file=sys.stderr)

    print(json.dumps({
        "status": "ok",
        "total_annotated": total_annotated,
        "selected": len(keys), "skipped_existing": skipped,
        "built": built, "failed": len(failed_keys), "failed_keys": failed_keys,
    }))


if __name__ == "__main__":
    main()
