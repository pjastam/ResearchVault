"""
test_feedreader_embed.py — unittests voor de itemzijde van de intake-scoring.

Geen netwerk, geen Ollama: de opener is injecteerbaar. `numpy` is de enige
niet-stdlib afhankelijkheid en wordt lazy geïmporteerd in `encode()`; de tests die
hem nodig hebben slaan zichzelf over als hij ontbreekt, zodat de rest op een kale
CI-runner blijft draaien.
"""

import json
import unittest
import urllib.error
from pathlib import Path
from tempfile import TemporaryDirectory

from feedreader_embed import (
    EmbedderConfigFout,
    EmbedderFout,
    OllamaEmbedder,
    lees_model_uit_config,
    maak_embedder,
)

try:
    import numpy  # noqa: F401
    HEEFT_NUMPY = True
except ImportError:  # pragma: no cover - alleen op een kale runner
    HEEFT_NUMPY = False

heeft_numpy = unittest.skipUnless(HEEFT_NUMPY, "numpy niet beschikbaar")


def schrijf_config(map_pad: str, inhoud) -> Path:
    pad = Path(map_pad) / "config.json"
    pad.write_text(json.dumps(inhoud) if not isinstance(inhoud, str) else inhoud,
                   encoding="utf-8")
    return pad


def nep_opener(vectoren, verzoeken=None):
    """Opener die vaste vectoren teruggeeft en de verzoeken vastlegt."""
    def opener(verzoek, timeout):
        if verzoeken is not None:
            verzoeken.append(json.loads(verzoek.data))
        n = len(json.loads(verzoek.data)["input"])
        return json.dumps({"embeddings": vectoren[:n]}).encode()
    return opener


class TestLeesModelUitConfig(unittest.TestCase):
    """De fabriek moet weigeren in plaats van raden — raden geeft qwen3-embedding."""

    def test_leest_model_naam(self):
        with TemporaryDirectory() as d:
            pad = schrijf_config(d, {"semantic_search": {
                "embedding_model": "ollama",
                "embedding_config": {"model_name": "nomic-embed-text-v2-moe"}}})
            self.assertEqual(lees_model_uit_config(pad), "nomic-embed-text-v2-moe")

    def test_ontbrekende_model_naam_werpt(self):
        """Precies de valstrik uit het plan: zonder deze sleutel valt zotero-mcp
        terug op qwen3-embedding, 39x duurder, en niemand ziet het."""
        with TemporaryDirectory() as d:
            pad = schrijf_config(d, {"semantic_search": {"embedding_model": "ollama"}})
            with self.assertRaises(EmbedderConfigFout) as ctx:
                lees_model_uit_config(pad)
            self.assertIn("qwen3-embedding", str(ctx.exception))

    def test_lege_model_naam_werpt(self):
        with TemporaryDirectory() as d:
            pad = schrijf_config(d, {"semantic_search": {
                "embedding_model": "ollama", "embedding_config": {"model_name": ""}}})
            with self.assertRaises(EmbedderConfigFout):
                lees_model_uit_config(pad)

    def test_andere_backend_werpt(self):
        """'default' is de MiniLM-ONNX-backend; die kan de itemzijde niet nabootsen."""
        with TemporaryDirectory() as d:
            pad = schrijf_config(d, {"semantic_search": {"embedding_model": "default"}})
            with self.assertRaises(EmbedderConfigFout) as ctx:
                lees_model_uit_config(pad)
            self.assertIn("default", str(ctx.exception))

    def test_ontbrekend_bestand_werpt(self):
        with TemporaryDirectory() as d:
            with self.assertRaises(EmbedderConfigFout):
                lees_model_uit_config(Path(d) / "bestaat-niet.json")

    def test_kapotte_json_werpt(self):
        with TemporaryDirectory() as d:
            pad = schrijf_config(d, "{niet: geldig")
            with self.assertRaises(EmbedderConfigFout):
                lees_model_uit_config(pad)

    def test_maak_embedder_draagt_model_over(self):
        with TemporaryDirectory() as d:
            pad = schrijf_config(d, {"semantic_search": {
                "embedding_model": "ollama",
                "embedding_config": {"model_name": "nomic-embed-text-v2-moe"}}})
            emb = maak_embedder(pad, opener=nep_opener([[0.0]]))
            self.assertEqual(emb.model_name, "nomic-embed-text-v2-moe")


class TestEncode(unittest.TestCase):

    @heeft_numpy
    def test_lege_lijst_geeft_lege_array(self):
        emb = OllamaEmbedder("m", opener=nep_opener([]))
        self.assertEqual(emb.encode([]).shape[0], 0)

    @heeft_numpy
    def test_vorm_en_dtype(self):
        emb = OllamaEmbedder("m", opener=nep_opener([[1.0, 2.0], [3.0, 4.0]]))
        uit = emb.encode(["a", "b"])
        self.assertEqual(uit.shape, (2, 2))
        self.assertEqual(uit.dtype.name, "float32")

    @heeft_numpy
    def test_batcht_in_brokken(self):
        verzoeken = []
        emb = OllamaEmbedder("m", opener=nep_opener([[1.0]] * 32, verzoeken))
        emb.encode(["x"] * 5, batch_size=2)
        self.assertEqual([len(v["input"]) for v in verzoeken], [2, 2, 1])

    @heeft_numpy
    def test_volgorde_blijft_behouden_over_batches(self):
        """zip(all_items, embeddings) in feedreader-score.py leunt hierop."""
        def opener(verzoek, timeout):
            teksten = json.loads(verzoek.data)["input"]
            return json.dumps({"embeddings": [[float(t)] for t in teksten]}).encode()
        emb = OllamaEmbedder("m", opener=opener)
        uit = emb.encode(["1", "2", "3", "4", "5"], batch_size=2)
        self.assertEqual([v[0] for v in uit.tolist()], [1.0, 2.0, 3.0, 4.0, 5.0])

    @heeft_numpy
    def test_te_weinig_vectoren_werpt(self):
        """Stil accepteren zou elk item de score van een ánder item geven."""
        def opener(verzoek, timeout):
            return json.dumps({"embeddings": [[1.0]]}).encode()
        emb = OllamaEmbedder("m", opener=opener)
        with self.assertRaises(EmbedderFout) as ctx:
            emb.encode(["a", "b"], batch_size=8)
        self.assertIn("2 teksten in", str(ctx.exception))

    @heeft_numpy
    def test_kapt_lange_tekst_af(self):
        verzoeken = []
        emb = OllamaEmbedder("m", opener=nep_opener([[1.0]], verzoeken))
        emb.encode(["x" * 20_000])
        self.assertEqual(len(verzoeken[0]["input"][0]), 8000)

    @heeft_numpy
    def test_show_progress_bar_wordt_geslikt(self):
        """De aanroepvorm van SentenceTransformer moet ongewijzigd blijven werken."""
        emb = OllamaEmbedder("m", opener=nep_opener([[1.0]]))
        emb.encode(["a"], batch_size=32, show_progress_bar=False)

    @heeft_numpy
    def test_model_naam_gaat_mee_in_het_verzoek(self):
        verzoeken = []
        emb = OllamaEmbedder("nomic-embed-text-v2-moe", opener=nep_opener([[1.0]], verzoeken))
        emb.encode(["a"])
        self.assertEqual(verzoeken[0]["model"], "nomic-embed-text-v2-moe")


class TestFouten(unittest.TestCase):
    """Een storing mag zich nooit voordoen als een uitkomst."""

    @heeft_numpy
    def test_onbereikbaar_werpt(self):
        def opener(verzoek, timeout):
            raise OSError("connection refused")
        with self.assertRaises(EmbedderFout) as ctx:
            OllamaEmbedder("m", opener=opener).encode(["a"])
        self.assertIn("niet bereikbaar", str(ctx.exception))

    @heeft_numpy
    def test_http_fout_noemt_het_model(self):
        def opener(verzoek, timeout):
            raise urllib.error.HTTPError("u", 404, "Not Found", {}, None)
        with self.assertRaises(EmbedderFout) as ctx:
            OllamaEmbedder("weg-model", opener=opener).encode(["a"])
        self.assertIn("weg-model", str(ctx.exception))

    @heeft_numpy
    def test_http_200_met_foutveld_werpt(self):
        """Ollama antwoordt met 200 en een 'error'-veld als het model ontbreekt."""
        def opener(verzoek, timeout):
            return json.dumps({"error": "model 'x' not found"}).encode()
        with self.assertRaises(EmbedderFout) as ctx:
            OllamaEmbedder("x", opener=opener).encode(["a"])
        self.assertIn("not found", str(ctx.exception))

    @heeft_numpy
    def test_geen_json_werpt(self):
        def opener(verzoek, timeout):
            return b"<html>502 Bad Gateway</html>"
        with self.assertRaises(EmbedderFout) as ctx:
            OllamaEmbedder("m", opener=opener).encode(["a"])
        self.assertIn("geldige JSON", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
