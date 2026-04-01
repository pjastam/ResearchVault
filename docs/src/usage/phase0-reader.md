# Phase 0: the HTML reader

The filtered feed is available at:

- **HTML reader** (Mac, iPhone, iPad): `http://localhost:8765/filtered.html`
- **Atom feed** (NetNewsWire): `http://localhost:8765/filtered.xml`

The HTML reader is the primary interface during the calibration phase. It shows all scored feed items sorted by relevance, with controls for filtering by type and view.

---

## Reading the item list

Each item shows:

- **Score badge** — relevance score 0–100, colour-coded: 🟢 ≥50 · 🟡 40–49 · 🔴 <40
- **Title** — links to the original source
- **Source and date** — feed name and publication date
- **Snippet** — short excerpt below the title (2 lines max):
  - Web articles: first prose from the article description
  - Podcasts: first prose from the show notes
  - YouTube: first prose from the video description, or — if the description contains only links — the opening lines of the video transcript

Items that have been read appear faded. Items marked with 👎 appear struck through.

---

## Type filters

The header contains four filter buttons:

| Button | Shows |
|---|---|
| Alles | All item types |
| 📄 | Web articles only |
| ▶️ | YouTube videos only |
| 🎙️ | Podcast episodes only |

Three sort views are also available: **Op score** (default), **Op bron** (grouped by feed), **Op datum** (chronological).

---

## Giving feedback

Feedback signals are the core input for calibrating Phase 0's scoring threshold.

### Positive signal: click + add to Zotero

When a headline is interesting:

1. Click the headline → the item opens in a new tab and is marked as read.
2. Save the item to Zotero `_inbox` via the browser extension or iOS app.

This is recorded as `added_to_zotero: true` in the score log — the strongest positive signal.

### Negative signal: 👎 button

When a headline is clearly off-topic, press the 👎 button directly — no need to open the item. The item is immediately struck through in the reader and queued in `skip_queue.jsonl`. `phase0-learn.py` processes this the next morning.

> **Use 👎 liberally during calibration.** Explicit negative signals are valuable because unclicked items are ambiguous — they could mean "not seen" just as easily as "not interesting".

### Signal quality overview

| Behaviour | Signal | How recorded |
|---|---|---|
| Clicked + added to Zotero | Strong positive | `added_to_zotero: true` |
| Clicked, not added to Zotero | Weak negative | `added_to_zotero: false` after 3 days |
| Not clicked, no 👎 | Ambiguous | `added_to_zotero: false` after 3 days |
| 👎 without clicking | Strong explicit negative | `skipped: true` immediately |
| Clicked, then 👎 | Strongest negative | `skipped: true` + `added_to_zotero: false` |

---

## Hiding read and skipped items

Click **verberg gelezen / overgeslagen** in the header to hide all items you have already processed. Click again to show everything.

---

## In-browser terminal

The **⌨️ terminal** button in the header opens an embedded terminal panel (ttyd, port 7681) alongside the article list. This lets you start a Claude Code session for Phase 2 without switching apps or tabs. The terminal works on Mac (`localhost`) and on iPad (via the Mac's local IP address).

To start a Phase 2 session from the terminal:

```bash
cd ~/Documents/ResearchVault && claude
```

Then type `beoordeel inbox` to begin the Go/No-go review.

---

## Calibration: adjusting the scoring threshold

`phase0-learn.py` runs automatically at 06:15 every day and produces a report of:

- ✅ positive signals (clicked + added to Zotero)
- 👎 explicit negative signals
- ❌ weak negatives (seen but not added after 3 days)

Run it manually at any time:

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/phase0-learn.py
```

After **≥30 positive signals**, the script produces a threshold recommendation. Apply it by editing two constants in `.claude/phase0-score.py`:

```python
THRESHOLD_GREEN  = 50   # adjust based on recommendation
THRESHOLD_YELLOW = 40   # adjust based on recommendation
```

Once the threshold is stable, Phase 0 can transition to autonomous mode. See [Roadmap](roadmap.md).

---

## NetNewsWire as an alternative reader

`filtered.xml` can be added as a single subscription in NetNewsWire on macOS or iOS. Titles are prefixed with score and label (`🟢 54 | Title…`). Phase 0 encodes the score as a synthetic publication date so sorting by **Newest First** equals sorting by relevance.

In NetNewsWire, saving an item via the share sheet to Zotero behaves like source (2) — you have actively selected the item, so it is treated as pre-filtered. This is an alternative calibration channel that works without opening the HTML reader.
