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
| Claude Code — `--hd` mode | ⚠️ Partially | Only on explicit `--hd` request: prompt and source content go to Anthropic API (Claude Sonnet 4.6) |

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

> **Conclusion:** in the default mode, no paper content, transcript, or wiki text leaves the Mac mini. Claude Code orchestrates the workflow (instructions go to Anthropic) and hosts the human `olw review` gate, but all generative work runs locally via mistral-small:22b. Only when you explicitly request `--hd` does source content go to the Anthropic API — Claude Code always asks for confirmation first.
