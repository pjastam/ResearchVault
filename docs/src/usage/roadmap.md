# Roadmap

The workflow is production-ready and in daily use, but several planned improvements remain. This page describes what has been done and what is still coming.

---

## Completed

### Rename: phase0-* → feedreader-* ✅

All scripts, configuration files, launchd agents, and internal references renamed. "Phase 0" was not a separate phase in the workflow but the automatic filtering function within Phase 1. The name `feedreader` better reflects the function: scoring, filtering, and serving RSS/YouTube/podcast feeds.

### Inline snippets in the HTML reader ✅

The HTML reader now shows a short text excerpt below each item title (max. 2 lines). For web articles and podcasts this comes from the RSS description or show notes. For YouTube videos it comes from the video description, with a fallback to the opening lines of the cached transcript for channels that provide no meaningful description.

This replaced an earlier design where clicking a YouTube or podcast headline generated a full reading article via Ollama (`qwen2.5:7b`). That approach placed article generation in the wrong part of the workflow: the HTML reader is for filtering, not for deep reading. All headlines now link directly to the original source URL.

---

## In progress

### Threshold calibration

The feedreader is learning your preferences by observing which items you add to Zotero (positive signal) and which items you explicitly reject with 👎 (negative signal).

**Current requirement:** ≥30 positive signals before `feedreader-learn.py` can produce a reliable initial threshold recommendation.

**How to contribute signals:**
- Browse the HTML reader daily
- Click on interesting items and add them to Zotero `_inbox`
- Press 👎 on clearly irrelevant items

`feedreader-learn.py` runs automatically at 06:15 every morning. Run it manually for a progress report:

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/feedreader-learn.py
```

Once ≥30 positives are reached, it will print a threshold recommendation. Apply it in `.claude/feedreader-score.py`:

```python
THRESHOLD_GREEN  = ...   # from the recommendation
THRESHOLD_YELLOW = ...   # from the recommendation
```

**Learning is continuous.** After the initial threshold is set, every 👎 signal and every Zotero addition continues to refine the scoring. There is no endpoint — the feedreader keeps improving as long as you interact with it.

---

## Planned

### Autonomous mode — after initial threshold is set

Once the threshold is configured, the feedreader will route items above the threshold **automatically to Zotero `_inbox`** via the Zotero web API — without any action from you.

This changes the daily rhythm:
- **Now:** browse HTML reader → manually forward interesting items → Phase 2
- **After:** feedreader fills `_inbox` autonomously → you interact mainly in Phase 2 and 3

The HTML reader stays available as a transparency window and as an ongoing calibration channel. The 👎 button continues to work as a correction mechanism. Occasional browsing in NetNewsWire and sharing items to Zotero remains useful for keeping the scoring calibrated over time.

### Skill update — after autonomous mode

The research workflow skill (`SKILL.md`) will be updated to reflect the fully autonomous feedreader as the default state for source 1, and to document the three-source model more precisely in the daily workflow description.

### NetNewsWire integration (ongoing, optional)

The three type-specific Atom feeds (`filtered-webpage.xml`, `filtered-youtube.xml`, `filtered-podcast.xml`) are available in NetNewsWire on macOS and iOS. The **👎** button in the NNW article view sends an explicit negative signal to the skip queue, making NetNewsWire a permanent optional calibration channel. Items you want to save go to Zotero via the browser extension or iOS app.

---

## Longer-term perspective

### Local orchestrator

The only component in this stack that does not run fully locally is Claude Code as orchestrator. All generation tasks (summaries, notes, syntheses, flashcards) already run via Qwen3.5:9b on Ollama — fully local, fully private. What goes through the Anthropic API are the workflow instructions: intake, phase monitoring, vault conventions, and the iterative Go/No-go dialogue.

Two serious candidates exist for replacing this layer with a local model:

**Open WebUI + MCPO** — a self-hosted browser interface that connects to Ollama and can call MCP servers (including zotero-mcp) via the MCPO proxy. Mature interface, actively maintained, works on macOS without Docker.

**ollmcp** — a terminal interface (TUI) that connects Ollama models to multiple MCP servers simultaneously, with an agent mode and human-in-the-loop controls. Closer to how Claude Code works today.

Neither is yet a full replacement. The orchestration layer that Claude Code provides involves multi-phase session awareness, vault conventions, and reliable instruction-following across many rounds and tools. The landscape is changing fast and worth continuing to follow.
