# Phase 1: sources into Zotero _inbox

Phase 1 is the collection step. Items from three sources flow into Zotero `_inbox`. The feedreader handles source 1 automatically; sources 2 and 3 are always manual.

---

## Source 1: the feedreader

`feedreader-score.py` runs daily via launchd. It fetches all feeds from `feedreader-list.txt`, scores each item by semantic similarity to your Zotero library, and produces:

- **HTML reader** (Mac, iPhone, iPad): `http://localhost:8765/filtered.html`
- **Atom feeds** (NetNewsWire): `http://[mac-ip]:8765/filtered-webpage.xml` · `filtered-youtube.xml` · `filtered-podcast.xml`

Transient network errors are common enough to matter: a feed that cannot be fetched is retried once, under a 15-second per-feed timeout so that one unresponsive server cannot stall the whole run. Feeds that stay unreachable are listed explicitly at the end of the fetch step, so a silently missing source shows up in the run output instead of looking like a feed that simply had nothing new.

Each item is shown once. That is less trivial than it sounds, because a link is a location, not an identity: PubMed appends a fresh `ff=<timestamp>` to every link on every fetch, so the same article arrived under a new URL each run and NetNewsWire kept showing it again. Items are therefore matched on a stable key — the RSS `<guid>` where the feed provides one, otherwise the link with tracking parameters stripped — both against earlier runs and within the current one, the latter catching a publication that appears in the PURE feeds of two co-authors. The reverse failure is guarded too: podcast feeds that give the show homepage as the link for every episode fall back to the guid alone, so episode 2 is not mistaken for a repeat of episode 1. The run output reports both counts (`Ontdubbeld: N al eerder gezien, M dubbel binnen deze run`).

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

"Added to Zotero" is detected two ways, by URL and by title. The URL half was silently broken until 16 August 2026: it queried the Zotero table that holds file paths rather than the one that holds URLs, so it always came back empty. Title matching covered for it, which is precisely why it went unnoticed — a dead signal propped up by its neighbour looks exactly like a quiet day. The counts are now compared on a normalised URL, so the link Zotero recorded after redirects still matches the one the feedreader read from the RSS. Threshold statistics count each article once rather than each log line, so an article that arrived repeatedly cannot outweigh the rest.

`feedreader-learn.py` runs as the last step of the morning batch (triggered by your login) and again at 09:00, 12:00, 15:00, 18:00 and 21:00, and tracks signal quality. Run it manually for a progress report:

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/feedreader-learn.py
```

After ≥30 positive signals, it prints an initial threshold recommendation. The recommendation is computed from the **positive** signals alone — percentiles over their scores. The negative and 👎 counts are printed beside it for inspection, but nothing in the calculation reads them. That is also why the two negative classes are pooled without weighting: their difference in evidential strength does not yet have anywhere to act. Apply the recommendation in `.claude/feedreader-score.py`:

```python
THRESHOLD_GREEN  = ...   # from the recommendation
THRESHOLD_YELLOW = ...   # from the recommendation
```

**Learning is continuous.** After the initial threshold is set, every Zotero addition keeps reshaping the recommendation as the positives accumulate — and it also enters the preference profile the scorer builds from your library, so adding a paper changes how the next batch is scored. 👎 signals do neither yet: they are recorded in `skip_queue.jsonl`, labelled in the log and reported in the summary, but no calculation reads them. Keep giving them anyway — they are the only unambiguous rejections on record, and they are what negative weighting will be built on. Occasional browsing in NetNewsWire and sharing items to Zotero remains useful even in autonomous mode.

### Hiding read and skipped items

Click **verberg gelezen / overgeslagen** in the header to hide processed items.

### In-browser terminal

The **⌨️ terminal** button opens an embedded ttyd terminal panel (port 7681) alongside the article list. Use it to start a Phase 2 session without switching apps:

```bash
cd ~/Documents/ResearchVault && claude
```

Then type `beoordeel inbox` to begin the Go/No-go review.

### NetNewsWire as an alternative reader

The three type-specific feeds can be subscribed to in NetNewsWire on macOS or iOS. Titles are prefixed with score and label (`🟢 54 | Title…`). Sorting by **Newest First** equals sorting by relevance (the feedreader encodes scores as synthetic dates).

Each article in NNW shows one action button (requires JavaScript enabled in NNW Article Content settings):
- **👎 Overslaan** — sends a negative signal to the learning loop

Pressing 👎 fades the item and writes the URL to `skip_queue.jsonl`; `feedreader-learn.py` processes it the next morning. To send items to Zotero `_inbox`, use the Zotero browser extension or iOS app instead.

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

Items added manually from email, a desktop browser, or notes follow the same path as source 1: they need a full Phase 2 review before entering the vault. Add them to Zotero `_inbox` via the Zotero browser extension or the desktop app.
