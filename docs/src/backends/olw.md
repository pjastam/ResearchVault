# Backend: olw (obsidian-llm-wiki)

[olw](https://github.com/kytmanov/obsidian-llm-wiki) ingests bundles from `raw/` and compiles interlinked concept pages into `wiki/`, running a local model through Ollama. It is the default backend and the one this project has run in production.

Install: `uv tool install obsidian-llm-wiki`

## Configuration

```toml
confidential = false
backend      = "olw"

[backends.olw]
invocation = "cli"
locality   = "local"
bin        = "~/.local/bin/olw"
config     = "wiki.toml"
state_dir  = ".olw"
drafts_dir = "wiki/.drafts"
model      = "mistral-small:22b"
timeout    = 1800
timeout_approve = 120
timeout_reject  = 120
ingest  = "{bin} ingest {file} --vault {vault} --fast-model {model}"
compile = "{bin} compile --vault {vault}"
approve = "{bin} approve {draft} --vault {vault}"
reject  = "{bin} reject {draft} --vault {vault}[ --feedback {feedback}]"
```

On a confidential vault, add:

```toml
force_args = "--provider ollama --provider-url http://localhost:11434"
```

## Backend-owned configuration

`wiki.toml` in your vault root is **olw's own configuration file**, not ResearchVault's. Models, context window, and pipeline switches live there. `wiki-backend.toml` only points at it.

## Workflow

`olw review` is the human quality gate: drafts land in `wiki/.drafts/`, you approve or reject, and approved pages publish to `wiki/` with cross-links.

## What a compiled draft contains

For papers, `olw compile` produces a draft page with:
- YAML frontmatter (title, authors, year, journal, citation key, tags, status)
- Core question and main argument
- Key findings (3–5 points)
- Methodological notes
- Relevant quotes (original language)
- Links to related pages

For video and podcast sources, the structure is the same except:
- Frontmatter carries a Zotero deep link instead of journal metadata
- A TLDR replaces the core question
- There is no quotes section — timestamps are unreliable without a verifiable source

Both variants get the same key findings, methodological notes, and links to related pages.
