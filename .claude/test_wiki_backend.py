#!/usr/bin/env python3
"""Tests voor wiki_backend.py — stdlib unittest, geen dependencies."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wiki_backend  # noqa: E402


OLW_BLOCK = """
[backends.olw]
invocation = "cli"
locality   = "local"
bin        = "/usr/bin/true"
state_dir  = ".olw"
drafts_dir = "wiki/.drafts"
model      = "m:22b"
timeout    = 1800
timeout_approve = 120
force_args = "--provider ollama --provider-url http://localhost:11434"
ingest  = "{bin} ingest {file} --vault {vault} --fast-model {model}"
compile = "{bin} compile --vault {vault}"
approve = "{bin} approve {draft} --vault {vault}"
reject  = "{bin} reject {draft} --vault {vault}[ --feedback {feedback}]"
"""


def make_vault(tmp, *, config=True, confidential=False, marker=None, extra=""):
    """Bouwt een tijdelijke vault. `marker=None` volgt `confidential`."""
    v = Path(tmp)
    (v / "raw").mkdir(exist_ok=True)
    if config:
        body = f'confidential = {"true" if confidential else "false"}\n'
        body += 'backend = "olw"\n' + OLW_BLOCK + extra
        (v / "wiki-backend.toml").write_text(body, encoding="utf-8")
    place_marker = confidential if marker is None else marker
    if place_marker:
        (v / ".confidential").write_text("", encoding="utf-8")
    return v


class TestLoad(unittest.TestCase):
    def test_ok_personal_vault(self):
        with tempfile.TemporaryDirectory() as t:
            v = make_vault(t)
            res = wiki_backend.load(v)
            self.assertEqual(res["status"], "ok")
            self.assertFalse(res["confidential"])
            self.assertEqual(res["backend"], "olw")
            self.assertEqual(res["cfg"]["state_dir"], ".olw")

    def test_missing_config_is_error_with_repair_hint(self):
        with tempfile.TemporaryDirectory() as t:
            v = make_vault(t, config=False)
            res = wiki_backend.load(v)
            self.assertEqual(res["status"], "error")
            self.assertIn("migrate-wiki-backend.py", res["error"])

    def test_unknown_backend_lists_available_names(self):
        with tempfile.TemporaryDirectory() as t:
            v = Path(t)
            (v / "wiki-backend.toml").write_text(
                'confidential = false\nbackend = "nope"\n' + OLW_BLOCK, encoding="utf-8")
            res = wiki_backend.load(v)
            self.assertEqual(res["status"], "error")
            self.assertIn("olw", res["error"])

    def test_missing_confidential_key_is_error(self):
        with tempfile.TemporaryDirectory() as t:
            v = Path(t)
            (v / "wiki-backend.toml").write_text('backend = "olw"\n' + OLW_BLOCK, encoding="utf-8")
            res = wiki_backend.load(v)
            self.assertEqual(res["status"], "error")
            self.assertIn("confidential", res["error"])

    def test_missing_locality_is_error(self):
        with tempfile.TemporaryDirectory() as t:
            v = Path(t)
            block = OLW_BLOCK.replace('locality   = "local"\n', "")
            (v / "wiki-backend.toml").write_text(
                'confidential = false\nbackend = "olw"\n' + block, encoding="utf-8")
            res = wiki_backend.load(v)
            self.assertEqual(res["status"], "error")
            self.assertIn("locality", res["error"])

    def test_missing_invocation_is_error(self):
        with tempfile.TemporaryDirectory() as t:
            v = Path(t)
            block = OLW_BLOCK.replace('invocation = "cli"\n', "")
            (v / "wiki-backend.toml").write_text(
                'confidential = false\nbackend = "olw"\n' + block, encoding="utf-8")
            res = wiki_backend.load(v)
            self.assertEqual(res["status"], "error")
            self.assertIn("invocation", res["error"])

    def test_config_true_marker_absent_is_error(self):
        with tempfile.TemporaryDirectory() as t:
            v = make_vault(t, confidential=True, marker=False)
            res = wiki_backend.load(v)
            self.assertEqual(res["status"], "error")
            self.assertIn(".confidential", res["error"])

    def test_config_false_marker_present_is_error(self):
        with tempfile.TemporaryDirectory() as t:
            v = make_vault(t, confidential=False, marker=True)
            res = wiki_backend.load(v)
            self.assertEqual(res["status"], "error")
            self.assertIn(".confidential", res["error"])

    def test_state_dir_missing_on_confidential_is_error(self):
        with tempfile.TemporaryDirectory() as t:
            v = Path(t)
            block = OLW_BLOCK.replace('state_dir  = ".olw"\n', "")
            (v / "wiki-backend.toml").write_text(
                'confidential = true\nbackend = "olw"\n' + block, encoding="utf-8")
            (v / ".confidential").write_text("", encoding="utf-8")
            res = wiki_backend.load(v)
            self.assertEqual(res["status"], "error")
            self.assertIn("state_dir", res["error"])

    def test_state_dir_missing_on_normal_vault_is_ok(self):
        with tempfile.TemporaryDirectory() as t:
            v = Path(t)
            block = OLW_BLOCK.replace('state_dir  = ".olw"\n', "")
            (v / "wiki-backend.toml").write_text(
                'confidential = false\nbackend = "olw"\n' + block, encoding="utf-8")
            res = wiki_backend.load(v)
            self.assertEqual(res["status"], "ok")

    def test_force_args_missing_on_confidential_is_error(self):
        with tempfile.TemporaryDirectory() as t:
            v = Path(t)
            block = OLW_BLOCK.replace(
                'force_args = "--provider ollama --provider-url http://localhost:11434"\n', "")
            (v / "wiki-backend.toml").write_text(
                'confidential = true\nbackend = "olw"\n' + block, encoding="utf-8")
            (v / ".confidential").write_text("", encoding="utf-8")
            res = wiki_backend.load(v)
            self.assertEqual(res["status"], "error")
            self.assertIn("force_args", res["error"])

    def test_confidential_vault_without_verbs_does_not_require_state_dir_or_force_args(self):
        """Test dat state_dir/force_args alleen verplicht zijn als backend verbs declareert.
        Dit test de has_verbs-voorwaarde (regel 264) die volledige bitterness zou veroorzaken."""
        with tempfile.TemporaryDirectory() as t:
            v = Path(t)
            # Backend zonder enkel verb; state_dir en force_args ontbreken.
            no_verb_block = """
[backends.static]
invocation = "none"
locality   = "local"
"""
            (v / "wiki-backend.toml").write_text(
                'confidential = true\nbackend = "static"\n' + no_verb_block, encoding="utf-8")
            (v / ".confidential").write_text("", encoding="utf-8")
            res = wiki_backend.load(v)
            # Status moet "ok" zijn omdat has_verbs=False (geen ingest/compile/approve/reject).
            self.assertEqual(res["status"], "ok")
            self.assertTrue(res["confidential"])
            self.assertEqual(res["backend"], "static")

    def test_load_never_raises_systemexit(self):
        with tempfile.TemporaryDirectory() as t:
            v = make_vault(t, config=False)
            try:
                wiki_backend.load(v)
            except SystemExit:
                self.fail("load() mag nooit sys.exit() aanroepen")


if __name__ == "__main__":
    unittest.main()
