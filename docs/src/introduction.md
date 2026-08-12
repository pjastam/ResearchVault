# Local Research Workflow

A privacy-first workflow for processing documents, videos, podcasts, and RSS feeds with local AI. Designed for a Mac with Apple Silicon; no cloud storage for your research data.

**Estimated installation time:** 60–120 minutes
**Requirements:** macOS Sequoia or later, internet connection for downloads, an Anthropic account (for Claude Code)

---

## The 3-phase model

Every source — paper, podcast, video, RSS article — passes through three explicit phases:

| Phase | Goal | How |
|---|---|---|
| **1 — Cast wide** | Capture everything relevant | Items flow into Zotero `_inbox` from three sources: (1) the feedreader (`feedreader-score.py`) scores RSS/YouTube/podcast feeds daily and produces a sorted HTML reader and Atom feed; (2) items shared directly via the iOS share sheet; (3) manual additions from desktop/email/notes |
| **2 — Filter** | You decide what enters the vault | `index-score.py` ranks inbox items by semantic similarity to your library; `summarize_item.py` (using the qwen3.5:9b fallback model) generates a Phase-2 preview for mid-range items; you give a **Go** or **No-go** |
| **3 — Process** | Approved items become a canonical bundle | On **Go**, `build-zotero-bundle.py` assembles a canonical bundle at `raw/{citekey}__{itemKey}.md` — verbatim metadata, notes, annotations, and full text. That bundle is the intake artifact, and it is where Phase 3 ends |

Turning bundles into a wiki is handled by whichever backend is configured for the vault — see [Choosing a backend](backends/choosing.md).

The separation between phases 1 and 3 keeps both your feed reader and your vault clean: only sources you have consciously approved end up in the vault.

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
| [Claude Code](https://claude.ai/claude-code) | AI assistant that orchestrates the workflow; generative work runs through your configured backend | Depends on backend + assistant mode — see [Privacy overview](reference/privacy.md) |

With the default `olw` backend, only orchestration instructions are sent to the Anthropic API; all generative work is handled locally by mistral-small:22b (with qwen3.5:9b as a fallback for Phase-2 previews). A vault can instead be configured with a cloud backend, which sends bundle content to that provider's API — see the [privacy overview](reference/privacy.md). Separately, for a single step you can ask Claude Code for maximum quality; this is a mode of the assistant, not a command-line flag — none of the scripts accept `--hd`. Claude then reads the source itself and sends it to the Anthropic API (Claude Sonnet 4.6) only after you confirm, and never on a vault marked confidential. Reference data, notes, and transcriptions always stay local unless a cloud backend is configured.

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
12. RSS integration + feedreader filtering (NetNewsWire + feedreader-score.py)
13. Set up filter layer per source
