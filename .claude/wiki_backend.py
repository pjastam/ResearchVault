#!/usr/bin/env python3
"""
wiki_backend.py — dispatcher naar de geconfigureerde wiki-backend.

ResearchVault levert canonieke bundles in raw/; wat daarna gebeurt is een vervangbare
backend (olw, claude-obsidian, none). Deze module leest wiki-backend.toml per vault,
controleert de guardrail en draait het subprocess.

Library-first: elke functie geeft een dict terug en roept NOOIT sys.exit(). Drie
aanroepers importeren deze module in-process, waaronder een launchd-daemon met een
`except Exception`-worker — SystemExit erft daar niet van en zou de thread doden.

Privacy: geen subprocess-inhoud in enige returnwaarde. Alleen returncode + logbestandsnaam.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

CONFIG_NAME = "wiki-backend.toml"
MARKER_NAME = ".confidential"
LOG_DIR_NAME = ".wiki-backend"

# Sleutels die op elke vault verplicht zijn, ongeacht backend.
REQUIRED_BACKEND_KEYS = ("locality", "invocation")
# Extra verplicht zodra de vault vertrouwelijk is (spec §4.1).
REQUIRED_CONFIDENTIAL_KEYS = ("state_dir", "force_args")

VERBS = ("ingest", "compile", "approve", "reject", "capture")


def _err(msg: str, **extra) -> dict:
    return {"status": "error", "error": msg, **extra}


def normalize_vault(vault) -> Path:
    """Eén padrepresentatie voor configlookup, markercheck en de {vault}-placeholder.
    Zonder deze regel kan de guardrail pad A controleren terwijl het subprocess op
    pad B draait (spec §4.2)."""
    return Path(vault).expanduser().resolve()


def load(vault) -> dict:
    """Leest en valideert wiki-backend.toml. Geen guardrail, geen subprocess."""
    vpath = normalize_vault(vault)
    cfg_path = vpath / CONFIG_NAME
    if not cfg_path.is_file():
        return _err(
            f"{CONFIG_NAME} ontbreekt in {vpath}. Repareer met: "
            f"python3 .claude/migrate-wiki-backend.py {vpath} --apply"
        )
    try:
        doc = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _err(f"{CONFIG_NAME} onleesbaar: {exc}")

    if "confidential" not in doc:
        return _err(f"'confidential' ontbreekt in {cfg_path} — verplicht, geen default")
    confidential = bool(doc["confidential"])

    marker = (vpath / MARKER_NAME).exists()
    if confidential != marker:
        return _err(
            f"config zegt confidential={confidential} maar {MARKER_NAME} is "
            f"{'aanwezig' if marker else 'afwezig'} in {vpath} — beide bronnen moeten "
            f"het eens zijn"
        )

    name = doc.get("backend")
    backends = doc.get("backends", {})
    if name not in backends:
        available = ", ".join(sorted(backends)) or "geen"
        return _err(f"onbekende backend '{name}'; beschikbaar: {available}")
    cfg = dict(backends[name])

    for key in REQUIRED_BACKEND_KEYS:
        if not cfg.get(key):
            return _err(f"'{key}' ontbreekt in [backends.{name}] — verplicht, geen default")

    has_verbs = any(cfg.get(v) for v in VERBS)
    if confidential and has_verbs:
        for key in REQUIRED_CONFIDENTIAL_KEYS:
            if not cfg.get(key):
                return _err(
                    f"'{key}' ontbreekt in [backends.{name}] terwijl deze vault "
                    f"vertrouwelijk is — verplicht (spec §4.1)"
                )

    return {
        "status": "ok",
        "vault": str(vpath),
        "confidential": confidential,
        "backend": name,
        "cfg": cfg,
    }
