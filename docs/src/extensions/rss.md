# Step 12: RSS integration + feedreader filtering

In the 3-phase model, RSS feeds are pre-filtered automatically before you see them — the feedreader (`feedreader-score.py`) is part of phase 1, not a separate phase. It scores feeds daily so that your feed reader only shows items that are likely relevant to your research. You then browse this curated selection and send interesting items to Zotero `_inbox`. Only in phase 2 do you decide what goes into the vault.

## 12a. Feedreader — Automatic relevance filtering

`feedreader-score.py` runs daily via launchd and produces a filtered, scored Atom feed and HTML reader from your RSS subscriptions. It uses the same ChromaDB preference profile as `index-score.py` — items are scored by semantic similarity to your existing library.

**Install dependencies** (if not already present from step 10):

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/pip install feedparser sentence-transformers youtube-transcript-api
```

> `youtube-transcript-api` is used to fetch transcripts for YouTube items in your feeds. These transcripts enrich the relevance score (instead of scoring on the title alone) and are cached in `.claude/transcript_cache/` so they are only fetched once per video.

**Configure your feeds** — add one URL per line to `.claude/feedreader-list.txt`:

```
https://arxiv.org/rss/econ.GN
https://www.skipr.nl/feed/
http://onlinelibrary.wiley.com/rss/journal/10.1002/(ISSN)1099-1050
```

**Create and load the launchd agents** (run once after installation):

Both the HTTP server and the nightly batch jobs run as LaunchDaemons in `/Library/LaunchDaemons/` — they fire even without an active user session, which is required when the Mac wakes from a scheduled `pmset` power-on.

Create the HTTP server daemon in `/Library/LaunchDaemons/`:

```xml
<!-- /Library/LaunchDaemons/nl.researchvault.feedreader-server.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>nl.researchvault.feedreader-server</string>
  <key>UserName</key>
  <string>pietstam</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/pietstam/.local/share/uv/tools/zotero-mcp-server/bin/python3</string>
    <string>/Users/pietstam/Workspace/repos/GitHub/ResearchVault/.claude/feedreader-server.py</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/Users/pietstam/Library/Logs/feedreader-server.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/pietstam/Library/Logs/feedreader-server.log</string>
</dict>
</plist>
```

The nightly batch jobs run via `~/bin/nachtelijke-taken.sh`, called from a LaunchDaemon in `/Library/LaunchDaemons/`. Because it is a system-level daemon, it fires at 06:00 even without an active user session — which is required when the Mac wakes from a scheduled `pmset` power-on. The script runs sequentially in 6 steps: Zotero DB update → feedreader-score → FreshRSS actualize → feedreader-learn → proton-backup → proton-mirror → shutdown. The FreshRSS actualize step (`docker exec freshrss php /var/www/FreshRSS/app/actualize_script.php`) runs immediately after feedreader-score so that FreshRSS fetches the freshly generated feeds before the Mac shuts down. Without this step, FreshRSS would not update until the next time the Mac is awake and FreshRSS's own refresh schedule fires.

```xml
<!-- /Library/LaunchDaemons/nl.pietstam.nachtelijke-taken.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>nl.pietstam.nachtelijke-taken</string>
  <key>UserName</key>
  <string>pietstam</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>/Users/pietstam/bin/nachtelijke-taken.sh</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>6</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>WorkingDirectory</key>
  <string>/Users/pietstam</string>
  <!-- Script logs zelf via exec >> redirect; geen StandardOutPath nodig -->
  <key>TimeOut</key>
  <integer>7200</integer>
  <key>EnvironmentVariables</key>
  <dict>
    <key>LAUNCHD_RUN</key>
    <string>1</string>
  </dict>
  <key>RunAtLoad</key>
  <false/>
</dict>
</plist>
```

Install and load both daemons as root:

```bash
# feedreader-server
sudo cp /path/to/nl.researchvault.feedreader-server.plist /Library/LaunchDaemons/
sudo chown root:wheel /Library/LaunchDaemons/nl.researchvault.feedreader-server.plist
sudo chmod 644 /Library/LaunchDaemons/nl.researchvault.feedreader-server.plist
sudo launchctl load /Library/LaunchDaemons/nl.researchvault.feedreader-server.plist

# nachtelijke-taken
sudo cp /path/to/nl.pietstam.nachtelijke-taken.plist /Library/LaunchDaemons/
sudo chown root:wheel /Library/LaunchDaemons/nl.pietstam.nachtelijke-taken.plist
sudo chmod 644 /Library/LaunchDaemons/nl.pietstam.nachtelijke-taken.plist
sudo launchctl load /Library/LaunchDaemons/nl.pietstam.nachtelijke-taken.plist
```

**macOS sleep/wake settings** — configure a scheduled wake so the Mac powers on automatically before the 06:00 batch run:

1. **Scheduled wake for the nightly daemon** — set a recurring daily wake time at least 30 minutes before the batch job so that `UserEventAgent-System` has time to fully initialize before the 06:00 trigger fires:
   ```bash
   sudo pmset repeat wakeorpoweron MTWRFSU 05:30:00
   ```
   The Mac wakes at 05:30, the daemon fires at 06:00, and the Mac shuts down automatically at the end of the script. Check the schedule with `pmset -g sched`; cancel with `sudo pmset repeat cancel`. If the wake time is too close to 06:00 (< 30 min), `UserEventAgent-System` may not be ready in time and launchd silently skips the trigger — the job will then only run the next day.

2. **Network wake for iPhone/iPad access** — in **System Settings → Energy** (Dutch: *Energie-instellingen*), enable **"Schakel sluimerstand uit voor netwerktoegang"**. Despite the wording ("disable sleep for network access"), this puts the Mac into a lighter sleep state rather than deep sleep, keeping the network interface active so the HTTP server on port 8765 remains reachable from iPhone or iPad. The Mac still saves significant power compared to staying fully awake.

With both settings active you can put the Mac mini to sleep at the end of the day instead of just locking the screen.

**Run manually** (first time, or on demand):

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/feedreader-score.py
```

**Access the filtered feeds:**
- HTML reader (Mac/iPhone/iPad): `http://localhost:8765/filtered.html`
- Atom feed — web articles (NetNewsWire): `http://[mac-ip]:8765/filtered-webpage.xml`
- Atom feed — YouTube (NetNewsWire): `http://[mac-ip]:8765/filtered-youtube.xml`
- Atom feed — podcasts (NetNewsWire): `http://[mac-ip]:8765/filtered-podcast.xml`

Three separate Atom feeds are produced — one per source type. Each feed only contains items of that type, which lets you organise them into folders in NetNewsWire and apply different reading flows per type. Use the Mac's LAN IP instead of `localhost` so the feeds also work on iPad and iPhone.

The HTML reader includes an **⌨️ terminal** button in the header. Clicking it opens an embedded terminal panel (powered by ttyd — see [Step 17](browser-terminal.md)) alongside the article list, so you can run Phase 2 (Claude Code) without leaving the browser tab. The terminal works both on Mac (via `localhost`) and on iPad (via the Mac's local IP address).

**YouTube articles:** clicking a YouTube headline in the HTML reader opens a generated reading article at `http://localhost:8765/article/{video_id}` instead of going to YouTube. The article (Introduction + Key Points + Conclusion, written in the original video language) is generated locally by `qwen2.5:7b` via Ollama. The first visit takes 30–60 seconds; a loading page refreshes automatically every 5 seconds until it is ready. Subsequent visits are instant (cached in `.claude/article_cache/`).

**Podcast articles:** clicking a podcast headline opens a similar generated article at `http://localhost:8765/article/podcast/{episode_id}`, based on the episode's show notes rather than an audio transcript. Only episodes with show notes of at least 200 characters get an article page; episodes with thinner show notes link directly to the source. Generation follows the same async pattern as YouTube articles.

The article page (for both YouTube and podcast) includes three tag buttons — **✅ verwerken**, **📖 later lezen**, **geen tag** (default) — that control which Zotero tag is attached when you save the page via the Zotero Connector. The selected tag is injected as a COinS span (`<span class="Z3988">`); the full article text is also injected as `rft.description`, so it appears automatically in the Abstract field of the saved Zotero item.

> **Serve directory:** the HTTP server serves files from `~/.local/share/feedreader-serve/`, not from `~/Documents/`, because macOS TCC prevents system Python from accessing the Documents folder when launched via launchd.

**Learning loop** — `feedreader-learn.py` runs daily as part of the nightly batch job and matches recently added Zotero items (by URL) against the score log. After ≥30 positives it prints a threshold recommendation. Once the threshold is stable, activate score filtering in `feedreader-score.py` by adjusting `THRESHOLD_GREEN` and `THRESHOLD_YELLOW`.

> **Privacy note:** `feedreader-score.py` runs entirely locally. Feed URLs are fetched directly from the source; no feed content is sent to any cloud service.

## 12b. RSS feeds via NetNewsWire

NetNewsWire is a free, open-source RSS reader for macOS and iOS. Rather than subscribing to individual feeds, you subscribe to the three filtered feeds produced by the feedreader. This way your reading list only contains items that are likely relevant, sorted by relevance score.

**Install:**

```bash
brew install --cask netnewswire
```

Or download via [netnewswire.com](https://netnewswire.com).

**Connect NetNewsWire to FreshRSS** (not directly to the feeds) — this is required for cross-device read/unread sync. See [Step 12c](#12c-freshrss--readunread-sync-across-devices) for FreshRSS setup. Once FreshRSS is running, add a FreshRSS account in NetNewsWire on each device:

NetNewsWire → Settings → Accounts → **+** → FreshRSS
- API URL: `http://[mac-ip]:8080/api/greader.php` (full path required — base URL alone does not work)
- Username + API password

NetNewsWire will then show the three filtered feeds (webpage, YouTube, podcast) via FreshRSS, with read/unread status synced across all devices.

Titles are prefixed with score and label (`🟢 54 | Title…`). Items in each Atom feed are sorted by relevance score: the feedreader assigns a synthetic publication time within today's date (higher score = later time) so that higher-scoring items appear first in NetNewsWire's **Newest First** sort order. The server always responds with HTTP 200 for feed requests (never 304 Not Modified), ensuring NetNewsWire refreshes the feed contents on every poll.

Each Atom feed is limited to the top 300 items by score. Items older than 30 days (web articles, podcasts, YouTube) or 365 days (academic journal feeds) are automatically excluded.

**Enable JavaScript in NetNewsWire** — required for the action buttons to work:

1. NetNewsWire → **Settings** → **Article Content**
2. Check **"Enable JavaScript"**

**Action buttons in the article view** — each item in NetNewsWire has three buttons at the bottom of the article:

| Button | Action |
|--------|--------|
| **✅ Zotero** | Adds the item to Zotero `_inbox` with tag `✅` (processed) via the Zotero Web API |
| **📖 Later lezen** | Adds the item to Zotero `_inbox` with tag `📖` (read later) |
| **👎 Overslaan** | Marks the item as skipped — sends a negative signal to the learning loop |

The buttons fire a silent HTTP request to the local server via `new Image().src` — no browser tab opens. The item's title, URL, source, publication date, and type are sent along so the Zotero entry is complete.

> **Zotero Web API key required:** the action buttons use the Zotero Web API to add items directly. Set your API key in `~/.zprofile`:
> ```bash
> export ZOTERO_API_KEY="your-key-here"
> ```
> Obtain your key at [zotero.org/settings/keys](https://www.zotero.org/settings/keys) (read/write access to library).

**Add your source feeds** to `.claude/feedreader-list.txt` instead of directly to NetNewsWire. Useful sources:
- Journal RSS (e.g. BMJ, NEJM, Wiley Health Economics)
- PubMed searches: `https://pubmed.ncbi.nlm.nih.gov/rss/search/?term=[searchterm]&format=abstract`
- Policy sites and government newsletters
- Trade blogs (e.g. Zorgvisie, Skipr)
- Substack: `[name].substack.com/feed`

> **Phase 1:** Items in the filtered feed have not yet been saved — they only exist in your feed reader. You browse through them and scan the scored headlines. Only what is truly relevant gets forwarded to Zotero. That is the phase 1 moment.

**From NetNewsWire to the vault (phase 1 → phase 2 → phase 3):**

Interesting articles are saved via two routes:

- **Via action buttons** (✅ / 📖): click directly in the NNW article view — the item is added to Zotero `_inbox` immediately, with the correct type (webpage / videoRecording / podcast), source, date, and tag.
- **Via Zotero browser extension or iOS app:** open the article in a browser, click the Zotero icon → item is saved with full metadata to Zotero `_inbox`. Use this route when you want annotation capabilities or need richer metadata.
- **Direct to `inbox/`:** pass the URL to Claude Code with the instruction `inbox [URL]` → Claude Code fetches the content and saves it as a Markdown file in `inbox/`, without Zotero. Use this route for non-academic articles and policy documents.

> **Privacy note:** NetNewsWire stores feed data locally. No reading habits are sent to external servers.

## 12c. FreshRSS — read/unread sync across devices

Without FreshRSS, read/unread status in NetNewsWire is device-local: marking an item as read on your Mac is not visible on your iPad. FreshRSS is a self-hosted RSS sync backend that solves this. It runs in Docker on the Mac mini.

**Install Docker Desktop:**

```bash
brew install --cask docker
```

Open Docker Desktop from Launchpad and wait until the whale icon in the menu bar stops animating.

**Start FreshRSS:**

```bash
docker run -d \
  --name freshrss \
  -p 8080:80 \
  --restart unless-stopped \
  freshrss/freshrss
```

Open `http://[mac-ip]:8080` in your browser and complete the FreshRSS installation wizard. Create an admin account.

**Set API password** (required for NetNewsWire):

In FreshRSS → click your username top-right → **Profile** → scroll to **API Management** → set an API password.

**Add the three feeds in FreshRSS** (use the Mac mini's LAN IP, not `localhost`):

- `http://[mac-ip]:8765/filtered-webpage.xml`
- `http://[mac-ip]:8765/filtered-youtube.xml`
- `http://[mac-ip]:8765/filtered-podcast.xml`

**Connect NetNewsWire** on each device (Mac, iPad, iPhone):

NetNewsWire → Settings → Accounts → **+** → FreshRSS
- API URL: `http://[mac-ip]:8080/api/greader.php` (full path required — base URL alone does not work)
- Username + API password from above

> **Note:** FreshRSS may show a "Niet ingedeeld" (Uncategorised) folder in NetNewsWire alongside any custom categories. This is a known limitation of the Google Reader API integration — the folder is empty and does not affect functionality.

**Remote access outside your home network** — use Tailscale Funnel to expose FreshRSS publicly over HTTPS without requiring Tailscale on the iPhone:

```bash
tailscale funnel --bg http://localhost:8080
```

This makes FreshRSS available at `https://[machine-name].[tailnet].ts.net/`. No changes needed to the NetNewsWire account — NNW continues to sync via the LAN IP at home; the Funnel URL is for browser access outside the home network. Tailscale Funnel is free and does not require port forwarding on the router. Only FreshRSS (port 8080) is exposed — nothing else on the Mac mini is reachable via the Funnel URL.

> **Privacy note:** FreshRSS runs entirely on your Mac mini. Read/unread sync stays on the local network. The Funnel URL is publicly accessible — protect FreshRSS with a strong password.

## 12d. Feedback signals: training the scoring

The HTML reader (`http://localhost:8765/filtered.html`) captures three types of user behaviour that feed into the learning loop:

| # | Behaviour | Signal strength | Recorded as |
|---|-----------|-----------------|-------------|
| 1 | Item clicked + added to Zotero | Strong positive | `added_to_zotero: true` |
| 2 | Item clicked, not added to Zotero | Weak negative (seen but not interesting enough) | `added_to_zotero: false` after 3 days |
| 3 | Item not clicked, no 👎 pressed | Ambiguous — not seen, or implicitly ignored | `added_to_zotero: false` after 3 days — indistinguishable from type 2 |
| 4 | 👎 pressed without clicking | **Strong explicit negative** (headline was enough to reject) | `skipped: true` immediately |
| 5 | Item clicked, then 👎 pressed | **Strongest negative signal** (read and rejected) | `skipped: true` + `added_to_zotero: false` |

> **Type 3 remains ambiguous** even with the 👎 button. Items you never looked at receive the same label as items you chose not to add. Only types 4 and 5 are unambiguous rejections. `feedreader-learn.py` reports all three categories separately so you can track signal quality over time.

**How to use the 👎 button:**
- When a headline is clearly off-topic, press 👎 directly — no need to open the article.
- The item is immediately faded and struck through in the reader.
- The rejection is sent to the server and queued in `skip_queue.jsonl`; `feedreader-learn.py` processes it the next morning.

**Future use of explicit negatives:** once enough `skipped: true` items have accumulated, they can be used to build a negative profile that penalises similarity to rejected content: `score = sim(item, positive_profile) − λ × sim(item, negative_profile)`. The learning loop will advise when enough data is available.

---

## 12e. Academic feeds: from NetNewsWire to Zotero

For academic articles from NetNewsWire, the recommended route is to always add them to Zotero first before having them processed. This way you have BibTeX metadata and annotation capabilities available:

1. Click **✅ Zotero** or **📖 Later lezen** in the article view — the item is saved directly to `_inbox`
2. Or open the article in a browser → click the Zotero icon → item is saved to `_inbox` with richer metadata
3. In the next research session, run `index-score.py` and process items from `_inbox` via the skill
