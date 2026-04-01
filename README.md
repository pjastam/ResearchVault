# ResearchVault

A privacy-first workflow for processing documents, videos, podcasts, and RSS feeds with local AI. Designed for a Mac with Apple Silicon; no cloud storage for your research data.

---

## The 3-phase model

Every source — paper, podcast, video, RSS article — passes through three explicit phases:

| Phase | Goal | How |
|---|---|---|
| **1 — Cast wide** | Capture from three sources into Zotero `_inbox` | **Feedreader** — `feedreader-score.py` runs daily, scores RSS/YouTube/podcast items by semantic similarity to your library, and produces a filtered HTML reader and Atom feed at `http://localhost:8765/filtered.html`; interesting items go to `_inbox` via browser extension or iOS app · **Share sheet** — content you've already consumed in apps (browser, YouTube, podcasts) goes directly to `_inbox` via the iOS share sheet · **Other** — documents, emails, and notes added manually |
| **2 — Filter** | You decide what enters the vault | `index-score.py` ranks inbox items by semantic similarity to your existing library; Qwen3.5:9b (local) generates a 2–3 sentence summary per item; you give a **Go** or **No-go** |
| **3 — Process** | Full processing of approved items | Qwen3.5:9b (local) writes a structured literature note to the Obsidian vault including key findings, methodology notes, relevant quotes, and flashcards for spaced repetition

The explicit filter step between capture and processing keeps both your feed reader and your vault clean: only sources you have consciously approved end up in the vault, and your feed reader only shows items that are likely relevant.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/architecture-diagram-v1.13-dark.svg">
  <img src="assets/architecture-diagram-v1.13-light.svg" alt="Architecture diagram">
</picture>

---

## Tools required

| Tool | Role | Local / Cloud |
|---|---|---|
| [Zotero](https://www.zotero.org) | Reference manager and central inbox | Local |
| [Zotero MCP](https://github.com/zotero-mcp) | Connects Claude Code to your Zotero library via local API | Local |
| [Obsidian](https://obsidian.md) | Markdown-based note-taking and knowledge base | Local |
| [Ollama](https://ollama.ai) | Local language model for offline tasks | Local |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Download YouTube transcripts and podcast audio | Local |
| [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api) | Fast transcript fetching for feedreader YouTube scoring (no video download) | Local |
| [whisper.cpp](https://github.com/ggerganov/whisper.cpp) | Local speech-to-text transcription for podcasts | Local |
| [NetNewsWire](https://netnewswire.com) | RSS reader subscribed to the feedreader filtered feed | Local |
| [Claude Code](https://claude.ai/claude-code) | AI assistant that orchestrates the workflow; generative work runs locally via Qwen3.5:9b (Ollama) | Local (default) / Cloud API with `--hd` |

In standard mode, only orchestration instructions are sent to the Anthropic API; all generative work is handled locally by Qwen3.5:9b. Only when `--hd` is explicitly requested do the prompt and source content go to the Anthropic API (Claude Sonnet 4.6). Reference data, notes, and transcriptions always stay local.

---

## Vault structure

```
ResearchVault/
├── literature/       # One note per approved source
├── syntheses/        # Thematic syntheses across multiple sources
├── projects/         # Project-specific documentation
├── daily/            # Daily notes and log
├── inbox/            # Raw input awaiting processing
├── CLAUDE.md         # Workflow instructions for Claude Code
└── .claude/
    ├── index-score.py          # Relevance scoring for _inbox items (phase 2)
    ├── fetch-fulltext.py       # Fetch Zotero attachment text to a local file (no content returned)
    ├── ollama-generate.py      # Call Ollama REST API and write output to file
    ├── zotero-inbox.py         # List all items in Zotero _inbox (human-readable or JSON)
    ├── feedreader-score.py     # RSS feed scoring and filtered feed generation (feedreader)
    ├── feedreader_core.py      # Shared scoring functions (cosine similarity, profile, source type detection)
    ├── feedreader-server.py    # Local HTTP server (port 8765) + POST /skip + GET /article/{video_id}
    ├── feedreader-learn.py     # Learning loop: processes skip queue + threshold calibration
    ├── feedreader-list.txt     # List of RSS feed URLs (web, YouTube, podcast)
    ├── score_log.jsonl         # Running log of scored feed items (incl. source_type, skipped flag)
    ├── skip_queue.jsonl        # Queue of explicitly rejected items (👎); processed daily
    ├── transcript_cache/       # Transcript & show-notes cache (YouTube: {video_id}.json; podcast: podcast_{episode_id}.json)
    ├── article_cache/          # Generated article cache (YouTube: {video_id}.html; podcast: podcast_{episode_id}.html)
    └── skills/
        ├── research-workflow-skill-v1.17.md  # Workflow skill (loaded each session)
        └── process_item.py                   # Privacy-preserving subagent: item key + metadata → literature note
```

---

## Daily use (summary)

**The feedreader runs automatically** — `feedreader-score.py` is triggered daily at 06:00 by a launchd agent, scores all feeds in `feedreader-list.txt`, and updates the filtered feed at `http://localhost:8765/filtered.html`. No manual action required.

**Your daily session:**

1. Browse the filtered feed at `http://localhost:8765/filtered.html` (or in NetNewsWire via `http://localhost:8765/filtered.xml`). Items are sorted by relevance score; interesting ones go to Zotero `_inbox` via the browser extension or iOS app.
2. Start Zotero (so the local API is active).
3. Open Terminal, navigate to your vault, and start Claude Code:
   ```bash
   cd ~/Documents/ResearchVault
   claude
   ```
4. Activate the research workflow:
   ```
   /research
   ```
   or just type: `start research workflow`
5. Optionally, run `index-score.py` first to prioritize your review:
   ```bash
   ~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/index-score.py
   ```
   This ranks all `_inbox` items by semantic similarity to your existing library (using the ChromaDB embeddings from zotero-mcp), so you know which items to focus on.
6. Claude Code retrieves all items from your Zotero `_inbox` and presents each one with a short summary and relevance assessment — the summary is generated locally by Qwen3.5:9b. You respond **Go** or **No-go** per item.
7. For each **Go**: Claude Code moves the item to the correct Zotero collection and writes a structured literature note in `literature/`.
8. For each **No-go**: Claude Code removes the item from `_inbox` (after your confirmation).
9. At the end of the session, Claude Code shows a summary: X approved, Y removed. If new papers were added, update the semantic search database. Use the quick version for metadata only, or the recommended full version for much better search results (5–20 min on Apple Silicon):
   ```bash
   zotero-mcp update-db            # quick (metadata only)
   zotero-mcp update-db --fulltext # recommended (includes full text)
   ```
   Or use the alias: `update-zotero` (equivalent to `--fulltext`). Check database status with `zotero-mcp db-status`.

---

## Getting started

Full step-by-step instructions covering all tools, configuration, and the first test run are published interactively at **[pjastam.github.io/ResearchVault](https://pjastam.github.io/ResearchVault/)**. A single-file download is also available: [installation-guide-v1.12.md](docs/installation-guide-v1.12.md).

To configure Claude Code's permission settings for this vault, run the setup script from your vault directory:

```bash
./setup.sh
```

The script auto-detects your home path and asks for your Zotero library ID (found via `zotero-mcp setup-info`).

---

## Privacy

- Your Zotero library and Obsidian vault stay entirely on your own machine
- The Zotero local API is only accessible via `localhost`
- Transcription (whisper.cpp) and local model inference (Ollama) run fully offline
- In standard mode, only orchestration instructions reach the Anthropic API; source content stays local
- With `--hd`, the prompt and source content are sent to the Anthropic API (Claude Sonnet 4.6)
- For a fully local orchestration alternative, see [Step 15: Future perspective — local orchestrator](https://pjastam.github.io/ResearchVault/extensions/future-orchestrator.html)

---

## Frequently asked questions

1. Does content go to the cloud?

In the default mode: no. Claude Code orchestrates the workflow, but all content-heavy work is delegated to `process_item.py` — a local subagent that receives only a Zotero item key and metadata (title, authors, year, tags). The subagent fetches the full text locally, generates the literature note via Qwen3.5:9b (Ollama), and writes the `.md` file to `literature/`. Claude Code receives only a JSON status object: `{"status": "ok", "path": "literature/..."}`. No source content ever reaches Anthropic's servers. Only when you explicitly add `--hd` does source content go to the Anthropic API — and Claude Code asks for confirmation first.

2. Do you need a paid Claude subscription?

Partially yes — Claude Code needs an Anthropic account (paid subscription or API credits) for its orchestration role. But the AI that actually reads and processes your research is Ollama + Qwen3.5:9b, which is completely free and open source. So the heavy lifting costs nothing.

3. "No data leaks" — is that accurate?

Yes, substantially. In default mode no vault content, paper, transcript, or note leaves your local machine. The privacy claim holds up in this sense.

---

## License

MIT — feel free to adapt this workflow for your own research setup.
