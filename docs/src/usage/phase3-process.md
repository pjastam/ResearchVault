# Phase 3: building the canonical bundle

Phase 3 converts approved items into a **canonical bundle** at `raw/{citekey}__{itemKey}.md` — one Markdown file per source, verbatim, engine-neutral. This is where ResearchVault's work ends: five different source types (PDF, YouTube transcript, podcast transcript, RSS article, personal note) converge on one documented format.

What happens next — turning bundles into an interlinked wiki — is a **replaceable backend**. See [Choosing a backend](../backends/choosing.md).

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
3. Removes the item from Zotero `_inbox`

> **Privacy:** no paper content ever appears in Claude Code's context. `build-zotero-bundle.py` is a self-contained local tool — it fetches and writes without returning any source text to the orchestration layer.

---

## YouTube videos

YouTube items follow an **eager transcript pipeline**: when you mark a video ✅ in the feedreader, `attach-transcript.py` runs automatically and stores a cleaned transcript as an attachment in the Zotero item — mirroring how a PDF accompanies a paper. This makes Go/No-go decisions content-based.

**If the transcript attachment is missing** (e.g. for manually added items), run it explicitly:

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/attach-transcript.py \
  --item-key ITEMKEY --url "https://www.youtube.com/watch?v=..."
```

This script:
1. Fetches the transcript via `YouTubeTranscriptApi` (or from `.claude/transcript_cache/`), preferring `nl`/`en` and falling back to any available language (needed for Dutch sources such as NOS/VPRO/NPO)
2. The local LLM generates an abstract
3. Uploads the transcript as a `.txt` attachment to Zotero; sets `abstractNote`

After a **Go** decision, process the item the same way as papers:

```
verwerk recente papers
```

Claude Code calls `build-zotero-bundle.py`, which reads the transcript attachment from Zotero locally via `fetch-fulltext.py` and writes the bundle to `raw/`. No transcript content reaches Claude Code.

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
3. Converts the audio to 16 kHz mono 16-bit PCM via ffmpeg, then transcribes locally via `whisper-cli` (model: `large-v3-turbo`, Metal GPU, ~2–3 min per 30 min audio on M4)
4. If `abstractNote` is already filled (show notes set by `enrich-inbox.py`): moves it to a child note titled "Shownotes"
5. Generates an abstract via the local LLM; sets `abstractNote`; stores transcript as `.txt` linked-file attachment; adds tag `_enriched-transcript`

After a **Go** decision, process the item the same way as papers: `build-zotero-bundle.py` → `raw/`.

**If yt-dlp fails** with "Unsupported URL": add the feed to `feedreader-list.txt`. After the next `feedreader-score.py` run, the direct audio URL is cached and used automatically. This is the intended route — an episode should arrive through the feed reader, where it also gets a relevance score. yt-dlp is the escape hatch for one-off episodes from feeds you do not subscribe to, and that branch cannot transcode without ffmpeg.

**Why the ffmpeg step (step 3).** `whisper-cli` decodes audio with the built-in ggml/dr_libs decoders and is not linked against `libav*`, so it reads wav, mp3 and flac but not m4a/aac or opus. On an unreadable file it prints `error: failed to read audio file` and exits **0** without writing a `.txt` — indistinguishable from a failed transcription. Converting up front removes the format question entirely. If ffmpeg is absent the conversion is skipped and the original file is passed through, so ffmpeg is an improvement rather than a hard requirement.

**A non-zero exit does not always mean no transcript.** If whisper demonstrably ran to completion — both end markers (`output_txt: saving output to` and `whisper_print_timings:`) present in stderr, and the `.txt` on disk — the transcript is kept and the crash is logged as a teardown failure. Without that evidence it is rejected: a partial transcript must never pass as a complete one.

> **Privacy note:** whisper-cli writes transcript text to **stdout** and only engine diagnostics to **stderr**. That is why stderr may be logged and stdout may not.

---

## RSS web articles

Non-academic articles from RSS feeds that you forward to `_inbox` can be processed the same way:

**Via Zotero** (recommended for articles worth citing):
```
verwerk recente papers
```
The item is already in `_inbox` with metadata from the Zotero Connector. Processed through the same `build-zotero-bundle.py` → `raw/` path as a standard paper.

Tag the item `#web` or `#beleid` as appropriate — the tag travels with the item into the bundle's frontmatter.

---

## Personal thinking

Your own notes and observations are not Zotero items. Promote them into the pipeline with `promote-to-raw.py`, which writes a bundle to `raw/notes/`.

---

## After processing

If new papers were added to Zotero, update the semantic search database:

```bash
update-zotero
```
