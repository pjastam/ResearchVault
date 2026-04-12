#!/usr/bin/env python3
"""
ollama-generate.py — Roept de Ollama REST API aan en schrijft output naar bestand.

Vermijdt ANSI-codes en terminale spinner-output van de Ollama CLI.
Gebruikt /no_think om het denkproces van qwen3.5:9b te onderdrukken.

Gebruik:
    python3 .claude/ollama-generate.py \\
        --input  inbox/bron.txt \\
        --output literature/notitie.md \\
        --prompt "Schrijf een literatuurnotitie in het Nederlands..."
        [--model qwen3.5:9b]
        [--no-think]  (standaard aan)
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

OLLAMA_API    = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen3.5:9b"
TIMEOUT       = 600   # seconden — ruim genoeg voor lange transcripten
MAX_RETRIES   = 2     # pogingen bij verbindingsfouten


def generate(model: str, prompt: str, content: str, no_think: bool) -> str:
    full_prompt = f"/no_think\n{prompt}\n\n{content}" if no_think else f"{prompt}\n\n{content}"

    payload_dict: dict = {
        "model": model,
        "prompt": full_prompt,
        "stream": True,
    }
    if no_think:
        payload_dict["think"] = False
    payload = json.dumps(payload_dict).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_API,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    for attempt in range(1, MAX_RETRIES + 2):
        parts = []
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                for line in resp:
                    if not line.strip():
                        continue
                    chunk = json.loads(line.decode("utf-8"))
                    if "response" in chunk:
                        parts.append(chunk["response"])
                    if chunk.get("done"):
                        break
            return "".join(parts)
        except urllib.error.URLError as e:
            if attempt <= MAX_RETRIES:
                print(f"⚠️  Verbindingsfout (poging {attempt}/{MAX_RETRIES + 1}): {e} — herprobeert...", file=sys.stderr)
                time.sleep(5)
            else:
                print(f"❌  Ollama niet bereikbaar na {MAX_RETRIES + 1} pogingen: {e}", file=sys.stderr)
                sys.exit(1)
        except TimeoutError:
            print(f"❌  Timeout na {TIMEOUT}s — model reageert niet.", file=sys.stderr)
            sys.exit(1)

    return ""  # onbereikbaar, maar maakt de type-checker tevreden


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",    required=True, help="Invoerbestand met brontekst")
    parser.add_argument("--output",   required=True, help="Uitvoerbestand voor gegenereerde note")
    parser.add_argument("--prompt",   required=True, help="Instructieprompt voor het model")
    parser.add_argument("--model",    default=DEFAULT_MODEL)
    parser.add_argument("--no-think", dest="no_think", action="store_true", default=True)
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌  Invoerbestand niet gevonden: {input_path}", file=sys.stderr)
        sys.exit(1)

    content = input_path.read_text(encoding="utf-8")
    print(f"Input: {input_path} ({len(content):,} tekens)")
    print(f"Model: {args.model} | /no_think: {args.no_think}")
    print("Genereren...", flush=True)

    result = generate(args.model, args.prompt, content, args.no_think)

    if not result.strip():
        print(f"❌  Ollama gaf een lege respons — uitvoerbestand NIET aangemaakt.", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result, encoding="utf-8")

    print(f"✅  Geschreven: {output_path} ({len(result):,} tekens)")


if __name__ == "__main__":
    main()
