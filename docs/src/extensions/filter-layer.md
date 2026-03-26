# Step 14: Set up filter layer per source

This is the core of the 4-phase model: each source has its own pre-filter (phase 0, where applicable) and filter moment (phase 2). Below is a per-source overview of all phases and how you indicate what may enter the vault.

## Papers (Zotero)

| Phase | What |
|------|-----|
| Dump layer | Zotero `_inbox` collection — central collection bucket for all sources |
| Filter moment | Run `index-score.py` to rank items by relevance; read abstract in Zotero, or have Claude Code summarize via Qwen3.5:9b (locally) |
| Go | Move item to the relevant collection in your library |
| No-go | Delete item from `_inbox` — no note is created |

### Tag-based filter logic

Claude Code adjusts its evaluation based on the Zotero tag of the item:

| Tag | Treatment |
|-----|------------|
| `✅` | Previously approved — skip Go/No-go, go directly to processing |
| `📖` | Marked as interesting — only ask the Go/No-go question, no summary |
| `/unread`, no tag, or another tag | Generate summary + relevance indication, ask Go or No-go |

Items with unknown tags (e.g. your own project tags or type indicators) are therefore treated as `/unread`: Claude Code generates a summary and asks for a Go/No-go decision.

**No-go is always final:** a rejected item is deleted from `_inbox` and receives no note in the vault. Claude Code always asks for confirmation before deletion.

### Reading status in Obsidian

Every literature note gets a `status` field in its YAML frontmatter:
- `status: unread` — default for all new notes
- `status: read` — set automatically when the Zotero item had a `✅` tag (meaning you had already read it before approving)

After reading a note in Obsidian, change `status: unread` to `status: read` manually.

To see all unread notes at a glance, create a note with this [Dataview](https://blacksmithgu.github.io/obsidian-dataview/) query:

```dataview
TABLE authors, year, journal, tags
FROM "literature"
WHERE status = "unread"
SORT year DESC, file.name ASC
```

> **Note:** frontmatter tags must be written without `#` (e.g. `tags: [beleid, zorg]`). Obsidian adds the `#` in the UI automatically. Using `#` inside a YAML array breaks frontmatter parsing.

### Relevance scoring with index-score.py

Before starting the Go/No-go review, you can run `index-score.py` to get a ranked list of inbox items sorted by semantic similarity to your existing library:

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/index-score.py
```

The script uses ChromaDB embeddings (all-MiniLM-L6-v2, same model as zotero-mcp) to compute a relevance score (0–100) per item. Items with PDF annotations in Zotero weigh more heavily in the preference profile. Output labels: 🟢 strong match (≥70) · 🟡 possibly relevant (40–69) · 🔴 weak match (<40).

### Summary requests

Claude Code can help you with the evaluation — ask for a summary of items in `_inbox`:

```
Give me an overview of the items in my Zotero _inbox collection with a 2–3 sentence
summary per item and a relevance assessment for my research on [topic].
```

Claude Code retrieves the metadata and abstract via Zotero MCP and gives a recommendation per item. You then decide which items deserve the next step.

---

## YouTube videos

| Phase | What |
|------|-----|
| Dump layer | Zotero `_inbox` via iOS share sheet from the YouTube app |
| Filter moment | Watch the first 5–10 minutes, or have Claude Code summarize based on metadata |
| Go | `transcript [URL]` in Claude Code |
| No-go | Delete item from `_inbox` |

---

## Podcasts

| Phase | What |
|------|-----|
| Dump layer | Zotero `_inbox` via iOS share sheet from Overcast (overcast.fm URL) |
| Filter moment | Listen to the first 5–10 minutes |
| Go | `podcast [URL]` in Claude Code (download + transcription + processing) |
| No-go | Delete item from `_inbox` |

For podcasts with rich show notes (≥ 200 characters), clicking the headline in the HTML reader opens a generated article at `/article/podcast/{episode_id}` — the same layout as YouTube articles, with tag buttons and abstract injection via COinS. For episodes with thin show notes the headline links directly to the source. You can also ask Claude Code to fetch show notes manually:

```
Fetch the show notes from [URL] and give a 3-sentence summary.
```

---

## RSS feeds

| Phase | What |
|------|-----|
| Phase 0 — Pre-filter | `phase0-score.py` scores all feed items daily; YouTube items are scored using transcript text fetched via `youtube_transcript_api`; podcast items with show notes ≥ 200 chars have their show notes cached; produces filtered Atom feed + HTML reader sorted by relevance at `http://localhost:8765/filtered.html`; clicking a YouTube headline opens a generated article (`/article/{video_id}`) with Zotero tag buttons; clicking a podcast headline (with sufficient show notes) opens a similar article (`/article/podcast/{episode_id}`); both article types inject the full text into the Zotero Abstract field via `rft.description` in COinS |
| Phase 1 — Dump layer | Browse the filtered feed in the HTML reader or NetNewsWire; interesting items forwarded to Zotero `_inbox` via browser extension or iOS app |
| Phase 2 — Filter moment | Scan headline and intro of items in `_inbox` |
| Go (academic) | Item already in Zotero `_inbox` → process via type 0 → type 1 in the skill |
| Go (non-academic) | Save via Zotero Connector, or pass `inbox [URL]` to Claude Code |
| No-go | Mark item as read or delete from NetNewsWire; remove from `_inbox` if already saved |

### Feedback signals in the HTML reader

The HTML reader captures five distinct behaviour types that feed into the learning loop (`phase0-learn.py`):

| # | Behaviour | Signal | Recorded as |
|---|-----------|--------|-------------|
| 1 | Headline clicked + added to Zotero | Strong positive | `added_to_zotero: true` |
| 2 | Headline clicked, not added to Zotero | Weak negative (seen, not interesting enough) | `added_to_zotero: false` after 3 days |
| 3 | Not clicked, no 👎 | Ambiguous — not seen, or implicitly ignored | `added_to_zotero: false` after 3 days (indistinguishable from type 2) |
| 4 | 👎 pressed without clicking | Strong explicit negative (headline was enough to reject) | `skipped: true` immediately |
| 5 | Headline clicked, then 👎 pressed | Strongest negative signal (read and rejected) | `skipped: true` + `added_to_zotero: false` |

Only types 4 and 5 are unambiguous rejections. Type 3 remains ambiguous even with the 👎 button. See [Step 12c](rss.md#12c-feedback-signals-training-the-scoring) for details on how these signals are used to calibrate scoring thresholds.
