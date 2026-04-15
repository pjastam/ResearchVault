# Using the workflow

This section describes how to use the research workflow day to day, assuming everything has been installed (see the Installation and Extensions sections).

The workflow has three phases. Phase 3 is handled by tooling; phases 1 and 2 involve you.

| Phase | What happens | Your role |
|---|---|---|
| **1 — Cast wide** | Items flow into Zotero `_inbox` from three sources | Forward items from the feedreader or share directly from iOS |
| **2 — Filter** | Claude Code presents each `_inbox` item with a relevance score and summary; you decide | Go / No-go per item |
| **3 — Process** | Claude Code writes a structured literature note to the Obsidian vault | Review the generated note |

---

## Three sources into Zotero `_inbox` (Phase 1)

All items that enter the workflow pass through Zotero `_inbox` first. They arrive from three distinct sources:

| Source | What it is | Filtering before `_inbox` | Phase 2 treatment |
|---|---|---|---|
| **1. Feedreader** | Aggregated RSS/YouTube/podcast feeds scored daily by `feedreader-score.py`; you browse the HTML reader or NetNewsWire and forward interesting items | Partly autonomous (scoring algorithm), partly manual (your click) | Standard Go/No-go |
| **2. iOS share sheet** | Items you share directly from YouTube, Overcast, Safari, or NetNewsWire | Done by you — you consumed or deliberately selected the item | Lighter: you already pre-filtered |
| **3. Desktop / email / notes** | Manual additions from any other source | None — comparable to source 1 | Standard Go/No-go |

**Key distinction:** items from source 2 arrive after you have already read, watched, or listened to them (or deliberately chosen them in NetNewsWire). The Phase 2 Go/No-go step is therefore lighter for these items. Items from sources 1 and 3 still need a full Phase 2 review.

**One nuance for source 2:** if you click an item in the feedreader HTML reader and then share it to Zotero via iOS — without having read it fully — it still needs proper reading before a Go in Phase 2. The share action is not always a signal that the content has been consumed.

---

## Current state: calibration mode

The feedreader is in **calibration mode** until its scoring threshold is stable. During this phase:

- The feedreader runs automatically but does **not** yet route items to Zotero `_inbox` on its own.
- You browse the HTML reader daily and give feedback signals: click on interesting items (and add them to Zotero) for positive signals, press 👎 on irrelevant items for explicit negative signals.
- `feedreader-learn.py` processes these signals every morning as part of the nightly batch job (06:00).
- Once **≥30 positive signals** have accumulated, `feedreader-learn.py` will recommend an initial threshold.

---

## Future state: autonomous mode

Once the threshold is set, the feedreader will route items above the threshold **automatically to Zotero `_inbox`** without any action from you. The HTML reader stays available as a transparency window and as an ongoing calibration channel — occasional browsing in NetNewsWire and sharing items to Zotero continues to refine the threshold over time.

See [Roadmap](roadmap.md) for the remaining steps.
