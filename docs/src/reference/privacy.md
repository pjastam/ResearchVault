# Privacy overview

| Component | Data local? | Notes |
|---|---|---|
| Zotero + local API | ✅ Fully | Runs on `localhost`, no cloud |
| Zotero MCP + Web API | ⚠️ Partially | Read operations local; removing items from `_inbox` uses the Zotero Web API — item metadata (URL, title, type) goes to zotero.org |
| Obsidian vault | ✅ Fully | Regular files on your Mac |
| Ollama + mistral-small:22b | ✅ Fully | Primary local model runs on M4; used by olw for compile; default for all generative tasks |
| Ollama + Qwen3.5:9b | ✅ Fully | Fallback model only (Phase-2 previews via `summarize_item.py`); runs locally on M4 |
| yt-dlp | ✅ Fully | Scraping executed locally |
| whisper.cpp | ✅ Fully | Transcription locally on M4 via Metal |
| NetNewsWire | ✅ Fully | RSS data stored locally, no account |
| FreshRSS (Docker) | ✅ Fully | Self-hosted on Home Assistant Green (always-on); read/unread sync stays on your Tailscale network |
| feedreader (score/server/learn) | ✅ Fully | Runs locally; scoring uses local ChromaDB embeddings |
| ttyd | ✅ Fully | Browser terminal runs locally on Mac mini |
| olw (obsidian-llm-wiki) | ✅ Fully | Ingest/compile/review run locally; compile uses local mistral-small:22b via `wiki.toml` |
| Claude Code — orchestration | ⚠️ Partially | Workflow instructions and metadata go to the Anthropic API; **source content must not** |
| Claude Code — maximum-quality mode | ⚠️ Partially | Only on explicit request: Claude reads the source itself and sends prompt + source content to the Anthropic API (Claude Sonnet 4.6). This is an assistant mode, not a script flag — see below |

## The content privacy rule

The most important privacy boundary in this workflow is not which tools you use — it is **whether source content appears in Claude Code's context**.

Claude Code communicates with the Anthropic API in every session. This is unavoidable: it is how the orchestration layer works. What you can control is whether the *content* of your papers, transcripts, or articles gets included in that communication.

**The rule:** source content (full text of papers, article HTML, transcripts) must never be returned as output of a Bash command. The moment text appears as tool output, it has reached the Anthropic API.

**The safe pipeline — a local build followed by local olw stages:**

On Go, a canonical bundle is built from the Zotero item; source content is written to a local file and never returned to the terminal:

```bash
# Build the canonical bundle — only JSON status returned, no source content
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/build-zotero-bundle.py \
  --item-key ITEMKEY
# → {"status": "ok", "path": "raw/smith2024keyword__ITEMKEY.md"}
```

From there the pipeline runs entirely through olw (obsidian-llm-wiki), all local:

```bash
olw ingest     # register the new bundle from raw/
olw compile    # generate/update draft pages using local mistral-small:22b → wiki/.drafts/
olw review     # human quality gate in Claude Code; on approval, publish to wiki/
```

What goes to the Anthropic API in this pipeline: only item keys and metadata (title, authors, year, tags), plus your review decisions. What stays local: the full text, the mistral-small:22b generation, the bundle in `raw/`, the draft pages in `wiki/.drafts/`, and the published pages in `wiki/`.

**What the pipeline does internally (all local):**

1. `build-zotero-bundle.py` — assembles the Zotero attachment, notes and annotations into a canonical bundle at `raw/{citekey}__{itemKey}.md`; prints only file size and status.
2. `olw compile` — runs the local mistral-small:22b model (configured in `wiki.toml`) to generate draft concept/synthesis pages into `wiki/.drafts/`.
3. `olw review` — presents each draft for human approval; approved drafts are published to `wiki/`. This is the single quality gate.

No stage ever prints source content to the terminal or to Claude Code's context. Claude Code only sees JSON status objects and the draft text you deliberately review.

## What leaves your machine depends on your backend

ResearchVault itself never sends source content anywhere: `build-zotero-bundle.py` fetches text locally and writes a bundle; Claude Code receives only a status object. What happens after `raw/` is up to the backend you configured.

| Backend | Source content leaves the machine? |
|---|---|
| `olw` (local) | No. Synthesis runs on a local model through Ollama or MLX |
| `none` | No. There is no synthesis step |
| A cloud backend (e.g. claude-obsidian) | **Yes** — bundle content goes to that provider's API |

`locality` and `invocation` are mandatory declarations in `wiki-backend.toml`. There is no default in either direction: a backend that fails to declare them is refused rather than guessed at.

## Vaults holding confidential material

A vault can declare `confidential = true` and carry a `.confidential` marker. Both must agree — a disagreement is a hard error, so neither can silently go missing. On such a vault the dispatcher refuses cloud backends, session backends, and any backend that does not pin its provider through `force_args`. There is no fallback path.

## Two routes to the cloud, two different locks

Being precise about this matters more than sounding safe:

| Route | Lock | Nature |
|---|---|---|
| Cloud backend | `confidential` + marker + `force_args`, checked before every subprocess | Mechanical — verifiable and covered by tests |
| Maximum-quality mode | An instruction the assistant follows: announce, confirm, never on a confidential vault | Convention — not enforceable by code |

The second route exists because Claude Code can read a source itself rather than calling a local script. No subprocess is involved, so the dispatcher cannot see it. That asymmetry is exactly why the backend route got a mechanical lock: configuration can be checked, behaviour cannot.

## What could still go wrong

- If a vault is copied somewhere new without both its config and its marker, the copy is no longer recognisable as confidential. The dispatcher refuses to run there, but the content sits unprotected.
- `force_args` assumes the backend lets command-line flags win over its own configuration files. True for olw; worth smoke-testing for any new backend.
- Cloud sync typically does not preserve unix permission bits, so a restored `.confidential` may no longer be mode 600. The guardrail checks presence, not permissions, so this weakens defence in depth without breaking the guarantee.

Run `python3 .claude/migrate-wiki-backend.py <vault> --verify` to check that config, marker, and permissions still line up.
