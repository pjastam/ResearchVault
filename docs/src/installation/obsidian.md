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
├── literature/          ← summaries of Zotero papers, YouTube and podcasts
│   └── annotations/     ← extracted PDF annotations
├── syntheses/           ← thematic cross-connections
├── projects/            ← per project or collaboration
├── daily/               ← daily notes
├── flashcards/          ← spaced repetition cards (optional, separate from literature/)
└── inbox/               ← raw input, yet to be processed
```

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
- `literature/` — one note per paper or source from Zotero
- `syntheses/` — thematic syntheses of multiple sources
- `projects/` — project-specific documentation
- `daily/` — daily notes and log
- `inbox/` — raw input yet to be processed

## Literature notes (from Zotero)
Each literature note contains:
- Bibliographic details (author, year, journal)
- Core question and main argument
- Key findings (3–5 points)
- Methodological notes
- Quotes relevant to my research
- Links to related notes in the vault

## Language
- Answer in English unless asked otherwise
- Write literature notes in English, quotes in the original language

## Zotero workflow
- Use Zotero MCP to retrieve papers by title or keywords
- Save literature notes as `literature/[author-year-keyword].md`
- Always add a #tag for the topic of the paper

## YouTube transcripts (yt-dlp)
- Transcripts are stored in `inbox/` as `.vtt` files
- Process a transcript into a note in `literature/` with the following structure:
  - Title, speaker, channel, date, URL
  - Summary (3–5 sentences)
  - Key points with timestamps
  - Relevant quotes (with timestamp)
  - Links to related notes in the vault
- File name for transcript notes: `[speaker-year-keyword].md` with #tag `#video`
- Delete raw `.vtt` files from `inbox/` after the note has been created

## Zotero database maintenance
- The semantic search database must be updated periodically after adding new papers
- Remind the user to update the database if more than a week has passed since the last update, or if searches are missing recent additions
- Use the command `update-zotero` (alias) or `zotero-mcp update-db --fulltext` for a full update
- Check the status with `zotero-status` or `zotero-mcp db-status`

## Podcast transcripts (whisper.cpp + yt-dlp)
- Audio is downloaded via yt-dlp and stored in `inbox/` as `.mp3`
- Transcription runs locally via whisper.cpp (fully offline)
- Whisper detects the language automatically; only pass `--language` explicitly if automatic detection is incorrect
- Process a transcript into a note in `literature/` with the following structure:
  - Title, speaker(s), program/channel, date, URL or source reference
  - Summary (3–5 sentences)
  - Key points with timestamps
  - Relevant quotes (with timestamp, in the original language)
  - Links to related notes in the vault
- File name for podcast notes: `[speaker-year-keyword].md` with #tag `#podcast`
- For long podcasts (> 45 min): first create a layered summary (overview → per segment)
- Delete raw `.mp3` and `.txt` files from `inbox/` after the note has been created

## RSS feeds
- All RSS feeds (academic and non-academic) are followed via NetNewsWire
- Academic articles of interest: add them to Zotero via the browser extension or iOS app → they end up in `_inbox`
- Non-academic articles: add via Zotero Connector or the iOS app — all sources enter the vault via Zotero `_inbox`

## Spaced repetition (Obsidian plugin)
- Flashcards are created after each literature note or synthesis
- Format: question and answer separated by `?` on a new line, enclosed by `#flashcard` tag
- Create a maximum of 5 cards per source — choose the most relevant concepts
- Daily review via Obsidian Spaced Repetition plugin (sidebar → Review cards)
```
