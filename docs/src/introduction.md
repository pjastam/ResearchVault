# Local Research Workflow

A privacy-first workflow for processing documents, videos, podcasts, and RSS feeds with local AI. Designed for a Mac with Apple Silicon; no cloud storage for your research data.

**Estimated installation time:** 60–120 minutes
**Requirements:** macOS Sequoia or later, internet connection for downloads, an Anthropic account (for Claude Code)

---

## The 3-phase model

Every source — paper, podcast, video, RSS article — passes through three explicit phases:

| Phase | Goal | How |
|---|---|---|
| **1 — Cast wide** | Capture everything, no filtering yet | All sources flow into a single Zotero `_inbox` collection via browser extension, iOS app, or RSS reader |
| **2 — Filter** | You decide what enters the vault | `index-score.py` ranks inbox items by semantic similarity to your library; Qwen3.5:9b (local) generates a summary for mid-range items; you give a **Go** or **No-go** |
| **3 — Process** | Full processing of approved items | Claude Code writes a structured literature note to the Obsidian vault, including key findings, methodology notes, relevant quotes, and flashcards for spaced repetition |

The separation between phases 1 and 3 keeps the vault clean: only sources you have consciously approved end up there.

---

## Tools required

| Tool | Role | Local / Cloud |
|---|---|---|
| [Zotero](https://www.zotero.org) | Reference manager and central inbox | Local |
| [Zotero MCP](https://github.com/zotero-mcp) | Connects Claude Code to your Zotero library via local API | Local |
| [Obsidian](https://obsidian.md) | Markdown-based note-taking and knowledge base | Local |
| [Ollama](https://ollama.ai) | Local language model for offline tasks | Local |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Download YouTube transcripts and podcast audio | Local |
| [whisper.cpp](https://github.com/ggerganov/whisper.cpp) | Local speech-to-text transcription for podcasts | Local |
| [NetNewsWire](https://netnewswire.com) | RSS reader for academic and non-academic feeds | Local |
| [Claude Code](https://claude.ai/claude-code) | AI assistant that orchestrates the workflow; generative work runs locally via Qwen3.5:9b (Ollama) | Local (default) / Cloud API with `--hd` |

In standard mode, only orchestration instructions are sent to the Anthropic API; all generative work is handled locally by Qwen3.5:9b. Only when `--hd` is explicitly requested do the prompt and source content go to the Anthropic API (Claude Sonnet 4.6). Reference data, notes, and transcriptions always stay local.

---

## Overview of steps

1. Install Homebrew (package manager)
2. Install and configure Zotero 7 **(including `_inbox` collection)**
3. Set up Python environment
4. Install and configure Zotero MCP
5. Install Claude Code
6. Install Ollama (local language model)
7. Install Obsidian and create vault
8. Connect everything: configure Claude Code with MCP
9. Run first test
10. Optional extensions (yt-dlp, semantic search, automatic updates)
11. Podcast integration (whisper.cpp)
12. RSS integration (Zotero feeds + NetNewsWire)
13. Spaced repetition (Obsidian plugin)
14. Set up filter layer per source
