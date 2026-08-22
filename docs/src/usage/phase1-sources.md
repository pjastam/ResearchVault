# Phase 1: sources into Zotero _inbox

Phase 1 is the collection step. Items from three sources flow into Zotero `_inbox`. The feedreader handles source 1 automatically; sources 2 and 3 are always manual.

---

## Source 1: the feedreader

`feedreader-score.py` runs daily via launchd. It fetches all feeds from `feedreader-list.txt`, scores each item by semantic similarity to your Zotero library, and produces:

- **Atom feeds** (NetNewsWire, via FreshRSS): `http://[mac-ip]:8765/filtered-webpage.xml` · `filtered-youtube.xml` · `filtered-podcast.xml`

(The standalone HTML reader at `/filtered.html` was removed on 18 April 2026; NetNewsWire and FreshRSS took over the reading layer. The URL survives only as the channel home `<link>` inside the Atom feeds, because FreshRSS stores no `htmlUrl` without it.)

Transient network errors are common enough to matter: a feed that cannot be fetched is retried once, under a 15-second per-feed timeout so that one unresponsive server cannot stall the whole run. Feeds that stay unreachable are listed explicitly at the end of the fetch step, so a silently missing source shows up in the run output instead of looking like a feed that simply had nothing new.

Each item is shown once. That is less trivial than it sounds, because a link is a location, not an identity: PubMed appends a fresh `ff=<timestamp>` to every link on every fetch, so the same article arrived under a new URL each run and NetNewsWire kept showing it again. Items are therefore matched on a stable key — the RSS `<guid>` where the feed provides one, otherwise the link with tracking parameters stripped — both against earlier runs and within the current one, the latter catching a publication that appears in the PURE feeds of two co-authors. The reverse failure is guarded too: podcast feeds that give the show homepage as the link for every episode fall back to the guid alone, so episode 2 is not mistaken for a repeat of episode 1. The run output reports both counts (`Ontdubbeld: N al eerder gezien, M dubbel binnen deze run`).

One caveat when editing `feedreader-list.txt`: the list is not de-duplicated. A feed listed twice is fetched twice per run, and — less obviously — the de-duplication key is `(feed URL, canonical link)`, so every episode is counted twice within what looks like the same feed. That trips the show-homepage fallback described above, and the items silently drop back to guid-only identity. Measured on 22 August 2026: the AI Report feed appeared under two category headings, and all 135 of its log lines carried a guid identity, never a URL form. The headings are comments only — source type is derived from the feed URL and the entry's enclosures — so a feed needs exactly one line, in whichever section fits.

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

**👎 is a hard stop.** A rejection blocks every later signal in the loop, including a star you set by hand — it is the only unambiguous judgement in the chain, so nothing derived may override it. This is enforced in `feedreader_labels.py` and locked down by the contract tests in `test_feedreader_labels.py` (class `DocContractTest`). The last row of the table above went unimplemented from the loop's inception until 19 Aug 2026: `skipped` was written but never read back, and `added_to_zotero: false` only ever arrived by accident, via the three-day timeout.

**Use 👎 liberally** on off-topic headlines. Unclicked items are ambiguous — they could mean "not seen" just as easily as "not interesting." Only 👎 signals are unambiguous rejections.

"Added to Zotero" is detected two ways, by URL and by title. The URL half was silently broken until 16 August 2026: it queried the Zotero table that holds file paths rather than the one that holds URLs, so it always came back empty. Title matching covered for it, which is precisely why it went unnoticed — a dead signal propped up by its neighbour looks exactly like a quiet day. The counts are now compared on a normalised URL, so the link Zotero recorded after redirects still matches the one the feedreader read from the RSS. Threshold statistics count each article once rather than each log line, so an article that arrived repeatedly cannot outweigh the rest.

`feedreader-learn.py` runs as the last step of the morning batch (triggered by your login) and again at 09:00, 12:00, 15:00, 18:00 and 21:00, and tracks signal quality. Run it manually for a progress report:

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/feedreader-learn.py
```

It prints an evidence table for **`THRESHOLD_STAR`** — the only threshold in the pipeline with consequences, since it decides what gets auto-starred. `THRESHOLD_GREEN` and `THRESHOLD_YELLOW` only colour the 🟢/🟡/🔴 label; nothing is filtered out (the sole limit is `MAX_FEED_ITEMS`, a count).

The table reports, per candidate threshold: how many items you would star, how many of those ended up in Zotero, and the **lift** over the base rate — precision divided by the fraction of all articles that ever reached Zotero (2.6% as of 19 Aug 2026). A lift of 1.0 means the score tells you nothing you could not get by starring at random.

Three deliberate choices in that calculation:

- **Zotero membership is the yardstick, not the star.** The star may not grade itself; that was the circularity removed on 19 Aug 2026 (ADR-0005).
- **👎 signals set a hard floor, not a weight.** No threshold is recommended that would star an item you explicitly rejected. With 56 observations that class cannot carry a weighting, but it carries a boundary — and a boundary is the strongest thing you can do with it.
- **Timeout negatives are excluded, and the report says so.** Their score distribution sits almost on top of the positives' (AUC 0.585 against 0.771 for 👎): "ignored" mostly means "not seen", not "not interesting". At 10,859 rows against 56 they would drown the one informative signal 194 to 1.

The recommendation is the lowest threshold above the floor that reaches a lift of 2.5× with at least 30 Zotero hits behind it — lowest rather than best, because every step up costs coverage and a missed star is cheap: nothing is filtered, the item is still in the score-sorted feed. Fall short of 30 hits and the report gives no number at all rather than one with false precision.

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

Pressing 👎 fades the item and writes the URL, the feed guid and the title to `skip_queue.jsonl`; `feedreader-learn.py` processes it the next morning and matches on the guid before the URL (podcast feeds that reuse the show page as every episode's link would otherwise take a whole show down with one rejection). To send items to Zotero `_inbox`, use the Zotero browser extension or iOS app instead.

> **Two conditions, both easy to get wrong.** The button only appears when `FEEDREADER_PUBLIC_URL` is set, and it must be the **HTTPS** Tailscale-funnel address. NetNewsWire receives the article over HTTPS, so a plain-HTTP subresource is mixed content and WebKit blocks it silently — measured on 19 Aug 2026 with three variants under one article: the HTTPS button landed, the identical HTTP button did not. Between 18 and 29 Apr 2026 the button pointed at `http://<hostname>.local:8765`; 993 items passed through and not one 👎 arrived. And JavaScript must be enabled per device, so if the loop reports zero rejections for weeks, check that box first.

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
