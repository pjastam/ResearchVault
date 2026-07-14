# Phase 3: processing to the vault

Phase 3 converts approved items into published wiki pages. The pipeline builds a canonical bundle in `raw/`, then hands it to **olw** (obsidian-llm-wiki) to ingest, compile, and review before publishing to `wiki/`. All generation runs locally: olw drives the primary model **mistral-small:22b** (fast=heavy) configured in `wiki.toml` (Ollama or MLX backend — set `LLM_BACKEND=mlx` in `ResearchVault/.env` to use MLX). Add `--hd` to any command to use Claude Sonnet 4.6 instead (after explicit confirmation).

---

## Papers

Papers reach `_inbox` via the Zotero browser extension, the iOS app, or automatically via the feedreader (after calibration). After a Go decision in Phase 2:

```
verwerk recente papers
```

Claude Code:
1. Retrieves metadata from Zotero MCP (title, authors, year, journal, citation key, tags) — no full text
2. Calls the local subagent `build-zotero-bundle.py` with only the item key and metadata:
   - `build-zotero-bundle.py` fetches the full text locally and assembles a canonical bundle at `raw/{citekey}__{itemKey}.md` (verbatim metadata, abstract, child notes, annotations, extracted text)
   - Claude Code receives only `{"status": "ok", "path": "raw/..."}` — no source content
3. Runs `olw ingest` to index the new bundle, then `olw compile` — olw generates draft pages via the local primary model (mistral-small:22b) into `wiki/.drafts/`
4. Removes the item from Zotero `_inbox`

The compiled draft page contains:
- YAML frontmatter (title, authors, year, journal, citation key, tags, status)
- Core question and main argument
- Key findings (3–5 points)
- Methodological notes
- Relevant quotes (original language)
- Links to related pages

`olw review` is the human quality gate: you inspect the draft in `wiki/.drafts/`, approve or reject it, and on approval olw publishes it to `wiki/` with cross-links to related pages. There is no separate `meta/candidates/` staging — `wiki/.drafts/` plus `olw review` *is* the gate.

> **Privacy:** no paper content ever appears in Claude Code's context. `build-zotero-bundle.py` and olw are self-contained local tools — they fetch, generate, and write without returning any source text to the orchestration layer.

---

## YouTube videos

YouTube items follow an **eager transcript pipeline**: when you mark a video ✅ in the feedreader, `attach-transcript.py` runs automatically and stores a cleaned transcript as an attachment in the Zotero item — mirroring how a PDF accompanies a paper. This makes Go/No-go decisions content-based.

**If the transcript attachment is missing** (e.g. for manually added items), run it explicitly:

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/attach-transcript.py \
  --item-key ITEMKEY --url "https://www.youtube.com/watch?v=..."
```

This script:
1. Fetches the transcript via `YouTubeTranscriptApi` (or from `.claude/transcript_cache/`)
2. The local LLM generates an abstract
3. Uploads the transcript as a `.txt` attachment to Zotero; sets `abstractNote`

After a **Go** decision, process the item the same way as papers:

```
verwerk recente papers
```

Claude Code calls `build-zotero-bundle.py`, which reads the transcript attachment from Zotero locally via `fetch-fulltext.py` and writes the bundle to `raw/`. Then `olw ingest` + `olw compile` produce a draft in `wiki/.drafts/`, and `olw review` is your gate before publishing to `wiki/`. No transcript content reaches Claude Code.

The compiled draft page contains:
- YAML frontmatter (title, authors, year, tags, status, Zotero deep link)
- TLDR
- Key findings (3–5 points)
- Methodological notes
- *(No "Relevant quotes" section — timestamps are unreliable without a verifiable source)*
- Links to related pages

---

## Podcasts

Podcast transcripts are created manually via `attach-transcript.py` — whisper.cpp requires audio download and transcription (minutes of processing), so it cannot run in the batch pipeline.

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/attach-transcript.py \
  --item-key ITEMKEY --url "https://podcast-episode-page-url"
```

This script:
1. Downloads audio using the direct MP3 URL cached from the RSS `<enclosure>` tag (via `feedreader-score.py`) or falls back to yt-dlp
2. Detects language automatically from cached show notes (Dutch show notes → `--language nl`); override with `--language` if needed
3. Transcribes locally via `whisper-cli` (model: `large-v3-turbo`, Metal GPU, ~2–3 min per 30 min audio on M4)
4. If `abstractNote` is already filled (show notes set by `enrich-inbox.py`): moves it to a child note titled "Shownotes"
5. Generates an abstract via the local LLM; sets `abstractNote`; stores transcript as `.txt` linked-file attachment; adds tag `_enriched-transcript`

After a **Go** decision, process the item the same way as papers: `build-zotero-bundle.py` → `raw/` → `olw ingest` → `olw compile` → `olw review` → `wiki/`.

**If yt-dlp fails** with "Unsupported URL": add the feed to `feedreader-list.txt`. After the next `feedreader-score.py` run, the direct audio URL is cached and used automatically.

Pages follow the same structure as YouTube: no "Relevant quotes" section (timestamps unreliable); all other sections as papers.

---

## RSS web articles

Non-academic articles from RSS feeds that you forward to `_inbox` can be processed the same way:

**Via Zotero** (recommended for articles worth citing):
```
verwerk recente papers
```
The item is already in `_inbox` with metadata from the Zotero Connector. Processed through the same `build-zotero-bundle.py` → `raw/` → olw path as a standard wiki page.

Pages get `#web` or `#beleid` as appropriate.

---

## Personal thinking

Your own notes and observations are not Zotero items. Promote them into the pipeline with `promote-to-raw.py`, which writes a bundle to `raw/notes/`. From there they are picked up by `olw ingest`/`olw compile` like any other bundle, and pass through `olw review` before landing in `wiki/`.

---

## After processing

After each session, check whether:

- New pages are linked to related existing pages (`[[double brackets]]`) — olw proposes cross-links during compilation, but confirm them during `olw review`
- Relevant syntheses in `wiki/syntheses/` need updating; the synthesised knowledge now lives in olw concept pages under `wiki/concepts/`

If new papers were added to Zotero, update the semantic search database:

```bash
update-zotero
```
