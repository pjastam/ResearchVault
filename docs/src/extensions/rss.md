# Step 12: RSS integration + Phase 0 filtering

In the 4-phase model, RSS feeds are pre-filtered automatically before you see them (phase 0), so that your feed reader only shows items that are likely relevant to your research. You then browse this curated selection and send interesting items to Zotero `_inbox` (phase 1). Only in phase 2 do you decide what goes into the vault.

## 12a. Phase 0 — Automatic relevance filtering

`phase0-score.py` runs daily via launchd and produces a filtered, scored Atom feed and HTML reader from your RSS subscriptions. It uses the same ChromaDB preference profile as `index-score.py` — items are scored by semantic similarity to your existing library.

**Install dependencies** (if not already present from step 10):

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/pip install feedparser sentence-transformers youtube-transcript-api
```

> `youtube-transcript-api` is used to fetch transcripts for YouTube items in your feeds. These transcripts enrich the relevance score (instead of scoring on the title alone) and are cached in `.claude/transcript_cache/` so they are only fetched once per video.

**Configure your feeds** — add one URL per line to `.claude/phase0-feeds.txt`:

```
https://arxiv.org/rss/econ.GN
https://www.skipr.nl/feed/
http://onlinelibrary.wiley.com/rss/journal/10.1002/(ISSN)1099-1050
```

**Load the launchd agents** (run once after installation):

```bash
launchctl load ~/Library/LaunchAgents/nl.researchvault.phase0-server.plist
launchctl load ~/Library/LaunchAgents/nl.researchvault.phase0-score.plist
launchctl load ~/Library/LaunchAgents/nl.researchvault.phase0-learn.plist
```

This starts a local HTTP server on port 8765 and schedules the daily score run at 06:00.

**Run manually** (first time, or on demand):

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/phase0-score.py
```

**Access the filtered feed:**
- HTML reader (Mac/iPhone/iPad): `http://localhost:8765/filtered.html`
- Atom feed (NetNewsWire): `http://localhost:8765/filtered.xml`

**YouTube articles:** clicking a YouTube headline in the HTML reader opens a generated reading article at `http://localhost:8765/article/{video_id}` instead of going to YouTube. The article (Introduction + Key Points + Conclusion, written in the original video language) is generated locally by `qwen2.5:7b` via Ollama. The first visit takes 30–60 seconds; a loading page refreshes automatically every 5 seconds until it is ready. Subsequent visits are instant (cached in `.claude/article_cache/`).

The article page includes three tag buttons — **✅ verwerken**, **📖 later lezen**, **geen tag** (default) — that control which Zotero tag is attached when you save the page via the Zotero Connector. The selected tag is injected as a COinS span (`<span class="Z3988">`) that Zotero reliably reads at page-load time.

> **Serve directory:** the HTTP server serves files from `~/.local/share/phase0-serve/`, not from `~/Documents/`, because macOS TCC prevents system Python from accessing the Documents folder when launched via launchd.

**Learning loop** — `phase0-learn.py` runs daily at 06:15 and matches recently added Zotero items (by URL) against the score log. After ≥30 positives it prints a threshold recommendation. Once the threshold is stable, activate score filtering in `phase0-score.py` by adjusting `THRESHOLD_GREEN` and `THRESHOLD_YELLOW`.

> **Privacy note:** `phase0-score.py` runs entirely locally. Feed URLs are fetched directly from the source; no feed content is sent to any cloud service.

## 12b. RSS feeds via NetNewsWire

NetNewsWire is a free, open-source RSS reader for macOS and iOS, with iCloud sync between both devices. Rather than subscribing to individual feeds, you subscribe to the single filtered feed produced by Phase 0. This way your reading list only contains items that are likely relevant, sorted by relevance score.

**Install:**

```bash
brew install --cask netnewswire
```

Or download via [netnewswire.com](https://netnewswire.com).

**Subscribe to the filtered feed** — add this single URL in NetNewsWire:

```
http://localhost:8765/filtered.xml
```

Titles are prefixed with score and label (`🟢 54 | Title…`). To sort by relevance, click the **Date** column header → **Newest First**. Phase 0 encodes the score as a synthetic publication date so that higher-scoring items appear at the top.

**Add your source feeds** to `.claude/phase0-feeds.txt` instead of directly to NetNewsWire. Useful sources:
- Journal RSS (e.g. BMJ, NEJM, Wiley Health Economics)
- PubMed searches: `https://pubmed.ncbi.nlm.nih.gov/rss/search/?term=[searchterm]&format=abstract`
- Policy sites and government newsletters
- Trade blogs (e.g. Zorgvisie, Skipr)
- Substack: `[name].substack.com/feed`

> **Phase 0 → phase 1:** Items in the filtered feed have not yet been saved — they only exist in your feed reader. You browse through them and scan the scored headlines. Only what is truly relevant gets forwarded to Zotero. That is the phase 1 moment.

**From NetNewsWire to the vault (phase 1 → phase 2 → phase 3):**

Interesting articles are saved via two routes:

- **Via Zotero browser extension or iOS app:** open the article, click the Zotero icon → item is saved with metadata to Zotero `_inbox`. Use this route for academic articles where you want to retain BibTeX metadata and annotation capabilities.
- **Direct to `inbox/`:** pass the URL to Claude Code with the instruction `inbox [URL]` → Claude Code fetches the content and saves it as a Markdown file in `inbox/`, without Zotero. Use this route for non-academic articles, news items, and policy documents.

> **Privacy note:** NetNewsWire stores feed data locally. No reading habits are sent to external servers.

## 12c. Feedback signals: training the scoring

The HTML reader (`http://localhost:8765/filtered.html`) captures three types of user behaviour that feed into the learning loop:

| # | Behaviour | Signal strength | Recorded as |
|---|-----------|-----------------|-------------|
| 1 | Item clicked + added to Zotero | Strong positive | `added_to_zotero: true` |
| 2 | Item clicked, not added to Zotero | Weak negative (seen but not interesting enough) | `added_to_zotero: false` after 3 days |
| 3 | Item not clicked, no 👎 pressed | Ambiguous — not seen, or implicitly ignored | `added_to_zotero: false` after 3 days — indistinguishable from type 2 |
| 4 | 👎 pressed without clicking | **Strong explicit negative** (headline was enough to reject) | `skipped: true` immediately |
| 5 | Item clicked, then 👎 pressed | **Strongest negative signal** (read and rejected) | `skipped: true` + `added_to_zotero: false` |

> **Type 3 remains ambiguous** even with the 👎 button. Items you never looked at receive the same label as items you chose not to add. Only types 4 and 5 are unambiguous rejections. `phase0-learn.py` reports all three categories separately so you can track signal quality over time.

**How to use the 👎 button:**
- When a headline is clearly off-topic, press 👎 directly — no need to open the article.
- The item is immediately faded and struck through in the reader.
- The rejection is sent to the server and queued in `skip_queue.jsonl`; `phase0-learn.py` processes it the next morning.

**Future use of explicit negatives:** once enough `skipped: true` items have accumulated, they can be used to build a negative profile that penalises similarity to rejected content: `score = sim(item, positive_profile) − λ × sim(item, negative_profile)`. The learning loop will advise when enough data is available.

---

## 12d. Academic feeds: from NetNewsWire to Zotero

For academic articles from NetNewsWire, the recommended route is to always add them to Zotero first before having them processed. This way you have BibTeX metadata and annotation capabilities available:

1. Open the article from NetNewsWire in your browser
2. Click the Zotero icon in your browser (or use the Zotero iOS app) → item is saved to `_inbox`
3. Process from `_inbox` via type 0 → type 1 in the skill
