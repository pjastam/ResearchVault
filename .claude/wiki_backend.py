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

import re
import shlex
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


_OPTIONAL_RE = re.compile(r"\[([^\[\]]*)\]")
_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def _resolve_timeout(cfg: dict, verb: str):
    """Per-verb override wint van de fallback. Ontbreken beide → None (fout)."""
    value = cfg.get(f"timeout_{verb}", cfg.get("timeout"))
    return int(value) if value is not None else None


def _strip_optional_segments(template: str, values: dict) -> str:
    """Een segment tussen blokhaken vervalt volledig wanneer een placeholder erbinnen
    geen (niet-lege) waarde heeft. Nodig omdat compartment-serve.py --feedback alleen
    meestuurt als de gebruiker een reden invulde (spec §4.1)."""
    def repl(m: re.Match) -> str:
        segment = m.group(1)
        for key in _PLACEHOLDER_RE.findall(segment):
            if not values.get(key):
                return ""
        return segment
    return _OPTIONAL_RE.sub(repl, template)


def check_guardrail(loaded: dict) -> dict:
    """Weigert hard op een vertrouwelijke vault. Geen fallback (spec §4.2).

    Locality wordt niet geverifieerd maar afgedwongen: olw ondersteunt zelf
    --provider groq|openai|azure en leest drie configlagen, dus `locality = "local"`
    is een verklaring, geen feit. force_args (in render() toegevoegd) zet de provider
    via de CLI zodat geen configlaag hem nog kan overrulen.
    """
    if not loaded["confidential"]:
        return {"status": "ok"}
    cfg, name, vpath = loaded["cfg"], loaded["backend"], loaded["vault"]

    if cfg["locality"] != "local":
        return _err(
            f"backend '{name}' heeft locality='{cfg['locality']}' en mag niet draaien op "
            f"de vertrouwelijke vault {vpath}"
        )
    if cfg["invocation"] != "cli":
        return _err(
            f"backend '{name}' heeft invocation='{cfg['invocation']}' en mag niet draaien "
            f"op de vertrouwelijke vault {vpath} — de guardrail kan een sessie-stap niet zien"
        )
    return {"status": "ok"}


def render(verb: str, vault, **args) -> dict:
    """Leest config en bepaalt capability (verbcheck, template). Controleert daarna de
    guardrail (spec §4.2) — een vertrouwelijke vault mag alleen naar een lokale cli-backend.
    Resolved timeout per verb. Vult placeholders in template in, voegt op een vertrouwelijke
    vault force_args toe en rendert naar argv-lijst. Voert niets uit."""
    loaded = load(vault)
    if loaded["status"] != "ok":
        return loaded
    cfg, vpath = loaded["cfg"], loaded["vault"]

    if verb not in cfg:
        return {"status": "skipped",
                "reason": f"backend '{loaded['backend']}' heeft geen {verb}"}
    template = cfg[verb]
    if not template:
        return {"status": "unsupported",
                "reason": f"backend '{loaded['backend']}' ondersteunt {verb} niet",
                "hint": cfg.get("session_hint", "")}

    guard = check_guardrail(loaded)
    if guard["status"] != "ok":
        return guard

    timeout = _resolve_timeout(cfg, verb)
    if timeout is None:
        return _err(f"geen timeout voor verb '{verb}' — zet timeout of timeout_{verb}")

    values = {
        "vault": vpath,
        "bin": str(Path(cfg["bin"]).expanduser()) if cfg.get("bin") else "",
        "root": str(Path(cfg["root"]).expanduser()) if cfg.get("root") else "",
        "model": cfg.get("model", ""),
    }
    for key in ("file", "draft", "feedback"):
        if args.get(key) is not None:
            values[key] = str(args[key])

    stripped = _strip_optional_segments(template, values)
    command: list[str] = []
    for token in shlex.split(stripped):
        names = _PLACEHOLDER_RE.findall(token)
        if not names:
            command.append(token)
            continue
        for name in names:
            if not values.get(name):
                return _err(f"placeholder '{{{name}}}' heeft geen waarde voor verb '{verb}'")
        command.append(_PLACEHOLDER_RE.sub(lambda m: values[m.group(1)], token))

    if loaded["confidential"] and cfg.get("force_args"):
        command += shlex.split(cfg["force_args"])

    log_path = Path(vpath) / LOG_DIR_NAME / f"{verb}.log"
    return {"status": "ok", "command": command, "timeout": timeout, "log": str(log_path)}
