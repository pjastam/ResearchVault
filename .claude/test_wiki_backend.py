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


class TestRender(unittest.TestCase):
    def test_all_placeholders_filled(self):
        with tempfile.TemporaryDirectory() as t:
            v = make_vault(t)
            res = wiki_backend.render("ingest", v, file="/tmp/a.md")
            self.assertEqual(res["status"], "ok")
            self.assertEqual(res["command"], [
                "/usr/bin/true", "ingest", "/tmp/a.md",
                "--vault", str(Path(t).resolve()), "--fast-model", "m:22b",
            ])

    def test_optional_segment_present_when_value_given(self):
        with tempfile.TemporaryDirectory() as t:
            v = make_vault(t)
            res = wiki_backend.render("reject", v, draft="/tmp/d.md", feedback="te dun")
            self.assertIn("--feedback", res["command"])
            self.assertIn("te dun", res["command"])

    def test_optional_segment_dropped_when_value_absent(self):
        with tempfile.TemporaryDirectory() as t:
            v = make_vault(t)
            res = wiki_backend.render("reject", v, draft="/tmp/d.md")
            self.assertEqual(res["status"], "ok")
            self.assertNotIn("--feedback", res["command"])

    def test_optional_segment_dropped_when_value_empty_string(self):
        with tempfile.TemporaryDirectory() as t:
            v = make_vault(t)
            res = wiki_backend.render("reject", v, draft="/tmp/d.md", feedback="")
            self.assertNotIn("--feedback", res["command"])

    def test_unfillable_required_placeholder_is_error(self):
        with tempfile.TemporaryDirectory() as t:
            v = make_vault(t)
            res = wiki_backend.render("ingest", v)   # geen file=
            self.assertEqual(res["status"], "error")
            self.assertIn("file", res["error"])

    def test_values_with_spaces_stay_single_argv_entries(self):
        with tempfile.TemporaryDirectory() as t:
            v = make_vault(t)
            res = wiki_backend.render("reject", v, draft="/tmp/d.md",
                                      feedback='twee woorden "met quotes"')
            self.assertIn('twee woorden "met quotes"', res["command"])

    def test_vault_placeholder_uses_normalized_path(self):
        with tempfile.TemporaryDirectory() as t:
            real = Path(t) / "real"
            real.mkdir()
            make_vault(real)
            link = Path(t) / "link"
            link.symlink_to(real)
            res = wiki_backend.render("compile", link)
            self.assertIn(str(real.resolve()), res["command"])

    def test_missing_timeout_for_declared_verb_is_error(self):
        with tempfile.TemporaryDirectory() as t:
            v = Path(t)
            block = OLW_BLOCK.replace("timeout    = 1800\n", "")
            block = block.replace("timeout_approve = 120\n", "")
            (v / "wiki-backend.toml").write_text(
                'confidential = false\nbackend = "olw"\n' + block, encoding="utf-8")
            res = wiki_backend.render("ingest", v, file="/tmp/a.md")
            self.assertEqual(res["status"], "error")
            self.assertIn("timeout", res["error"])

    def test_per_verb_timeout_overrides_fallback(self):
        with tempfile.TemporaryDirectory() as t:
            v = make_vault(t)
            self.assertEqual(wiki_backend.render("approve", v, draft="/d.md")["timeout"], 120)
            self.assertEqual(wiki_backend.render("compile", v)["timeout"], 1800)

    def test_missing_verb_template_is_skipped_for_none_backend(self):
        with tempfile.TemporaryDirectory() as t:
            v = Path(t)
            (v / "wiki-backend.toml").write_text(
                'confidential = false\nbackend = "none"\n\n'
                '[backends.none]\ninvocation = "cli"\nlocality = "local"\n',
                encoding="utf-8")
            res = wiki_backend.render("ingest", v, file="/tmp/a.md")
            self.assertEqual(res["status"], "skipped")

    def test_empty_verb_template_is_unsupported_with_hint(self):
        with tempfile.TemporaryDirectory() as t:
            v = Path(t)
            (v / "wiki-backend.toml").write_text(
                'confidential = false\nbackend = "co"\n\n'
                '[backends.co]\ninvocation = "session"\nlocality = "cloud"\n'
                'timeout = 600\ncapture = "/usr/bin/true capture {file}"\n'
                'approve = ""\nsession_hint = "gebruik Claude Code"\n',
                encoding="utf-8")
            res = wiki_backend.render("approve", v, draft="/d.md")
            self.assertEqual(res["status"], "unsupported")
            self.assertEqual(res["hint"], "gebruik Claude Code")

    def test_status_always_in_closed_vocabulary(self):
        allowed = {"ok", "skipped", "unsupported", "error"}
        with tempfile.TemporaryDirectory() as t:
            v = make_vault(t)
            for call in (
                lambda: wiki_backend.render("ingest", v, file="/a.md"),
                lambda: wiki_backend.render("ingest", v),
                lambda: wiki_backend.load(v),
            ):
                self.assertIn(call()["status"], allowed)


CLOUD_BLOCK = """
[backends.cloud]
invocation = "cli"
locality   = "cloud"
bin        = "/usr/bin/true"
state_dir  = ".cloud"
timeout    = 600
force_args = "--offline"
ingest = "{bin} ingest {file} --vault {vault}"
"""

SESSION_BLOCK = """
[backends.sess]
invocation = "session"
locality   = "local"
bin        = "/usr/bin/true"
state_dir  = ".sess"
timeout    = 600
force_args = "--offline"
ingest = "{bin} ingest {file} --vault {vault}"
"""

# Cloud-backend (triggert de guardrail) die het verb "approve" niet ondersteunt (leeg
# template). Bewaakt de bindende volgorde-eis in render(): capability-check vóór guardrail.
CLOUD_UNSUPPORTED_APPROVE_BLOCK = """
[backends.cloudnoapprove]
invocation = "cli"
locality   = "cloud"
bin        = "/usr/bin/true"
state_dir  = ".cloud"
timeout    = 600
force_args = "--offline"
ingest = "{bin} ingest {file} --vault {vault}"
approve = ""
"""


def write_vault(tmp, backend, block, confidential):
    v = Path(tmp)
    (v / "wiki-backend.toml").write_text(
        f'confidential = {"true" if confidential else "false"}\n'
        f'backend = "{backend}"\n' + block, encoding="utf-8")
    if confidential:
        (v / ".confidential").write_text("", encoding="utf-8")
    return v


class TestGuardrail(unittest.TestCase):
    def test_cloud_backend_on_confidential_vault_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            v = write_vault(t, "cloud", CLOUD_BLOCK, confidential=True)
            res = wiki_backend.render("ingest", v, file="/a.md")
            self.assertEqual(res["status"], "error")
            self.assertIn("cloud", res["error"])
            self.assertIn(str(Path(t).resolve()), res["error"])

    def test_session_backend_on_confidential_vault_is_refused_even_when_local(self):
        with tempfile.TemporaryDirectory() as t:
            v = write_vault(t, "sess", SESSION_BLOCK, confidential=True)
            res = wiki_backend.render("ingest", v, file="/a.md")
            self.assertEqual(res["status"], "error")
            self.assertIn("session", res["error"])

    def test_cloud_backend_on_normal_vault_is_allowed(self):
        with tempfile.TemporaryDirectory() as t:
            v = write_vault(t, "cloud", CLOUD_BLOCK, confidential=False)
            res = wiki_backend.render("ingest", v, file="/a.md")
            self.assertEqual(res["status"], "ok")

    def test_force_args_appended_to_every_verb_on_confidential_vault(self):
        with tempfile.TemporaryDirectory() as t:
            v = make_vault(t, confidential=True)
            for verb, kw in (("ingest", {"file": "/a.md"}), ("compile", {}),
                             ("approve", {"draft": "/d.md"})):
                cmd = wiki_backend.render(verb, v, **kw)["command"]
                self.assertIn("--provider", cmd, f"{verb} mist force_args")
                self.assertIn("http://localhost:11434", cmd)

    def test_force_args_not_appended_on_normal_vault(self):
        with tempfile.TemporaryDirectory() as t:
            v = make_vault(t, confidential=False)
            self.assertNotIn("--provider",
                             wiki_backend.render("compile", v)["command"])

    def test_unsupported_verb_on_confidential_vault_reports_unsupported_not_guardrail_error(self):
        """Bewaakt de bindende volgorde in render(): de capability-check (verb bestaat en
        heeft een niet-leeg template) moet vóór de guardrail-gate lopen. Deze vault is
        vertrouwelijk mét een cloud-backend die de guardrail zou triggeren, maar 'approve'
        heeft een leeg template. Verwacht 'unsupported' (configuratie-info), niet 'error'
        (guardrail-weigering). Zet iemand de gate vóór de capabilitycheck, dan wordt dit
        'error' en gaat deze test rood."""
        with tempfile.TemporaryDirectory() as t:
            v = write_vault(t, "cloudnoapprove", CLOUD_UNSUPPORTED_APPROVE_BLOCK,
                             confidential=True)
            res = wiki_backend.render("approve", v, draft="/d.md")
            self.assertEqual(res["status"], "unsupported")


FAILING_BLOCK = """
[backends.olw]
invocation = "cli"
locality   = "local"
bin        = "/usr/bin/false"
state_dir  = ".olw"
timeout    = 30
compile = "{bin} compile --vault {vault}"
"""

LEAKY_BLOCK = """
[backends.olw]
invocation = "cli"
locality   = "local"
bin        = "/bin/sh"
state_dir  = ".olw"
timeout    = 30
compile = "{bin} -c echo_geheim_op_stdout_en_exit_1"
"""

# Schrijft eerst een herkenbare marker naar stdout en gaat dan langer slapen dan de
# timeout — zo bewijst de test dat de marker écht geschreven is (en dus iets is om
# tegen te toetsen) én dat hij niet in de returnwaarde terechtkomt.
TIMEOUT_BLOCK = """
[backends.olw]
invocation = "cli"
locality   = "local"
bin        = "/bin/sh"
state_dir  = ".olw"
timeout    = 1
compile = "{bin} -c 'echo herkenbare_marker_voor_timeout_test; sleep 5'"
"""


class TestRun(unittest.TestCase):
    def test_success_returns_ok_and_log_path(self):
        with tempfile.TemporaryDirectory() as t:
            v = make_vault(t)
            res = wiki_backend.run("compile", v)
            self.assertEqual(res["status"], "ok")
            self.assertEqual(res["returncode"], 0)
            self.assertTrue(Path(res["log"]).is_file())

    def test_log_lives_inside_vault_with_tight_permissions(self):
        with tempfile.TemporaryDirectory() as t:
            v = make_vault(t)
            res = wiki_backend.run("compile", v)
            log = Path(res["log"])
            self.assertEqual(log.parent, Path(t).resolve() / ".wiki-backend")
            self.assertEqual(log.parent.stat().st_mode & 0o777, 0o700)
            self.assertEqual(log.stat().st_mode & 0o777, 0o600)

    def test_failure_reports_returncode_and_log_but_no_output(self):
        with tempfile.TemporaryDirectory() as t:
            v = Path(t)
            (v / "wiki-backend.toml").write_text(
                'confidential = false\nbackend = "olw"\n' + FAILING_BLOCK, encoding="utf-8")
            res = wiki_backend.run("compile", v)
            self.assertEqual(res["status"], "error")
            self.assertEqual(res["returncode"], 1)
            self.assertIn("compile.log", res["log"])

    def test_no_subprocess_output_leaks_into_result(self):
        """De kernbelofte uit spec §5: nooit loginhoud in de returnwaarde."""
        with tempfile.TemporaryDirectory() as t:
            v = Path(t)
            (v / "wiki-backend.toml").write_text(
                'confidential = false\nbackend = "olw"\n' + LEAKY_BLOCK, encoding="utf-8")
            res = wiki_backend.run("compile", v)
            self.assertEqual(res["status"], "error")
            blob = repr(res)
            self.assertNotIn("echo_geheim_op_stdout_en_exit_1", blob)

    def test_timeout_reports_returncode_none_and_no_output(self):
        """Het timeout-pad is ongetest gebleven bij de eerste implementatie — deze test
        toont aan dat het privacycontract ook hier standhoudt: er bestaat geen exit-code
        (proces liep nog), dus returncode moet aanwezig én None zijn, en de herkenbare
        marker die het commando vóór het slapen naar stdout schreef mag niet in de
        returnwaarde lekken."""
        with tempfile.TemporaryDirectory() as t:
            v = Path(t)
            (v / "wiki-backend.toml").write_text(
                'confidential = false\nbackend = "olw"\n' + TIMEOUT_BLOCK, encoding="utf-8")
            res = wiki_backend.run("compile", v)
            self.assertEqual(res["status"], "error")
            self.assertIn("returncode", res)
            self.assertIsNone(res["returncode"])
            blob = repr(res)
            self.assertNotIn("herkenbare_marker_voor_timeout_test", blob)

    def test_exec_failure_reports_returncode_none_directly_indexable(self):
        """Wanneer het subprocess niet eens kan starten (ontbrekende binary), moet
        res["returncode"] uitleesbaar zijn met directe indexering — geen .get() nodig.
        Dat was precies de eigenschap die kapot was vóór deze fix."""
        with tempfile.TemporaryDirectory() as t:
            v = Path(t)
            missing_bin = str(Path(t) / "nonexistent-dir" / "no-such-binary")
            block = f"""
[backends.olw]
invocation = "cli"
locality   = "local"
bin        = "{missing_bin}"
state_dir  = ".olw"
timeout    = 30
compile = "{{bin}} compile --vault {{vault}}"
"""
            (v / "wiki-backend.toml").write_text(
                'confidential = false\nbackend = "olw"\n' + block, encoding="utf-8")
            res = wiki_backend.run("compile", v)
            self.assertEqual(res["status"], "error")
            self.assertIsNone(res["returncode"])

    def test_skipped_passes_through_without_subprocess(self):
        with tempfile.TemporaryDirectory() as t:
            v = Path(t)
            (v / "wiki-backend.toml").write_text(
                'confidential = false\nbackend = "none"\n\n'
                '[backends.none]\ninvocation = "cli"\nlocality = "local"\n',
                encoding="utf-8")
            res = wiki_backend.run("ingest", v, file="/a.md")
            self.assertEqual(res["status"], "skipped")
            self.assertFalse((Path(t) / ".wiki-backend").exists())

    def test_unsupported_passes_through_without_subprocess(self):
        """Spiegelt de `skipped`-test. Een leeg verb-template betekent: deze backend
        heeft voor dit verb geen subprocess-pad (de claude-obsidian-configuratie uit
        docs/src/backends/claude-obsidian.md). Er valt dus niets te draaien en niets
        te loggen — de vroege return in render() moet vóór logmap en subprocess komen.
        De hint moet meekomen, want die vertelt de gebruiker wat hij zelf moet doen."""
        with tempfile.TemporaryDirectory() as t:
            v = Path(t)
            (v / "wiki-backend.toml").write_text(
                'confidential = false\nbackend = "claude-obsidian"\n\n'
                '[backends.claude-obsidian]\ninvocation = "session"\n'
                'locality = "cloud"\ntimeout = 600\ningest = ""\n'
                'session_hint = "open Claude Code in this vault and ask for wiki-ingest"\n',
                encoding="utf-8")
            res = wiki_backend.run("ingest", v, file="/a.md")
            self.assertEqual(res["status"], "unsupported")
            self.assertIn("wiki-ingest", res["hint"])
            self.assertFalse((Path(t) / ".wiki-backend").exists())

    def test_no_public_function_ever_raises_systemexit(self):
        with tempfile.TemporaryDirectory() as t:
            broken = Path(t) / "broken"
            broken.mkdir()
            for call in (
                lambda: wiki_backend.load(broken),
                lambda: wiki_backend.render("ingest", broken, file="/a.md"),
                lambda: wiki_backend.run("ingest", broken, file="/a.md"),
            ):
                try:
                    call()
                except SystemExit:
                    self.fail("geen enkele publieke functie mag sys.exit() aanroepen")


if __name__ == "__main__":
    unittest.main()
