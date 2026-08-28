#!/usr/bin/env python3
"""
whisper_local.py — lokale audiotranscriptie via whisper.cpp.

Losgemaakt uit attach-transcript.py (28 aug 2026) zodat ook gereedschap buiten deze
repo de transcriptie kan aanroepen zonder de Zotero-laag mee te slepen. De aanleiding
was een los `transcribe`-commando voor eigen opnames; de code zelf is ongewijzigd
overgenomen, inclusief de docstrings die vastleggen waarom de foutafhandeling is zoals
ze is.

Deze module hangt bewust aan niets anders dan de stdlib. Dat is de reden van haar
bestaan: attach-transcript.py trekt bij het laden `zotero_api` en `feedreader_identity`
mee, en wie alleen wil transcriberen heeft die niet.

Privacygrens: de transcripttekst gaat naar STDOUT en naar het .txt-bestand; STDERR
draagt uitsluitend motordiagnostiek. Daarom mag stderr wél in een log — stdout nooit.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

WHISPER_MODEL        = "large-v3-turbo"
WHISPER_MODELS_DIR   = Path("/opt/homebrew/share/whisper.cpp/models")


# whisper-cli: rekenwerk vs. afbouw ─────────────────────────────────────────────
# De transcripttekst gaat naar STDOUT; STDERR draagt uitsluitend motordiagnostiek
# (backend-laden, Metal-init, voortgang, timings). Daarom mag stderr wél in de log —
# stdout nooit. Wie dit ooit omdraait, doorbreekt de privacygrens.
#
# Beide markeringen hieronder verschijnen pas ná de laatste segmentdecodering: eerst
# het wegschrijven van de .txt, dan het timingsblok. Staan ze allebei in stderr, dan
# heeft whisper zijn werk aantoonbaar afgemaakt.
WHISPER_EINDMARKERS = ("output_txt: saving output to", "whisper_print_timings:")


def _whisper_liep_af(stderr: str) -> bool:
    """True als whisper-cli aantoonbaar tot het einde is gekomen."""
    return all(m in stderr for m in WHISPER_EINDMARKERS)


def _knip(tekst: str, kop: int = 800, staart: int = 800) -> str:
    """Kort een lange uitvoer in met behoud van kop én staart.

    Aanleiding (22 aug 2026): een crash van whisper-cli werd gelogd als
    `stderr.strip()[-500:]`. Bij een stackdump houdt een staart-only afkapping juist
    de minst informatieve helft over — het log begon bij frame 6, de eigenlijke
    foutregel was weg. De oorzaak van die crash is daardoor nooit vastgesteld.
    """
    tekst = (tekst or "").strip()
    if len(tekst) <= kop + staart:
        return tekst
    weg = len(tekst) - kop - staart
    return f"{tekst[:kop]}\n  […{weg} tekens overgeslagen…]\n{tekst[-staart:]}"


FFMPEG = Path("/opt/homebrew/bin/ffmpeg")


def _naar_wav(audio_path: Path) -> Path | None:
    """Zet audio om naar 16 kHz mono 16-bit PCM — precies wat whisper.cpp intern wil.

    Reden (22 aug 2026): whisper-cli leest audio via de ingebouwde decoders van
    ggml/dr_libs en is nergens tegen libav* gelinkt (`otool -L` bevestigt dat). Die
    decoders kennen wav, mp3 en flac — géén m4a/aac of opus. Erger: bij een onleesbaar
    bestand meldt whisper-cli `error: failed to read audio file` en sluit af met
    **exit 0** en zonder .txt. `download_audio()` accepteert daarentegen wél
    m4a/ogg, dus die twee stonden scheef op elkaar.

    Gemeten blootstelling op dat moment: 839 van 840 gecachete afleveringen was mp3,
    één m4a (Van Zorg Verzekerd). Klein dus — dit is verzekering, geen brandje. Maar
    het maakt het formaat irrelevant en scheelt whisper bovendien het interne
    resamplen.

    Geeft None als ffmpeg ontbreekt of de omzetting faalt; de aanroeper valt dan terug
    op het originele bestand, precies zoals vóór deze stap. ffmpeg is dus een
    verbetering, geen nieuwe harde afhankelijkheid.
    """
    if not FFMPEG.exists():
        return None
    wav_path = audio_path.with_suffix(".16k.wav")
    result = subprocess.run(
        [str(FFMPEG), "-y", "-loglevel", "error", "-i", str(audio_path),
         "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(wav_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not wav_path.exists():
        print(f"  ffmpeg-omzetting mislukt (exit {result.returncode}), "
              f"whisper krijgt het originele bestand: {_knip(result.stderr, 300, 300)}",
              file=sys.stderr)
        wav_path.unlink(missing_ok=True)
        return None
    return wav_path


def transcribe_audio(audio_path: Path, model: str, language: str = "") -> Path | None:
    """Transcribert audio via whisper-cli; retourneert pad naar .txt output."""
    model_path = WHISPER_MODELS_DIR / f"ggml-{model}.bin"
    if not model_path.exists():
        print(f"  Whisper-model niet gevonden: {model_path}", file=sys.stderr)
        print(f"  Download via: brew run whisper-cpp --download-model {model}",
              file=sys.stderr)
        return None
    # Omzetten naar het formaat dat whisper zeker kan lezen; lukt dat niet, dan gaat het
    # originele bestand erin (zelfde gedrag als vóór deze stap).
    wav_path = _naar_wav(audio_path)
    bron = wav_path or audio_path
    try:
        return _draai_whisper(bron, model_path, language)
    finally:
        # De omgezette WAV is werkmateriaal van deze functie; de .txt niet — die leest
        # de aanroeper nog en ruimt hij zelf op.
        if wav_path is not None:
            wav_path.unlink(missing_ok=True)


def _draai_whisper(audio_path: Path, model_path: Path, language: str) -> Path | None:
    """Roept whisper-cli aan en beslist of de uitkomst bruikbaar is."""
    cmd = ["/opt/homebrew/bin/whisper-cli", "-m", str(model_path), "-otxt", str(audio_path)]
    if language:
        cmd += ["--language", language]
    result = subprocess.run(cmd, capture_output=True, text=True)
    # whisper-cli voegt .txt toe aan de volledige bestandsnaam: audio.mp3 → audio.mp3.txt
    txt_path = Path(str(audio_path) + ".txt")
    if result.returncode != 0:
        # Onderscheid tussen "gecrasht tijdens het rekenwerk" en "gecrasht bij het
        # afsluiten". Alleen in het tweede geval is de .txt compleet en mag hij mee.
        # Klakkeloos een bestaande .txt accepteren zou een halve transcriptie als heel
        # laten doorgaan — een afkapping die zich voordoet als een uitkomst.
        #
        # Gemeten geval (22 aug 2026, item FNHK8YYX): whisper-cli crashte in
        # ~ggml_metal_device_deleter tijdens __cxa_finalize_ranges, dus ná exit(). De
        # oorzaak is niet vastgesteld en bleek in isolatie niet reproduceerbaar —
        # dezelfde bron, hetzelfde model en dezelfde taal gaven exit 0. Wat wél vaststaat
        # is dat een crash in de afbouw minuten GPU-werk weggooide.
        if _whisper_liep_af(result.stderr) and txt_path.exists():
            print(f"  whisper-cli eindigde met exit {result.returncode}, maar had zijn werk "
                  f"al af (transcript geschreven) — storing in de afbouw, transcript behouden.",
                  file=sys.stderr)
            print(f"  whisper-cli uitvoer: {_knip(result.stderr)}", file=sys.stderr)
            return txt_path
        print(f"  whisper-cli fout (exit {result.returncode}): {_knip(result.stderr)}",
              file=sys.stderr)
        return None
    return txt_path if txt_path.exists() else None
