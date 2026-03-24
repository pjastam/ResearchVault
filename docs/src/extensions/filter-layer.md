# Step 14: Set up filter layer per source

This is the core of the 3-phase model: phase 2, the filter moment, is set up differently for each source. Below is a per-source overview of the dump layer, the filter moment, and how you indicate what may enter the vault.

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

For podcasts the filter moment is intentionally manual — audio is harder to evaluate quickly than an abstract. You can ask Claude Code to fetch the show notes of an episode for additional help with the decision:

```
Fetch the show notes from [URL] and give a 3-sentence summary.
```

---

## RSS feeds

| Phase | What |
|------|-----|
| Dump layer (academic and non-academic) | NetNewsWire — unread items |
| Filter moment | Scan headline and intro |
| Go (academic) | Open article → save to Zotero via browser extension or iOS app → ends up in `_inbox` |
| Go (non-academic) | Save via Zotero Connector, or pass `inbox [URL]` to Claude Code |
| No-go | Mark item as read or delete from NetNewsWire |
