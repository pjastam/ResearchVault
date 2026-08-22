"""
test_attach_transcript.py — tests voor de whisper-foutafhandeling.

Draait op kale stdlib (de CI heeft geen pip-install-stap). Het bestand draagt een
hyphen en is dus niet gewoon importeerbaar; vandaar de importlib-omweg, net als in
test_feedreader_server.py.
"""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def _laad():
    sys.path.insert(0, str(SCRIPT_DIR))
    # Gezette sleutel → zotero_api slaat de dotenv-import over, zodat de test ook
    # zonder python-dotenv draait. Er gaat geen enkel verzoek uit.
    os.environ.setdefault("ZOTERO_API_KEY", "test-geen-echte-sleutel")
    pad = SCRIPT_DIR / "attach-transcript.py"
    spec = importlib.util.spec_from_file_location("attach_transcript", pad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


at = _laad()

# Zoals whisper-cli het werkelijk afdrukt (gemeten op deze machine, 22 aug 2026).
VOLLEDIG = """load_backend: loaded BLAS backend from /opt/homebrew/Cellar/ggml/libggml-blas.so
ggml_metal_device_init: GPU name:   MTL0 (Apple M4)
whisper_init_with_params_no_state: use gpu    = 1
output_txt: saving output to 'audio.mp3.txt'

whisper_print_timings:     load time =   803.48 ms
whisper_print_timings:    total time =  1941.38 ms
ggml_metal_free: deallocating
"""

AFGEBROKEN = """load_backend: loaded BLAS backend from /opt/homebrew/Cellar/ggml/libggml-blas.so
ggml_metal_device_init: GPU name:   MTL0 (Apple M4)
whisper_init_with_params_no_state: use gpu    = 1
"""


class TestWhisperLiepAf(unittest.TestCase):
    """Onderscheidt een crash in de afbouw van een crash tijdens het rekenwerk."""

    def test_beide_eindmarkeringen_aanwezig(self):
        self.assertTrue(at._whisper_liep_af(VOLLEDIG))

    def test_afgebroken_run_haalt_het_niet(self):
        self.assertFalse(at._whisper_liep_af(AFGEBROKEN))

    def test_alleen_txt_geschreven_is_niet_genoeg(self):
        # Het timingsblok ontbreekt: whisper is niet tot zijn natuurlijke einde gekomen.
        self.assertFalse(at._whisper_liep_af("output_txt: saving output to 'a.txt'\n"))

    def test_alleen_timings_is_niet_genoeg(self):
        self.assertFalse(at._whisper_liep_af("whisper_print_timings: total time = 1 ms\n"))

    def test_lege_uitvoer(self):
        self.assertFalse(at._whisper_liep_af(""))


class TestKnip(unittest.TestCase):
    """Regressietest bij de verloren crashdiagnose van 22 aug 2026.

    De oude regel was `stderr.strip()[-500:]`; bij een stackdump hield dat juist de
    buitenste frames over en gooide het de eigenlijke foutregel weg.
    """

    def test_korte_tekst_blijft_heel(self):
        self.assertEqual(at._knip("kort bericht"), "kort bericht")

    def test_lange_tekst_behoudt_de_eerste_regel(self):
        eerste = "libc++abi: terminating due to uncaught exception"
        tekst = eerste + "\n" + "\n".join(f"frame {i} in libsystem" for i in range(400))
        geknipt = at._knip(tekst)
        self.assertIn(eerste, geknipt)          # dit ontbrak in het echte incident
        self.assertIn("frame 399", geknipt)     # en de staart blijft ook staan
        self.assertIn("overgeslagen", geknipt)

    def test_grens_precies_op_maat_knipt_niet(self):
        tekst = "x" * 1600
        self.assertEqual(at._knip(tekst, kop=800, staart=800), tekst)

    def test_een_teken_erboven_knipt_wel(self):
        geknipt = at._knip("x" * 1601, kop=800, staart=800)
        self.assertIn("overgeslagen", geknipt)

    def test_none_klapt_niet(self):
        self.assertEqual(at._knip(None), "")



class TestNaarWav(unittest.TestCase):
    """De ffmpeg-voorstap (22 aug 2026).

    whisper-cli leest geen m4a/aac en meldt dat met exit 0 en zonder .txt — een
    onleesbaar bestand zag er dus uit als een mislukte transcriptie. Deze stap zet
    alles eerst om naar 16 kHz mono PCM; ontbreekt ffmpeg, dan verandert er niets.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bron = Path(self.tmp.name) / "_audio_TEST.mp3"
        self.bron.write_bytes(b"geen echte audio")
        self._origineel = at.FFMPEG

    def tearDown(self):
        at.FFMPEG = self._origineel
        self.tmp.cleanup()

    def test_zonder_ffmpeg_geen_omzetting(self):
        # Terugval op het originele bestand: ffmpeg is een verbetering, geen harde eis.
        at.FFMPEG = Path(self.tmp.name) / "bestaat-niet" / "ffmpeg"
        self.assertIsNone(at._naar_wav(self.bron))

    def test_mislukte_omzetting_geeft_none(self):
        at.FFMPEG = Path("/usr/bin/false")   # bestaat, exit 1, schrijft niets
        self.assertIsNone(at._naar_wav(self.bron))

    def test_mislukte_omzetting_laat_geen_rommel_achter(self):
        at.FFMPEG = Path("/usr/bin/false")
        at._naar_wav(self.bron)
        self.assertFalse((Path(self.tmp.name) / "_audio_TEST.16k.wav").exists())

    def test_bronbestand_blijft_ongemoeid(self):
        at.FFMPEG = Path("/usr/bin/false")
        at._naar_wav(self.bron)
        self.assertTrue(self.bron.exists())

    @unittest.skipUnless(Path("/opt/homebrew/bin/ffmpeg").exists(),
                         "ffmpeg niet geïnstalleerd op deze machine")
    def test_echte_omzetting_levert_16k_mono_pcm(self):
        import subprocess
        # Stilte van een halve seconde: klein, en genoeg om de kop te controleren.
        wav_in = Path(self.tmp.name) / "stilte.wav"
        subprocess.run(["/opt/homebrew/bin/ffmpeg", "-y", "-loglevel", "error",
                        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                        "-t", "0.5", str(wav_in)], check=True)
        uit = at._naar_wav(wav_in)
        self.assertIsNotNone(uit)
        self.assertTrue(uit.exists())
        kop = uit.read_bytes()[:44]
        # WAV-header: samplerate op byte 24-27, kanalen op 22-23 (little-endian).
        self.assertEqual(int.from_bytes(kop[24:28], "little"), 16000)
        self.assertEqual(int.from_bytes(kop[22:24], "little"), 1)
        uit.unlink()


if __name__ == "__main__":
    unittest.main()
