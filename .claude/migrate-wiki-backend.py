#!/usr/bin/env python3
"""
migrate-wiki-backend.py — schrijft wiki-backend.toml (+ .confidential) per vault.

Idempotent. Zonder vlag toont het alleen het plan; --apply schrijft; --verify
controleert een bestaande installatie (spec §5.1) en is bedoeld voor /check-backup.

Een vault is herkenbaar aan de aanwezigheid van raw/. --confidential geldt voor ALLE
paden in dezelfde aanroep, dus de migratie bestaat uit twee runs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wiki_backend  # noqa: E402

def plan_for(vault: Path, confidential: bool) -> dict:
    actions = []
    if not (vault / "raw").is_dir():
        return {"vault": str(vault), "error": "geen raw/ — dit lijkt geen vault"}
    if (vault / wiki_backend.CONFIG_NAME).exists():
        actions.append("config: reeds gemigreerd, ongemoeid gelaten")
    else:
        actions.append(f"config: {wiki_backend.CONFIG_NAME} aanmaken")
    marker = vault / wiki_backend.MARKER_NAME
    if confidential and not marker.exists():
        actions.append(f"marker: {wiki_backend.MARKER_NAME} aanmaken (600)")
    elif confidential:
        actions.append("marker: aanwezig, ongemoeid gelaten")
    return {"vault": str(vault), "confidential": confidential, "actions": actions}


def apply_to(vault: Path, confidential: bool) -> dict:
    """Schrijven zit in wiki_backend.write_config — één plek kent het formaat."""
    guard = plan_for(vault, confidential)
    if "error" in guard:
        return guard
    wiki_backend.write_config(vault, confidential)
    return plan_for(vault, confidential)


def verify(vault: Path) -> dict:
    """Controleert of config, marker en de verplichte sleutels nog kloppen."""
    res = wiki_backend.load(vault)
    if res["status"] != "ok":
        return {"vault": str(vault), "ok": False, "problem": res["error"]}
    cfg = res["cfg"]
    problems = []
    if res["confidential"]:
        if cfg["locality"] != "local":
            problems.append(f"locality={cfg['locality']} op vertrouwelijke vault")
        if cfg["invocation"] != "cli":
            problems.append(f"invocation={cfg['invocation']} op vertrouwelijke vault")
        state = Path(res["vault"]) / cfg["state_dir"]
        if state.is_dir() and (state.stat().st_mode & 0o777) != 0o700:
            problems.append(f"{cfg['state_dir']} staat niet op 700")
    return {"vault": str(vault), "ok": not problems, "problem": "; ".join(problems) or None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("vaults", nargs="+")
    ap.add_argument("--apply", action="store_true", help="daadwerkelijk schrijven")
    ap.add_argument("--verify", action="store_true", help="bestaande installatie controleren")
    ap.add_argument("--confidential", action="store_true",
                    help="geldt voor ALLE paden in deze aanroep")
    a = ap.parse_args()

    paths = [wiki_backend.normalize_vault(v) for v in a.vaults]
    if a.verify:
        results = [verify(p) for p in paths]
        print(json.dumps({"mode": "verify", "results": results}, indent=2, ensure_ascii=False))
        sys.exit(0 if all(r["ok"] for r in results) else 1)

    mode = "apply" if a.apply else "dry-run"
    fn = apply_to if a.apply else plan_for
    results = [fn(p, a.confidential) for p in paths]
    print(json.dumps({"mode": mode, "results": results}, indent=2, ensure_ascii=False))
    sys.exit(1 if any("error" in r for r in results) else 0)


if __name__ == "__main__":
    main()
