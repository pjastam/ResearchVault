# ResearchVault

A local, privacy-first research workflow for academic researchers, built on **Claude Code**, **Zotero**, **Obsidian**, and **Ollama**. Designed for a Mac with Apple Silicon; no cloud storage for your research data.

---

## The 3-phase model

Every source — paper, podcast, video, RSS article — passes through three explicit phases:

| Phase | Goal | How |
|---|---|---|
| **1 — Cast wide** | Capture everything, no filtering yet | All sources flow into a single Zotero `_inbox` collection via browser extension, iOS app, or RSS reader |
| **2 — Filter** | You decide what enters the vault | Claude Code summarises each inbox item in 2–3 sentences; you give a **Go** or **No-go** |
| **3 — Process** | Full processing of approved items | Claude Code writes a structured literature note to the Obsidian vault, including key findings, methodology notes, relevant quotes, and flashcards for spaced repetition |

The separation between phases 1 and 3 keeps the vault clean: only sources you have consciously approved end up there.

---

## Tools required

| Tool | Role | Local / Cloud |
|---|---|---|
| [Zotero 7](https://www.zotero.org) | Reference manager and central inbox | Local |
| [Zotero MCP](https://github.com/zotero-mcp) | Connects Claude Code to your Zotero library via local API | Local |
| [Claude Code](https://claude.ai/claude-code) | AI assistant that runs the workflow | Cloud API (Anthropic) |
| [Obsidian](https://obsidian.md) | Markdown-based note-taking and knowledge base | Local |
| [Ollama](https://ollama.ai) | Local language model for offline tasks | Local |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Download YouTube transcripts and podcast audio | Local |
| [whisper.cpp](https://github.com/ggerganov/whisper.cpp) | Local speech-to-text transcription for podcasts | Local |
| [NetNewsWire](https://netnewswire.com) | RSS reader for academic and non-academic feeds | Local |

Only the Claude Code API call leaves your machine. All reference data, notes, and transcriptions stay local.

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
    └── skills/       # Research workflow skill loaded each session
```

---

## Daily use (summary)

1. Start Zotero
2. Open Terminal, navigate to your vault, and start Claude Code:
   ```bash
   cd ~/Documents/ResearchVault
   claude
   ```
3. Activate the research workflow:
   ```
   /research
   ```
   or just type: `start research workflow`
4. Claude Code retrieves all items from your Zotero `_inbox` and presents each one with a short summary and relevance assessment. You respond **Go** or **No-go** per item.
5. For each **Go**: Claude Code moves the item to the correct Zotero collection and writes a structured literature note in `literature/`.
6. For each **No-go**: Claude Code removes the item from `_inbox` (after your confirmation).
7. At the end of the session, Claude Code shows a summary: X approved, Y removed. If new papers were added, update the semantic search database:
   ```
   update database
   ```

---

## Getting started

See the [installation guide](installatiegids-lokale-research-workflow-v1.11.md) for full step-by-step instructions covering all tools, configuration, and the first test run.

> **Note:** The installation guide is currently written in Dutch. An English translation is planned.

For Claude Code configuration, copy `.claude/settings.local.json.template` to `.claude/settings.local.json` and replace the placeholder paths with your own.

---

## Privacy

- Your Zotero library and Obsidian vault stay entirely on your own machine
- The Zotero local API is only accessible via `localhost`
- Transcription (whisper.cpp) and local model inference (Ollama) run fully offline
- Only the text you send to Claude Code in a session is processed via the Anthropic API

---

## License

MIT — feel free to adapt this workflow for your own research setup.
