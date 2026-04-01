# Roadmap

The workflow is production-ready and in daily use, but several planned improvements remain. This page describes what has been done and what is still coming.

---

## Completed

### Inline snippets in the HTML reader ✅

The HTML reader now shows a short text excerpt below each item title (max. 2 lines). For web articles and podcasts this comes from the RSS description or show notes. For YouTube videos it comes from the video description, with a fallback to the opening lines of the cached transcript for channels that provide no meaningful description.

This replaced an earlier design where clicking a YouTube or podcast headline generated a full reading article via Ollama (`qwen2.5:7b`). That approach placed article generation in Phase 0, where it does not belong: Phase 0 is for filtering, not for deep reading. All headlines now link directly to the original source URL. The article generation routes in `phase0-server.py` remain available but are no longer linked from the main reader.

---

## In progress

### Threshold calibration (Step 2)

Phase 0 is learning your preferences by observing which items you add to Zotero (positive signal) and which items you explicitly reject with 👎 (negative signal).

**Current requirement:** ≥30 positive signals before `phase0-learn.py` can produce a reliable threshold recommendation.

**How to contribute signals:**
- Browse the HTML reader daily
- Click on interesting items and add them to Zotero `_inbox`
- Press 👎 on clearly irrelevant items — even when just the headline makes it obvious

`phase0-learn.py` runs automatically at 06:15 every morning. Run it manually for a progress report:

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/phase0-learn.py
```

Once ≥30 positives are reached, it will print a threshold recommendation. Apply it in `.claude/phase0-score.py`:

```python
THRESHOLD_GREEN  = ...   # from the recommendation
THRESHOLD_YELLOW = ...   # from the recommendation
```

---

## Planned

### Autonomous mode (Step 3) — after calibration

Once the threshold is stable, Phase 0 will route items above the threshold **automatically to Zotero `_inbox`** via the Zotero web API — without any action from you.

This changes the daily rhythm:
- **Now:** browse HTML reader → manually forward interesting items → Phase 2
- **After:** Phase 0 fills `_inbox` autonomously → you only interact during Phase 2 and 3

The HTML reader stays available as a transparency window: you can check at any time what was routed and why. The 👎 button continues to work as a correction mechanism.

### Skill update (Step 4) — after Step 3

The research workflow skill (`research-workflow-skill-v1.16.md`) will be updated to reflect the three-sources model:

| Source | Filtering | Phase 2 needed? |
|---|---|---|
| Phase 0 (autonomous) | Algorithm | Yes |
| iOS share sheet | You | Minimal |
| Desktop / email / notes | Manual | Yes |

The current skill describes Phase 1 as "the user scans the filtered feed." This will be updated to reflect that, in autonomous mode, Phase 1 is fully automatic for RSS content.

### NetNewsWire integration test (Step 5, optional)

Subscribe `filtered.xml` in NetNewsWire on iOS and evaluate whether the score labels (🟢🟡🔴) and titles are readable. If successful, NetNewsWire becomes an additional calibration channel: sharing an item from NetNewsWire to Zotero via the iOS share sheet behaves like source (2) — a deliberate user choice — and generates clean positive signals without needing to open the HTML reader.

---

## Longer-term perspective

### Local orchestrator

The only component in this stack that does not run fully locally is Claude Code as orchestrator. All generation tasks (summaries, notes, syntheses, flashcards) already run via Qwen3.5:9b on Ollama — fully local, fully private. What goes through the Anthropic API are the workflow instructions: intake, phase monitoring, vault conventions, and the iterative Go/No-go dialogue.

Two serious candidates exist for replacing this layer with a local model:

**Open WebUI + MCPO** — a self-hosted browser interface that connects to Ollama and can call MCP servers (including zotero-mcp) via the MCPO proxy. Mature interface, actively maintained, works on macOS without Docker.

**ollmcp** — a terminal interface (TUI) that connects Ollama models to multiple MCP servers simultaneously, with an agent mode and human-in-the-loop controls. Closer to how Claude Code works today.

Neither is yet a full replacement. The orchestration layer that Claude Code provides involves multi-phase session awareness, vault conventions, and reliable instruction-following across many rounds and tools. Local models (Qwen3.5:9b included) are noticeably less consistent in this role — not due to language capability, but due to reliability across complex multi-step workflows. The skill logic and CLAUDE.md conventions would need to be fully rebuilt as a system prompt, and the result would be less robust.

This is worth revisiting as local models improve. The landscape is changing fast — Open WebUI and ollmcp are both in active development.
