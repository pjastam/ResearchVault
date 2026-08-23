"""
feedreader_embed.py — De itemzijde van de intake-scoring
========================================================
Eén klasse, `OllamaEmbedder`, met de `.encode()`-vorm van `SentenceTransformer`,
en één fabriek, `maak_embedder()`, die het model uit de zotero-mcp-configuratie
leest.

Waarom deze laag bestaat
------------------------
De intake-scoring vergelijkt twee soorten vectoren met elkaar: het **profiel**,
opgebouwd uit de ChromaDB-collectie van zotero-mcp, en de **items** uit de feeds,
die op het moment van scoren worden geëmbed. Die twee zijden moeten uit hetzelfde
model komen, anders vergelijkt `cosine_similarity()` twee onvergelijkbare ruimtes.

Tot 23 aug 2026 stond het model op drie plaatsen hardgecodeerd als
`all-MiniLM-L6-v2` — in `feedreader-score.py`, opnieuw in `backfill-scout.py`, en
impliciet in de ChromaDB-collectie. ADR-0007 sprak van "beide plaatsen"; het waren
er drie. Eén sleutel in `config.json` is nu de enige bron, precies zoals besluit A
van 14 aug 2026 dat bij olw regelde nadat `wiki.toml` en `wiki-backend.toml` elk
een `model`-sleutel droegen en een halve wissel ingest en compile stil uiteen liet
lopen.

Waarom de fabriek weigert in plaats van te raden
------------------------------------------------
`maak_embedder()` werpt een `EmbedderConfigFout` zodra `config.json` geen expliciete
`model_name` draagt. Raden zou hier de gevaarlijkste uitkomst geven: zotero-mcp valt
in datzelfde geval terug op `qwen3-embedding` (`chroma_client.py`), een model dat
39x duurder is dan de gekozen `nomic-embed-text-v2-moe` — en de scores zouden er
plausibel uitzien terwijl de bibliotheekzijde uit een ander model komt.

De opener is injecteerbaar en `numpy` wordt lazy geïmporteerd, zodat de tests op
kale stdlib draaien zonder netwerk (net als `feedreader_fetch.py`).
"""

import json
import urllib.error
import urllib.request
from pathlib import Path

ZOTERO_MCP_CONFIG = Path.home() / ".config" / "zotero-mcp" / "config.json"
OLLAMA_BASE_URL = "http://localhost:11434"
EMBED_TIMEOUT_SECONDS = 300
EMBED_BATCH = 32

# Ollama kapt zelf af op het contextvenster van het model; dit is een tweede rem
# tegen een enkel absurd lang item dat de hele batch laat time-outen.
MAX_TEKENS_PER_TEKST = 8000


class EmbedderConfigFout(RuntimeError):
    """De configuratie wijst niet ondubbelzinnig één model aan."""


class EmbedderFout(RuntimeError):
    """De embedding-aanroep is mislukt."""


def _open_url(request, timeout):
    with urllib.request.urlopen(request, timeout=timeout) as antwoord:
        return antwoord.read()


class OllamaEmbedder:
    """Adapter rond Ollama's `/api/embed` met de aanroepvorm van SentenceTransformer.

    Bestaat om de twee bestaande aanroepplaatsen ongewijzigd te laten: zowel
    `feedreader-score.py` als `backfill-scout.py` roepen
    `model.encode(texts, batch_size=32, show_progress_bar=False)` aan.
    `show_progress_bar` wordt geaccepteerd en genegeerd — deze embedder draait in
    een batchscript waar niemand naar een balk kijkt.
    """

    def __init__(self, model_name: str, base_url: str = OLLAMA_BASE_URL,
                 opener=_open_url, timeout: int = EMBED_TIMEOUT_SECONDS):
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self._opener = opener
        self._timeout = timeout

    def __repr__(self) -> str:
        return f"OllamaEmbedder({self.model_name!r})"

    def encode(self, texts, batch_size: int = EMBED_BATCH,
               show_progress_bar: bool = False, **_genegeerd):
        """Embed een lijst teksten; geeft een (n, dim) float32-array terug."""
        import numpy as np

        teksten = list(texts)
        if not teksten:
            return np.zeros((0, 0), dtype=np.float32)

        uit = []
        for begin in range(0, len(teksten), max(1, batch_size)):
            brok = [t[:MAX_TEKENS_PER_TEKST] for t in teksten[begin:begin + batch_size]]
            uit.extend(self._embed_batch(brok))

        vectoren = np.array(uit, dtype=np.float32)
        if vectoren.shape[0] != len(teksten):
            # Ollama gaf minder vectoren terug dan er teksten in gingen. Stil
            # accepteren zou `zip(all_items, embeddings)` in feedreader-score.py
            # laten verschuiven: elk item kreeg dan de score van een ander item.
            raise EmbedderFout(
                f"{len(teksten)} teksten in, {vectoren.shape[0]} vectoren uit "
                f"(model {self.model_name!r})")
        return vectoren

    def _embed_batch(self, teksten: list[str]) -> list[list[float]]:
        body = json.dumps({"model": self.model_name, "input": teksten}).encode("utf-8")
        verzoek = urllib.request.Request(
            f"{self.base_url}/api/embed", data=body,
            headers={"Content-Type": "application/json"})
        try:
            rauw = self._opener(verzoek, self._timeout)
        except urllib.error.HTTPError as exc:
            raise EmbedderFout(
                f"Ollama gaf HTTP {exc.code} voor model {self.model_name!r} — "
                f"draait `ollama pull {self.model_name}` nog?") from exc
        except Exception as exc:
            raise EmbedderFout(f"Ollama niet bereikbaar op {self.base_url}: {exc}") from exc

        try:
            antwoord = json.loads(rauw)
        except ValueError as exc:
            raise EmbedderFout(f"Ollama gaf geen geldige JSON: {exc}") from exc

        vectoren = antwoord.get("embeddings")
        if not vectoren:
            # `/api/embed` antwoordt met HTTP 200 en een foutveld als het model
            # niet bestaat. Zonder deze controle wordt dat een lege array en
            # daarna een vormfout diep in numpy, ver van de oorzaak.
            raise EmbedderFout(
                f"Ollama gaf geen 'embeddings' terug voor {self.model_name!r}: "
                f"{antwoord.get('error', antwoord)}")
        return vectoren


def lees_model_uit_config(pad: Path = ZOTERO_MCP_CONFIG) -> str:
    """Het Ollama-model waarmee de ChromaDB-collectie is opgebouwd.

    Werpt in plaats van te raden: zie de moduletoelichting.
    """
    if not Path(pad).exists():
        raise EmbedderConfigFout(f"Geen zotero-mcp-configuratie op {pad}")
    try:
        config = json.loads(Path(pad).read_text(encoding="utf-8"))
    except ValueError as exc:
        raise EmbedderConfigFout(f"{pad} is geen geldige JSON: {exc}") from exc

    semantisch = config.get("semantic_search") or {}
    backend = semantisch.get("embedding_model")
    if backend != "ollama":
        raise EmbedderConfigFout(
            f"zotero-mcp draait op embedding_model={backend!r}; de itemzijde kan "
            f"die vectoren niet reproduceren. Zet 'ollama' in {pad}.")

    naam = (semantisch.get("embedding_config") or {}).get("model_name")
    if not naam:
        raise EmbedderConfigFout(
            f"embedding_config.model_name ontbreekt in {pad}. Zonder die sleutel "
            f"valt zotero-mcp terug op qwen3-embedding en komen bibliotheek- en "
            f"itemzijde uit verschillende modellen.")
    return naam


def maak_embedder(pad: Path = ZOTERO_MCP_CONFIG, **kwargs) -> OllamaEmbedder:
    """De embedder voor de itemzijde, met het model uit de zotero-mcp-configuratie."""
    return OllamaEmbedder(lees_model_uit_config(pad), **kwargs)
