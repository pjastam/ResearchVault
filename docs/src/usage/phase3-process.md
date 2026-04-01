# Phase 3: processing to the vault

Phase 3 converts approved items into structured Obsidian notes. All generation runs locally via Qwen3.5:9b. Add `--hd` to any command to use Claude Sonnet 4.6 instead (after explicit confirmation).

---

## Papers

Papers reach `_inbox` via the Zotero browser extension, the iOS app, or automatically via the feedreader (after calibration). After a Go decision in Phase 2:

```
verwerk recente papers
```

Claude Code:
1. Retrieves metadata from Zotero MCP (title, authors, year, journal, citation key, tags) — no full text
2. Calls the local subagent `process_item.py` with only the item key and metadata:
   - `process_item.py` fetches the full text locally, generates a structured note via Qwen3.5:9b, builds the YAML frontmatter, and writes the `.md` file to `literature/`
   - Claude Code receives only `{"status": "ok", "path": "literature/..."}` — no source content
3. Adds `[[internal links]]` to related notes in the vault
4. Removes the item from Zotero `_inbox`

The generated note contains:
- YAML frontmatter (title, authors, year, journal, citation key, tags, status)
- Core question and main argument
- Key findings (3–5 points)
- Methodological notes
- Relevant quotes (original language)
- Links to related notes

Notes are saved to `literature/[citation-key].md`.

> **Privacy:** no paper content ever appears in Claude Code's context. `process_item.py` is a self-contained local subagent — it fetches, generates, and writes without returning any source text to the orchestration layer.

---

## YouTube videos

Videos added via the iOS share sheet from the YouTube app arrive in Zotero `_inbox` as watch URLs. After a Go decision:

```
transcript [URL]
```

Claude Code:
1. Checks whether a transcript is already cached from the feedreader (`.claude/transcript_cache/{video_id}.json`) — no re-fetch needed if so
2. Falls back to yt-dlp if no cache exists
3. Generates a structured note locally via Qwen3.5:9b:
   - Title, speaker, channel, date, URL
   - Summary (3–5 sentences)
   - Key points with timestamps
   - Relevant quotes with timestamps
4. Adds frontmatter, `[[internal links]]`, and `#video` tag
5. Removes the raw transcript from `inbox/` and the item from Zotero `_inbox`

Notes are saved to `literature/[speaker-year-keyword].md`.

---

## Podcasts

Podcast episodes added from Overcast (via iOS share sheet) arrive in Zotero `_inbox` as overcast.fm URLs. After a Go decision:

```
podcast [URL]
```

Claude Code:
1. Checks for a cached show notes file in `.claude/transcript_cache/podcast_{episode_id}.json`
2. If no cache: downloads audio via yt-dlp, transcribes locally via whisper.cpp (automatic language detection)
3. For long episodes (> 45 min): generates a layered summary first (main line → per segment), then the final note
4. Generates a structured note locally via Qwen3.5:9b:
   - Title, speaker(s), programme/channel, date, URL
   - Summary (3–5 sentences)
   - Key points with timestamps
   - Relevant quotes with timestamps (original language)
5. Adds frontmatter, `[[internal links]]`, and `#podcast` tag
6. Removes raw `.mp3` and `.txt` files from `inbox/` and the item from Zotero `_inbox`

Notes are saved to `literature/[speaker-year-keyword].md`.

---

## RSS web articles

Non-academic articles from RSS feeds that you forward to `_inbox` can be processed in two ways:

**Via Zotero** (recommended for articles worth citing):
```
verwerk recente papers
```
The item is already in `_inbox` with metadata from the Zotero Connector. Processed as a standard literature note.

**Direct to `inbox/`** (for news items, policy documents, quick reads):
```
inbox [URL]
```
Claude Code fetches the article and saves it as a Markdown file in `inbox/`. You can then ask Claude Code to convert it to a note in `literature/`.

Notes get `#web` or `#beleid` as appropriate.

---

## After processing

After each session, check whether:

- New notes are linked to related existing notes (`[[double brackets]]`)
- Relevant syntheses in `syntheses/` need updating
- Flashcards should be created for the new notes:

```
maak flashcards voor literature/[note].md
```

If new papers were added to Zotero, update the semantic search database:

```bash
update-zotero
```
