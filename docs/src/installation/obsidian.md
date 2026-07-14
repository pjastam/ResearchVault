# Step 7: Install Obsidian and create vault

## 7a. Download Obsidian

Download Obsidian via [obsidian.md](https://obsidian.md). Install the application in the usual way.

## 7b. Create a vault

1. Open Obsidian
2. Choose **"Create new vault"**
3. Give the vault a name, e.g. `ResearchVault`
4. Choose a location you will remember, e.g. `~/Documents/ResearchVault`
5. Click **"Create"**

## 7c. Create folder structure

Create the following folders in your vault (right-click in the left panel → "New folder"):

```
ResearchVault/
├── raw/                 ← canonical bundles per Zotero item (input layer)
├── wiki/                ← published, olw-managed concept & synthesis pages
│   └── .drafts/         ← olw-compiled drafts pending review (staging)
├── .olw/                ← olw state
├── projects/            ← per project or collaboration
├── daily/               ← daily notes
└── inbox/               ← raw input, yet to be processed
```

`raw/` holds the canonical bundles that `build-zotero-bundle.py` writes (`raw/{citekey}__{itemKey}.md`); `wiki/` holds the pages that `olw` generates and maintains. You do not hand-write notes into `wiki/` — `olw compile` places drafts in `wiki/.drafts/` and `olw review` (the human quality gate) publishes them.

## 7d. Create CLAUDE.md

Create a file `CLAUDE.md` in the **root of your vault** (not in a subfolder). This is Claude Code's memory. Paste the following starter text and adjust to your preference:

```markdown
# CLAUDE.md — ResearchVault Workflow

## Obsidian conventions
- All files are Markdown (.md)
- Use [[double brackets]] for internal links between notes
- Use #tags for thematic categorization
- File names: use hyphens, no spaces (e.g. `author-2024-keyword.md`)

## Vault structure
- `raw/` — canonical bundles, one per Zotero item (`raw/{citekey}__{itemKey}.md`)
- `wiki/` — published concept and synthesis pages, managed by olw
- `wiki/.drafts/` — olw-compiled drafts pending review (staging)
- `.olw/` — olw state
- `projects/` — project-specific documentation
- `daily/` — daily notes and log
- `inbox/` — raw input yet to be processed

## Wiki pages (from Zotero)
The knowledge base is built by olw (obsidian-llm-wiki), not by hand. On Go, `build-zotero-bundle.py` writes a canonical bundle to `raw/`; then `olw ingest` and `olw compile` produce draft pages in `wiki/.drafts/`; `olw review` (the human quality gate) publishes them to `wiki/`. Each olw concept page carries the synthesised knowledge:
- Bibliographic details (author, year, journal)
- Core question and main argument
- Key findings (3–5 points)
- Methodological notes
- Quotes relevant to my research
- Links to related pages in the wiki

## Language
- Answer in English unless asked otherwise
- Write wiki pages in English, quotes in the original language

## Zotero workflow
- Use Zotero MCP to retrieve papers by title or keywords
- On Go, run `build-zotero-bundle.py` to create the bundle in `raw/`, then let olw ingest, compile and (after review) publish to `wiki/`
- Always add a #tag for the topic of the paper

## YouTube transcripts (yt-dlp)
- Transcripts are stored in `inbox/` as `.vtt` files
- On Go, the transcript feeds into the bundle in `raw/` and olw compiles a page (via `.drafts/` and review) covering:
  - Title, speaker, channel, date, URL
  - Summary (3–5 sentences)
  - Key points with timestamps
  - Relevant quotes (with timestamp)
  - Links to related pages in the wiki
- Add a #tag `#video` for the source type
- Delete raw `.vtt` files from `inbox/` after the bundle has been created

## Zotero database maintenance
- The semantic search database must be updated periodically after adding new papers
- Remind the user to update the database if more than a week has passed since the last update, or if searches are missing recent additions
- Use the command `update-zotero` (alias) or `zotero-mcp update-db --fulltext` for a full update
- Check the status with `zotero-status` or `zotero-mcp db-status`

## Podcast transcripts (whisper.cpp + yt-dlp)
- Audio is downloaded via yt-dlp and stored in `inbox/` as `.mp3`
- Transcription runs locally via whisper.cpp (fully offline)
- Whisper detects the language automatically; only pass `--language` explicitly if automatic detection is incorrect
- On Go, the transcript feeds into the bundle in `raw/` and olw compiles a page (via `.drafts/` and review) covering:
  - Title, speaker(s), program/channel, date, URL or source reference
  - Summary (3–5 sentences)
  - Key points with timestamps
  - Relevant quotes (with timestamp, in the original language)
  - Links to related pages in the wiki
- Add a #tag `#podcast` for the source type
- For long podcasts (> 45 min): first create a layered summary (overview → per segment)
- Delete raw `.mp3` and `.txt` files from `inbox/` after the bundle has been created

## RSS feeds
- All RSS feeds (academic and non-academic) are followed via NetNewsWire
- Academic articles of interest: add them to Zotero via the browser extension or iOS app → they end up in `_inbox`
- Non-academic articles: add via Zotero Connector or the iOS app — all sources enter the vault via Zotero `_inbox`
```
