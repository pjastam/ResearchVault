#!/usr/bin/env python3
"""
ollama-generate.py — Roept een lokale LLM REST API aan en schrijft output naar bestand.

Ondersteunt twee backends:
- ollama (standaard): Ollama REST API op localhost:11434
- mlx: mlx_lm server (OpenAI-compatible) op localhost:8080
  Start met: python3 -m mlx_lm server --model mlx-community/Qwen3-8B-4bit

Gebruik:
    python3 .claude/ollama-generate.py \\
        --input  inbox/bron.txt \\
        --output literature/notitie.md \\
        --prompt "Schrijf een literatuurnotitie in het Nederlands..."
        [--model qwen3.5:9b]
        [--no-think]  (standaard aan)
        [--backend ollama|mlx]
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

_env = Path(__file__).resolve().parent.parent / ".env"
if _env.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env, override=False)
    except ImportError:
        pass

OLLAMA_API        = "http://localhost:11434/api/generate"
MLX_API           = "http://localhost:8080/v1/completions"
DEFAULT_MODEL     = "qwen3.5:9b"
DEFAULT_MLX_MODEL = "mlx-community/Qwen3-8B-4bit"
TIMEOUT           = 600   # seconden — ruim genoeg voor lange transcripten
MAX_RETRIES       = 2     # pogingen bij verbindingsfouten


def generate_ollama(model: str, prompt: str, content: str, no_think: bool) -> str:
    full_prompt = f"/no_think\n{prompt}\n\n{content}" if no_think else f"{prompt}\n\n{content}"

    payload_dict: dict = {
        "model": model,
        "prompt": full_prompt,
        "stream": True,
        "options": {"num_ctx": 32768},
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


def generate_mlx(model: str, prompt: str, content: str, no_think: bool) -> str:
    # /no_think is een Qwen3-instructietoken; mlx_lm.server kent geen aparte think=False optie.
    # Qwen3-modellen van mlx-community respecteren het token — gedrag is modelspecifiek.
    full_prompt = f"/no_think\n{prompt}\n\n{content}" if no_think else f"{prompt}\n\n{content}"

    payload = json.dumps({
        "model": model,
        "prompt": full_prompt,
        "max_tokens": 4096,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        MLX_API,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = json.loads(resp.read())
                choice = data["choices"][0]
                if choice.get("finish_reason") == "length":
                    print(f"⚠️  MLX output afgekapt (max_tokens=4096 bereikt) — notitie mogelijk onvolledig.",
                          file=sys.stderr)
                text = choice["text"]
                # Strip denkfragment: Qwen3 laat </think> door ondanks /no_think prefix.
                if "</think>" in text:
                    text = text.split("</think>", 1)[1].lstrip("\n")
                return text
        except urllib.error.URLError as e:
            if isinstance(e.reason, TimeoutError):
                print(f"❌  Timeout na {TIMEOUT}s — MLX model reageert niet.", file=sys.stderr)
                sys.exit(1)
            if attempt <= MAX_RETRIES:
                print(f"⚠️  Verbindingsfout (poging {attempt}/{MAX_RETRIES + 1}): {e} — herprobeert...",
                      file=sys.stderr)
                time.sleep(5)
            else:
                print(f"❌  MLX server niet bereikbaar na {MAX_RETRIES + 1} pogingen: {e}", file=sys.stderr)
                print("   Start de server met: python3 -m mlx_lm server --model mlx-community/Qwen3-8B-4bit",
                      file=sys.stderr)
                sys.exit(1)
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            print(f"❌  Onverwacht MLX-responsformaat: {e}", file=sys.stderr)
            sys.exit(1)
    return ""  # onbereikbaar, maar maakt de type-checker tevreden


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",    required=True, help="Invoerbestand met brontekst")
    parser.add_argument("--output",   required=True, help="Uitvoerbestand voor gegenereerde note")
    parser.add_argument("--prompt",   required=True, help="Instructieprompt voor het model")
    parser.add_argument("--model",    default=DEFAULT_MODEL)
    parser.add_argument("--no-think", dest="no_think", action="store_true", default=True)
    parser.add_argument("--backend",  default=os.environ.get("LLM_BACKEND", "ollama"),
                        choices=["ollama", "mlx"],
                        help="LLM-backend: ollama of mlx. Standaard via LLM_BACKEND env var of 'ollama'.")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌  Invoerbestand niet gevonden: {input_path}", file=sys.stderr)
        sys.exit(1)

    content = input_path.read_text(encoding="utf-8")

    if args.backend == "mlx":
        effective_model = DEFAULT_MLX_MODEL if args.model == DEFAULT_MODEL else args.model
        print(f"Input: {input_path} ({len(content):,} tekens)")
        print(f"Model: {effective_model} | backend: mlx | /no_think: {args.no_think}")
        print("Genereren...", flush=True)
        result = generate_mlx(effective_model, args.prompt, content, args.no_think)
    else:
        print(f"Input: {input_path} ({len(content):,} tekens)")
        print(f"Model: {args.model} | backend: ollama | /no_think: {args.no_think}")
        print("Genereren...", flush=True)
        result = generate_ollama(args.model, args.prompt, content, args.no_think)

    if not result.strip():
        print(f"❌  {args.backend.upper()} gaf een lege respons — uitvoerbestand NIET aangemaakt.",
              file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result, encoding="utf-8")

    print(f"✅  Geschreven: {output_path} ({len(result):,} tekens)")


if __name__ == "__main__":
    main()
