# Using the workflow

This section describes how to use the research workflow day to day, assuming everything has been installed (see the Installation and Extensions sections).

The workflow has four phases. Phases 0 and 3 are handled by tooling; phases 1 and 2 involve you.

| Phase | What happens | Your role |
|---|---|---|
| **0 — Pre-filter** | `phase0-score.py` scores all RSS items and produces a sorted HTML reader and Atom feed | None (runs automatically at 06:00 via launchd) |
| **1 — Cast wide** | Interesting items flow into Zotero `_inbox` | Forward items from the feed reader to Zotero |
| **2 — Filter** | Claude Code presents each `_inbox` item with a relevance score and summary; you decide | Go / No-go per item |
| **3 — Process** | Claude Code writes a structured literature note to the Obsidian vault | Review the generated note |

---

## Current state: calibration mode

Phase 0 is in **calibration mode** until its scoring threshold is stable. During this phase:

- Phase 0 runs automatically but does **not** yet route items to Zotero `_inbox` on its own.
- You browse the HTML reader daily and give feedback signals: click on interesting items (and add them to Zotero) for positive signals, press 👎 on irrelevant items for explicit negative signals.
- `phase0-learn.py` processes these signals every morning at 06:15 and tracks signal quality.
- Once **≥30 positive signals** have accumulated, `phase0-learn.py` will recommend a threshold. You then adjust `THRESHOLD_GREEN` and `THRESHOLD_YELLOW` in `phase0-score.py`.

After calibration, Phase 0 transitions to autonomous mode (see [Roadmap](roadmap.md)).

---

## Three input sources into Zotero `_inbox`

Items reach Zotero `_inbox` from three distinct sources. The key difference is whether filtering has already been done by you.

| Source | Filtering done by | Phase 2 needed? |
|---|---|---|
| **Phase 0** (RSS, calibration/autonomous) | Algorithm, then validated by you | Yes — algorithm may err |
| **iOS share sheet** (YouTube, podcast, web page) | You (you watched/listened and decided it is relevant) | Minimal — you already filtered |
| **Desktop / email / notes** | Manual, case by case | Yes — comparable to Phase 0 |

Items from the iOS share sheet are pre-filtered by the act of sharing: you saw the content and consciously chose to save it. The Go/No-go step in Phase 2 is therefore much lighter for these items.

---

## Future state: autonomous mode

Once the threshold is stable:

- Phase 0 **automatically routes** items above the threshold to Zotero `_inbox` without any action from you.
- The HTML reader stays available as a transparency window — you can check what was routed — but it is no longer the primary decision channel.
- Your active time is concentrated in Phase 2 (reviewing what landed in `_inbox`) and Phase 3 (processing approved items to the vault).

See [Roadmap](roadmap.md) for the remaining steps.
