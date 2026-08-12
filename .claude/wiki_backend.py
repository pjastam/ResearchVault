#!/usr/bin/env python3
"""
wiki_backend.py — dispatcher naar de geconfigureerde wiki-backend.

ResearchVault levert canonieke bundles in raw/; wat daarna gebeurt is een vervangbare
backend (olw, claude-obsidian, none). Deze module leest wiki-backend.toml per vault,
controleert de guardrail en draait het subprocess.

Library-first: elke functie geeft een dict terug en roept NOOIT sys.exit(). Zeven
aanroepers importeren deze module in-process (promote-to-raw.py, declassify-to-personal.py,
feedreader-server.py, compartment-serve.py, sync-personal-context.py, new-compartment.py
en migrate-wiki-backend.py), waaronder een launchd-daemon met een `except Exception`-worker
— SystemExit erft daar niet van en zou de thread doden.

Privacy: geen subprocess-inhoud in enige returnwaarde. Alleen returncode + logbestandsnaam.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tomllib
from datetime import datetime
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


def run(verb: str, vault, **args) -> dict:
    """render() plus subprocess, logging en timeout."""
    plan = render(verb, vault, **args)
    if plan["status"] != "ok":
        return plan

    log_path = Path(plan["log"])
    try:
        log_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(log_path.parent, 0o700)
    except OSError as exc:
        return _err(f"kon logmap niet aanmaken: {exc}")

    try:
        # Append, geen truncate. Het logpad hangt aan het verb, niet aan de aanroeper,
        # dus drie ingest-aanroepers (promote-to-raw.py, declassify-to-personal.py,
        # feedreader-server.py) delen ingest.log. Met "w" kapte de tweede run het log
        # van de eerste af en wees "zie ingest.log" naar andermans uitvoer. Een naam
        # per aanroeper zou het contract verbreden voor een diagnostisch probleem —
        # de dispatcher kent zijn aanroeper niet. De scheidingsregel hieronder is
        # dispatcher-eigen tekst (verb + tijdstempel), geen subprocess-uitvoer, en
        # houdt opeenvolgende runs uit elkaar. Flush vóór subprocess.run, anders
        # belandt de header ná de uitvoer die het kind naar dezelfde fd schrijft.
        with open(log_path, "a", encoding="utf-8") as lf:
            os.chmod(log_path, 0o600)
            stamp = datetime.now().astimezone().isoformat(timespec="seconds")
            lf.write(f"\n===== {verb} · {stamp} =====\n")
            lf.flush()
            proc = subprocess.run(
                plan["command"], stdout=lf, stderr=lf,
                timeout=plan["timeout"], cwd=plan_cwd(vault),
            )
    except subprocess.TimeoutExpired:
        return _err(f"{verb} timeout na {plan['timeout']}s, zie {log_path.name}",
                    returncode=None, log=str(log_path))
    except OSError as exc:
        # returncode is hier altijd aanwezig, ook al bestaat er geen exit-code: het
        # proces is nooit gestart. None is eerlijker dan de sleutel weglaten — een
        # aanroeper die res["returncode"] direct indexeert (geen .get()) mag hier niet
        # op een KeyError stuiten, juist op het pad waar de foutmelding het hardst nodig is.
        return _err(f"{verb} kon niet starten: {exc}", returncode=None, log=str(log_path))

    if proc.returncode != 0:
        # Log-inhoud NOOIT teruggeven — alleen de code en de bestandsnaam.
        return _err(f"{verb} faalde (exit {proc.returncode}), zie {log_path.name}",
                    returncode=proc.returncode, log=str(log_path))
    return {"status": "ok", "returncode": 0, "log": str(log_path)}


def plan_cwd(vault) -> str:
    return str(normalize_vault(vault))


CONFIG_TEMPLATE = """\
# Wiki-backend contract voor deze vault. ResearchVault levert raw/; wat daarna
# gebeurt is een vervangbare backend. Zie ResearchVault/docs → "Wiki backends".

confidential = {confidential}
backend      = "olw"

[backends.olw]
invocation = "cli"
locality   = "local"
bin        = "~/.local/bin/olw"
config     = "wiki.toml"          # backend-eigen config; niet van ResearchVault
state_dir  = ".olw"
drafts_dir = "wiki/.drafts"
model      = "mistral-small:22b"
timeout    = 1800
timeout_approve = 120
timeout_reject  = 120
{force_line}ingest  = "{{bin}} ingest {{file}} --vault {{vault}} --fast-model {{model}}"
compile = "{{bin}} compile --vault {{vault}}"
approve = "{{bin}} approve {{draft}} --vault {{vault}}"
reject  = "{{bin}} reject {{draft}} --vault {{vault}}[ --feedback {{feedback}}]"
"""

FORCE_LINE = ('force_args = "--provider ollama '
              '--provider-url http://localhost:11434"\n')


def write_config(vault, confidential: bool) -> dict:
    """Schrijft wiki-backend.toml en (bij confidential) de marker. Idempotent:
    bestaande bestanden blijven ongemoeid. Gedeeld door migrate-wiki-backend.py
    en new-compartment.py, zodat één plek het configformaat kent."""
    vpath = normalize_vault(vault)
    created = []
    cfg = vpath / CONFIG_NAME
    if not cfg.exists():
        cfg.write_text(CONFIG_TEMPLATE.format(
            confidential="true" if confidential else "false",
            force_line=FORCE_LINE if confidential else "",
        ), encoding="utf-8")
        os.chmod(cfg, 0o600 if confidential else 0o644)
        created.append(str(cfg))
    marker = vpath / MARKER_NAME
    if confidential and not marker.exists():
        marker.write_text("", encoding="utf-8")
        os.chmod(marker, 0o600)
        created.append(str(marker))
    return {"status": "ok", "vault": str(vpath), "created": created}


def main() -> None:
    """Dun CLI-omhulsel: vertaalt status naar exit-code. De enige plek met sys.exit()."""
    ap = argparse.ArgumentParser(description="Dispatch naar de geconfigureerde wiki-backend.")
    ap.add_argument("verb", choices=VERBS + ("load",))
    ap.add_argument("vault")
    ap.add_argument("--file")
    ap.add_argument("--draft")
    ap.add_argument("--feedback")
    ap.add_argument("--render-only", action="store_true")
    a = ap.parse_args()

    if a.verb == "load":
        res = load(a.vault)
    else:
        kwargs = {k: v for k, v in
                  (("file", a.file), ("draft", a.draft), ("feedback", a.feedback))
                  if v is not None}
        res = (render if a.render_only else run)(a.verb, a.vault, **kwargs)

    print(json.dumps(res, ensure_ascii=False))
    sys.exit(0 if res["status"] in ("ok", "skipped") else 1)


if __name__ == "__main__":
    main()
