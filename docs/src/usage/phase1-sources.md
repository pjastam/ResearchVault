# Phase 1: sources into Zotero _inbox

Phase 1 is the collection step. Items from three sources flow into Zotero `_inbox`. The feedreader handles source 1 automatically; sources 2 and 3 are always manual.

---

## Source 1: the feedreader

`feedreader-score.py` runs daily at 06:00 via launchd. It fetches all feeds from `feedreader-list.txt`, scores each item by semantic similarity to your Zotero library, and produces:

- **HTML reader** (Mac, iPhone, iPad): `http://localhost:8765/filtered.html`
- **Atom feed** (NetNewsWire): `http://localhost:8765/filtered.xml`

### Reading the item list

Each item shows:

- **Score badge** — relevance score 0–100, colour-coded: 🟢 ≥50 · 🟡 40–49 · 🔴 <40
- **Title** — links to the original source
- **Source and date** — feed name and publication date
- **Snippet** — short text excerpt (2 lines max): first meaningful prose from the description or show notes; for YouTube, from the video description or — if that contains only links — the opening lines of the cached transcript

**Type filters** in the header: Alles / 📄 web / ▶️ YouTube / 🎙️ podcast. Three sort views: **Op score** (default), **Op bron**, **Op datum**.

### Forwarding to Zotero _inbox

When a headline is interesting, click it (marks as read) and save to Zotero `_inbox` via the browser extension or iOS app. This is the phase 1 action for source 1.

### Giving feedback: calibrating the feedreader

The feedreader learns from your behaviour. Two types of signal matter:

| Behaviour | Signal | Recorded as |
|---|---|---|
| Clicked + added to Zotero | Strong positive | `added_to_zotero: true` |
| Clicked, not added | Weak negative | `added_to_zotero: false` after 3 days |
| Not clicked, no 👎 | Ambiguous | `added_to_zotero: false` after 3 days |
| 👎 without clicking | Strong explicit negative | `skipped: true` immediately |
| Clicked, then 👎 | Strongest negative | `skipped: true` + `added_to_zotero: false` |

**Use 👎 liberally** on off-topic headlines. Unclicked items are ambiguous — they could mean "not seen" just as easily as "not interesting." Only 👎 signals are unambiguous rejections.

`feedreader-learn.py` runs at 06:15 every morning and tracks signal quality. Run it manually for a progress report:

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/feedreader-learn.py
```

After ≥30 positive signals, it prints an initial threshold recommendation. Apply it in `.claude/feedreader-score.py`:

```python
THRESHOLD_GREEN  = ...   # from the recommendation
THRESHOLD_YELLOW = ...   # from the recommendation
```

**Learning is continuous.** After the initial threshold is set, every 👎 signal and every Zotero addition continues to refine the scoring. Occasional browsing in NetNewsWire and sharing items to Zotero remains useful even in autonomous mode.

### Hiding read and skipped items

Click **verberg gelezen / overgeslagen** in the header to hide processed items.

### In-browser terminal

The **⌨️ terminal** button opens an embedded ttyd terminal panel (port 7681) alongside the article list. Use it to start a Phase 2 session without switching apps:

```bash
cd ~/Documents/ResearchVault && claude
```

Then type `beoordeel inbox` to begin the Go/No-go review.

### NetNewsWire as an alternative reader

`filtered.xml` can be added as a single subscription in NetNewsWire on macOS or iOS. Titles are prefixed with score and label (`🟢 54 | Title…`). Sorting by **Newest First** equals sorting by relevance (the feedreader encodes scores as synthetic dates).

When you share an item from NetNewsWire to Zotero via the iOS share sheet, it behaves like **source 2** — a deliberate choice — and contributes a clean positive calibration signal.

---

## Source 2: iOS share sheet

Items you share directly from YouTube, Overcast, Safari, or NetNewsWire arrive in Zotero `_inbox` as deliberate choices. You have typically already consumed the content (watched the video, listened to the podcast, read the article) or you made a specific decision to save it.

**Phase 2 treatment is lighter** for these items: no summary needed for content you have already evaluated. Claude Code will recognise the context and ask only for a Go/No-go confirmation.

**One nuance:** if you clicked a feedreader headline and then shared it via the iOS share button without having read the full content, it is still source 1 in terms of depth — you will need to read/watch/listen before confirming Go in Phase 2.

Items from the iOS share sheet may carry a Zotero tag from the source app:
- **`✅`** — you marked it for processing; Phase 2 skips the Go/No-go and goes directly to Phase 3
- **`📖`** — you marked it as "read later"; Phase 2 asks only for Go/No-go confirmation

---

## Source 3: desktop / email / notes

Items added manually from email, a desktop browser, or notes follow the same path as source 1: they need a full Phase 2 review before entering the vault. Add them to Zotero `_inbox` via the Zotero browser extension or the desktop app, or pass a URL directly:

```
inbox [URL]
```

This fetches the article and saves it as Markdown in `inbox/` without going through Zotero.
