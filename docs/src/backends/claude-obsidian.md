# Backend: claude-obsidian

[claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian) turns sources into a linked knowledge graph using Claude through Claude Code.

## Two things to understand first

**It is a cloud backend.** Synthesis runs through the Anthropic API, so bundle content leaves your machine. It cannot run on a vault marked confidential.

**It is a session backend.** Its CLI subcommands are `doctor, transaction, hook, lint, contracts, package, release, capture, mode, extension, migrate, init, adopt, checkpoint`. The wiki functions — `wiki-ingest`, `wiki-query`, `wiki-lint` — are Claude Code Agent Skills invoked in natural language inside a running session, not CLI verbs. Only `capture` and `transaction` are subprocesses.

ResearchVault therefore drives it partially: the dispatcher can hand a bundle to `capture`, and then tells you what to do next.

## Configuration

```toml
confidential = false
backend      = "claude-obsidian"

[backends.claude-obsidian]
invocation = "session"
locality   = "cloud"
root       = "~/tools/claude-obsidian"
state_dir  = ".claude-obsidian"
drafts_dir = ""
timeout    = 600
capture = "python3 {root}/claude-obsidian.py capture {file}"
ingest  = ""
compile = ""
approve = ""
reject  = ""
session_hint = "open Claude Code in this vault and ask for wiki-ingest"
```

Empty verbs are not an oversight — they declare that this backend does not support that step through a subprocess. The dispatcher returns `unsupported` and shows `session_hint` rather than pretending to have done something.
