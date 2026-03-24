# Installation Guide: Local Research Workflow
## Claude Code + Zotero MCP + Obsidian + Ollama on macOS (M4)

**Goal:** Set up a fully local, privacy-friendly research workflow on a Mac mini M4 (2024), where Zotero, Claude Code, Obsidian, and Ollama work together without relying on external cloud services for your data. The workflow follows a **3-phase model**: capture broadly → filter → process.

**Estimated installation time:** 60–120 minutes
**Requirements:** macOS Sequoia or later, internet connection for downloads, an Anthropic account (for Claude Code)

---

## The 3-phase model

The workflow is built around three explicit phases — every source passes through all three:

| Phase                        | Goal                                        | Approach                                                                                                                                                                                  |
| --------------------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **1 — Cast wide**        | Low threshold, no filtering                | Each source has its own dump layer: Browser (Zotero Connector/iOS), NetNewsWire (RSS), Overcast (podcasts), YouTube (videos), Other (iOS share sheet) — everything flows together into Zotero `_inbox` |
| **2 — Filter**            | You decide what enters the vault             | `index-score.py` ranks inbox items by semantic similarity to your library; Qwen3.5:9b (local) generates a summary for mid-range items; you give a **Go** or **No-go**                                                          |
| **3 — Process** | Full processing of approved items | Claude Code writes a structured literature note to the Obsidian vault, including key findings, methodology notes, relevant quotes, and flashcards for spaced repetition                                                                                                                                               |

The distinction between phase 1 and phase 3 prevents your vault from being polluted with material that seemed interesting at the moment of capture but turns out to be irrelevant on reflection.

---

## Overview of steps

1. Install Homebrew (package manager)
2. Install and configure Zotero 7 **(including `_inbox` collection)**
3. Set up Python environment
4. Install and configure Zotero MCP
5. Install Claude Code
6. Install Ollama (local language model)
7. Install Obsidian and create vault
8. Connect everything: configure Claude Code with MCP
9. Run first test
10. Optional extensions (yt-dlp, semantic search, automatic updates)
11. Podcast integration (whisper.cpp)
12. RSS integration (Zotero feeds + NetNewsWire)
13. Spaced repetition (Obsidian plugin)
14. Set up filter layer per source
15. Future perspective — local orchestrator

---

## Step 1: Install Homebrew

Homebrew is the standard package manager for macOS and simplifies the installation of all further tools.

Open Terminal (found via Spotlight: `Cmd + Space` → type "Terminal") and run the following command:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Follow the on-screen instructions. After installation, add Homebrew to your shell path (the installation script shows this command at the end — copy and run it).

Verify the installation was successful:

```bash
brew --version
```

---

## Step 2: Install and configure Zotero 7

### 2a. Download Zotero

Download Zotero 7 via [zotero.org](https://www.zotero.org/download/). Install the application by opening the `.dmg` and dragging Zotero to your Applications folder.

### 2b. Enable the local API

This is the crucial step that makes Zotero MCP possible:

1. Open Zotero
2. Go to **Zotero → Settings → Advanced** (or `Cmd + ,`)
3. Scroll down to the **Other** section
4. Check the box next to **"Allow other applications on this computer to communicate with Zotero"**
5. Note the port number that appears (default: `23119`)

> **Privacy note:** This API is only accessible via `localhost` — no external access is possible.

### 2c. Verify the local API is working

Open a new tab in your browser and go to:

```
http://localhost:23119/
```

You should see a JSON response with version information from Zotero. If that works, the local API is functioning correctly.

### 2d. Create `_inbox` collection (central collection bucket)

In the 3-phase model, Zotero's `_inbox` collection is not a source in itself, but the central collection bucket where all sources flow: documents via the Zotero Connector or iOS app, RSS items via NetNewsWire, podcasts and videos via the Zotero iOS share sheet, and emails or notes via the iOS share button. You evaluate the content only in phase 2 (see step 14).

1. In Zotero, right-click **My Library** → **New Collection**
2. Name the collection `_inbox` (the underscore ensures it appears at the top of the list)
3. Set this as the default destination in the Zotero Connector: open the browser extension → **Settings** → set the default collection to `_inbox`
4. Set the same default on iOS: open the Zotero app → **Settings** → set the default collection location to `_inbox`

From now on, everything you save via the Connector or the iOS share sheet automatically goes to `_inbox`. You can also create a note directly within the Zotero app itself — it also ends up in `_inbox` if you have set that as the default.

### 2e. Install Better BibTeX plugin (recommended)

Better BibTeX significantly improves annotation extraction:

1. Download the latest `.xpi` from [retorque.re/zotero-better-bibtex/installation](https://retorque.re/zotero-better-bibtex/installation/)
2. In Zotero: **Tools → Plugins → Gear icon → Install from file**
3. Select the downloaded `.xpi` file
4. Restart Zotero

---

## Step 3: Set up Python environment

Zotero MCP requires Python 3.10 or higher. On Apple Silicon, `uv` works best as a fast, modern package manager.

### 3a. Install uv (recommended)

```bash
brew install uv
```

Verify the installation:

```bash
uv --version
```

### 3b. Check Python version

```bash
python3 --version
```

If the version is lower than 3.10, install a newer version:

```bash
brew install python@3.12
```

---

## Step 4: Install and configure Zotero MCP

### 4a. Install the package

```bash
uv tool install zotero-mcp-server
```

Verify the installation was successful:

```bash
zotero-mcp version
```

### 4b. Run the setup wizard

```bash
zotero-mcp setup
```

The wizard asks you a number of questions:

- **Access method:** choose `local` (no API key needed, fully offline)
- **MCP client:** choose `Claude Desktop` if you plan to install it later, or skip
- **Semantic search:** you can skip this now and configure it later (see step 10)

### 4c. Initialize semantic search

Build the local search database (uses the free, locally running model `all-MiniLM-L6-v2`):

```bash
# Quick version (metadata only):
zotero-mcp update-db

# Extended version (including full text — recommended):
zotero-mcp update-db --fulltext
```

> **Note:** The `--fulltext` option takes longer but gives much better search results. On an M4 Mac mini with an average-sized library this takes 5–20 minutes.

Check the status of the database:

```bash
zotero-mcp db-status
```

---

## Step 5: Install Claude Code

### 5a. Install Node.js

```bash
brew install node
```

### 5b. Install Claude Code

```bash
npm install -g @anthropic-ai/claude-code
```

### 5c. Authenticate

```bash
claude
```

On first launch you will be asked to log in with your Anthropic account. Follow the instructions in the terminal.

---

## Step 6: Install Ollama (local language model)

### Local vs. cloud — what happens where?

It is important to understand what runs locally in this workflow and what goes through the cloud:

| Step | Where | Notes |
|------|------|-------------|
| Zotero MCP (querying library) | ✅ Local | Connection via `localhost` |
| yt-dlp (fetching transcripts) | ✅ Local | Scraping on your Mac |
| whisper.cpp (transcribing audio) | ✅ Local | M4 Metal GPU |
| Semantic search (Zotero MCP) | ✅ Local | Local vector database |
| **Reasoning, summarizing, writing syntheses** | ✅ **Local** | Qwen3.5:9b via Ollama (default); Anthropic API only when `--hd` is used |

In the default mode, all generative work — summaries, literature notes, flashcards — is handled locally by Qwen3.5:9b via Ollama. Claude Code orchestrates the workflow but does not send source content to the Anthropic API. No tokens, no data transfer.

**The honest trade-off:** local models are less capable than Claude Sonnet for complex or nuanced tasks. For simple summaries and flashcards the difference is small; for writing rich literature notes or drawing subtle connections between sources, Claude Sonnet is noticeably better. Add `--hd` to any request to switch to Claude Sonnet 4.6 via the Anthropic API for that task — Claude Code always announces this and asks for confirmation before making the API call.

---

### 6a. Install

```bash
brew install ollama
```

### 6b. Download models

For an M4 Mac mini with 24 GB memory, **Qwen3.5:9b** is the recommended default model for all local processing tasks in the workflow:

```bash
ollama pull qwen3.5:9b   # ~6.6 GB — default model for all tasks
```

Qwen3.5:9b has a context window of 256K tokens, recent training with explicit attention to multilingualism (201 languages, including Dutch), and a hybrid architecture that stays fast even with long input. It replaces both llama3.1:8b and mistral for all workflow tasks.

```bash
# Optional alternatives (not needed if you use qwen3.5:9b):
ollama pull llama3.1:8b   # ~4.7 GB — proven, but 128K context and less multilingual
ollama pull phi3           # ~2.3 GB — very compact, for systems with less memory
```

Check which models are available after downloading:

```bash
ollama list
```

### 6c. Start Ollama

```bash
ollama serve
```

Leave this running in a separate Terminal window, or configure it as a background service so it is always available:

```bash
# Start automatically at system startup (recommended):
brew services start ollama
```

Check whether Ollama is active and which models are available:

```bash
ollama list
```

### 6d. How Ollama is used in the workflow

Qwen3.5:9b is the default engine for all generative tasks. Claude Code calls Ollama via its bash tool whenever it needs to generate a summary, write a literature note, or create flashcards. No explicit configuration is needed per task — the CLAUDE.md in your vault already sets this as the default.

**Option 1: Verify per task (if needed)**

To confirm that a specific task runs locally, you can instruct Claude Code explicitly:

```
Use Ollama (qwen3.5:9b) to create a summary of this transcript.
Call the model via: ollama run qwen3.5:9b
```

Claude Code runs the command locally via the bash tool and processes the output without making an Anthropic API call for that step.

**Option 2: Default rule in CLAUDE.md**

The starter `CLAUDE.md` from step 7d already contains the following section — no further action needed. It instructs Claude Code to use Ollama by default for all processing tasks:

```markdown
## Local processing via Ollama

By default, all processing runs locally via Qwen3.5:9b. Use this for:
- Literature notes based on papers or transcripts
- Thematic syntheses
- Flashcard generation

Call Ollama via the bash tool:
`ollama run qwen3.5:9b < inbox/[filename].txt`

**Maximum quality mode:** if the user adds `--hd` or explicitly asks for "maximum quality" or "use Sonnet", switch to Claude Sonnet 4.6 via the Anthropic API. Always announce this first and wait for confirmation before making the API call. Never automatically fall back to Sonnet if Qwen is unreachable — report that Ollama is not active and ask what the user wants.
```

**Option 3: Test whether Ollama is reachable**

Verify from Claude Code that Ollama is active and processes a test prompt:

```bash
ollama run qwen3.5:9b "Give a three-sentence summary about substitution care."
```

If this returns a response, Ollama is ready for use from Claude Code.

---

## Step 7: Install Obsidian and create vault

### 7a. Download Obsidian

Download Obsidian via [obsidian.md](https://obsidian.md). Install the application in the usual way.

### 7b. Create a vault

1. Open Obsidian
2. Choose **"Create new vault"**
3. Give the vault a name, e.g. `ResearchVault`
4. Choose a location you will remember, e.g. `~/Documents/ResearchVault`
5. Click **"Create"**

### 7c. Create folder structure

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

### 7d. Create CLAUDE.md

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
- Non-academic articles: add via Zotero Connector, or pass the URL with `inbox [URL]` for direct storage as Markdown in `inbox/`
- File name for RSS items without a Zotero record: `[source-year-keyword].md` with #tag `#web` or `#policy`

## Spaced repetition (Obsidian plugin)
- Flashcards are created after each literature note or synthesis
- Format: question and answer separated by `?` on a new line, enclosed by `#flashcard` tag
- Create a maximum of 5 cards per source — choose the most relevant concepts
- Daily review via Obsidian Spaced Repetition plugin (sidebar → Review cards)
```

---

## Step 8: Connect Claude Code to Zotero MCP

### 8a. Edit the configuration file

Claude Code reads the MCP configuration from `~/Library/Application Support/Claude/claude_desktop_config.json`. This is the same location used by Claude Desktop. Create or edit this file:

```bash
mkdir -p ~/Library/Application\ Support/Claude
nano ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

Insert the following (or add the `zotero` section to an existing file):

```json
{
  "mcpServers": {
    "zotero": {
      "command": "zotero-mcp",
      "env": {
        "ZOTERO_LOCAL": "true"
      }
    }
  }
}
```

Save with `Ctrl + O`, `Enter`, then `Ctrl + X`.

### 8b. Verify the MCP configuration

```bash
zotero-mcp setup-info
```

This shows the installation path and the configuration as Zotero MCP sees it. Note down the **userID** shown — you will need it in the next step.

### 8c. Configure Claude Code permissions

Claude Code's permission settings for this vault are stored in `.claude/settings.local.json`. This file contains your home path and Zotero library ID, so it is not checked into version control. Generate it from the template using the setup script:

```bash
cd ~/Documents/ResearchVault
./setup.sh
```

The script:
1. Auto-detects your home path
2. Asks for your Zotero library ID (the userID from `zotero-mcp setup-info`)
3. Writes `.claude/settings.local.json` with the correct paths

> **Note:** If you ever move your vault or reinstall tools, re-run `./setup.sh` to regenerate the file.

---

## Step 9: Run first test

### 9a. Start Zotero

Make sure Zotero 7 is open and active (the local API is only available when Zotero is running).

### 9b. Open Claude Code in your vault

```bash
cd ~/Documents/ResearchVault
claude
```

### 9c. Run test prompts

Try the following prompts in Claude Code to verify everything works:

**Test 1 — Zotero connection:**
```
Search my Zotero library for recent additions and give an overview.
```

**Test 2 — Retrieve a paper:**
```
Find a paper about [a topic you have in Zotero] and write a literature note
to literature/ in Obsidian format.
```

**Test 3 — Semantic search:**
```
Use semantic search to find papers that are conceptually related to [topic].
```

**Test 4 — Vault awareness:**
```
Look at the structure of this vault and give a summary of what is already in it.
```

If all four tests work, the basic installation is complete.

---

## Step 10: Optional extensions

### 10a. Install yt-dlp (YouTube transcripts)

With yt-dlp you can retrieve transcripts from YouTube videos and store them as sources in your vault. This is useful for lectures, conference recordings, interviews, and other academic video content.

#### Install

```bash
brew install yt-dlp
```

Verify the installation:

```bash
yt-dlp --version
```

#### Retrieve a transcript

The basic command to download an automatically generated subtitle file:

```bash
yt-dlp --write-auto-sub --skip-download --sub-format vtt \
  "https://www.youtube.com/watch?v=VIDEOID" -o "transcript"
```

This creates a `.vtt` file in your current folder. The VTT format contains timestamps and is directly readable as text.

For videos where you want to retrieve manual subtitles if available (better quality than auto-generated):

```bash
# Retrieve manual subtitles (if available), otherwise automatic:
yt-dlp --write-sub --write-auto-sub --skip-download \
  --sub-lang nl,en --sub-format vtt \
  "https://www.youtube.com/watch?v=VIDEOID" -o "~/Documents/ResearchVault/inbox/%(title)s"
```

The flags `--write-sub --write-auto-sub` work the same way for all languages: yt-dlp takes manual subtitles if available, and falls back to auto-generated ones otherwise. `--sub-lang nl,en` requests both languages — useful for bilingual content. The `-o "...%(title)s"` option automatically uses the video title as the filename, so you know what you have saved.

#### Integrating into the vault workflow

Always save transcripts to `inbox/` and ask Claude Code to process them:

```bash
# Step 1: retrieve transcript to inbox
yt-dlp --write-auto-sub --skip-download --sub-format vtt \
  "https://www.youtube.com/watch?v=VIDEOID" \
  -o "~/Documents/ResearchVault/inbox/%(title)s"

# Step 2: open Claude Code in your vault
cd ~/Documents/ResearchVault
claude
```

Then give Claude Code the instruction:

```
Process the transcript in inbox/ into a structured note in literature/
with summary, key points, and timestamped quotes.
```

#### Multiple videos at once (search results)

You can also retrieve YouTube search results in batch. You do not need to type the command yourself: you can instruct Claude Code in plain language, for example:

```
Retrieve the first ten YouTube videos about "implementation care agreement Netherlands"
and save the transcripts to inbox/
```

Claude Code writes and runs the yt-dlp command itself. The underlying command looks like this:

```bash
# Retrieve the first 10 videos about a search term:
yt-dlp --write-auto-sub --skip-download --sub-format vtt \
  "ytsearch10:implementation care agreement Netherlands" \
  -o "~/Documents/ResearchVault/inbox/%(title)s"
```

> **Privacy note:** yt-dlp only connects to YouTube to download publicly available subtitle files. No personal data is sent and no account is required.

### 10b. Better semantic embeddings (optional)

The default local model (`all-MiniLM-L6-v2`) is free and fast. If you want better search results and are willing to use an OpenAI API key exclusively for embeddings (not for text generation):

```bash
zotero-mcp setup --semantic-config-only
```

Then choose `openai` as the embedding model and enter your API key. Afterwards, reinitialize the database:

```bash
zotero-mcp update-db --fulltext --force-rebuild
```

### 10c. Automatic database updates

Every time you add new papers to Zotero, the semantic search database must be updated in order to find those papers. You can do this manually, but automation is more convenient.

#### Option 1: Via the Zotero MCP setup wizard (simplest)

```bash
zotero-mcp setup --semantic-config-only
```

For the update frequency, choose **"Daily"** or **"Auto on startup"**. With "Auto on startup" the database is updated every time Claude Code calls Zotero MCP — this is the most hands-off approach.

> **About "unknown" as model name:** After running `zotero-mcp setup-info`, the embedding model name may be displayed as `unknown`. This is normal behavior: the default local model (`all-MiniLM-L6-v2`) is used, but the name is not reported back by setup-info. Your installation is working fine. Verification is done not via the terminal but via Claude Code: after running `zotero-mcp update-db`, ask Claude Code to semantically search for a term that exists in your library. If that returns results, the database is working correctly.

#### Option 2: Handy alias in your shell profile

Add an alias so you can update the database with a single command:

```bash
# Open your shell configuration file:
nano ~/.zshrc
```

Add at the bottom:

```bash
# Zotero MCP helper commands
alias update-zotero="zotero-mcp update-db --fulltext"
alias zotero-status="zotero-mcp db-status"
```

Activate the changes:

```bash
source ~/.zshrc
```

After that, you can always simply type:

```bash
update-zotero
```

#### Option 3: Automated via macOS launchd (background task)

For fully automatic daily updates you can set up a macOS launchd task. Create a new file:

```bash
nano ~/Library/LaunchAgents/com.zotero-mcp.update.plist
```

Paste the following:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.zotero-mcp.update</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/sh</string>
    <string>-c</string>
    <string>zotero-mcp update-db --fulltext >> ~/Documents/ResearchVault/zotero-mcp-update.log 2>&1</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>8</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>RunAtLoad</key>
  <false/>
</dict>
</plist>
```

This runs a database update daily at 08:00 and saves the log to your vault. Activate the task:

```bash
launchctl load ~/Library/LaunchAgents/com.zotero-mcp.update.plist
```

> **Note:** For the launchd option, Zotero must be open at the time the update runs. If your Mac is in sleep mode at that time, the task will be skipped until the next day.

---

## Step 11: Podcast integration (whisper.cpp)

With whisper.cpp you can transcribe podcasts and other audio recordings entirely locally on your M4 Mac mini. The M4 chip executes this via Metal (the GPU) extremely fast: one hour of audio takes approximately 3–5 minutes.

### 11a. Install whisper.cpp

```bash
brew install whisper-cpp
```

Verify the installation:

```bash
whisper-cpp --version
```

### 11b. Download and transcribe a podcast

yt-dlp supports many podcast platforms beyond YouTube (SoundCloud, Podbean, direct MP3 links via RSS). The full pipeline in two steps:

```bash
# Step 1: download audio to inbox/
yt-dlp -x --audio-format mp3 \
  "https://[podcast-url]" \
  -o "~/Documents/ResearchVault/inbox/%(title)s.%(ext)s"

# Step 2: transcribe — whisper detects the language automatically
whisper-cpp --model small \
  ~/Documents/ResearchVault/inbox/[filename].mp3
```

This creates a `.txt` and a `.vtt` file alongside the `.mp3`. The `.txt` file contains the transcription without timestamps; the `.vtt` file contains timestamps per segment.

**Language**

Whisper detects the language automatically based on the first few seconds of audio. For most monolingual podcasts (Dutch or English) this works fine and you do not need to configure anything. Only pass `--language` explicitly if you encounter problems, for example with multilingual content or if automatic detection picks the wrong language:

```bash
# Only needed if detection fails:
whisper-cpp --model small --language nl ~/Documents/ResearchVault/inbox/[file].mp3
whisper-cpp --model small --language en ~/Documents/ResearchVault/inbox/[file].mp3
```

In the daily workflow, Claude Code lets the language be detected automatically based on metadata (podcast title, channel, description) and only passes `--language` explicitly if that metadata is unclear.

**Models and quality**

| Model | Size | Speed (1 hour audio) | Quality |
|---|---|---|---|
| `base` | ~145 MB | ~2 min | Good for clear speech |
| `small` | ~465 MB | ~4 min | Recommended starting point |
| `medium` | ~1.5 GB | ~8 min | Better for accents, fast speech |
| `large` | ~3 GB | ~15 min | Best quality |

Models are automatically downloaded on first use.

### 11c. Process in the vault

After the transcript is available in `inbox/`, open Claude Code in your vault:

```bash
cd ~/Documents/ResearchVault
claude
```

Give the instruction:

```
Process the podcast transcript in inbox/[filename].txt into a structured
note in literature/ with summary, key points, and timestamped quotes.
```

Claude Code follows the conventions from `CLAUDE.md` (see step 7d): title, speaker, summary, key points with timestamps, and links to related vault notes.

> **Privacy note:** whisper.cpp runs entirely locally on your M4. No audio leaves your machine.

### 11d. Shortcut: full pipeline in one step

You can also have Claude Code run the full pipeline with a single instruction:

```
podcast https://[url-to-episode]
```

Claude Code downloads the audio, automatically determines the language based on metadata, runs whisper.cpp, and processes the transcript into a literature note — see also the skill (step "activate skill"). The Zotero `_inbox` step is skipped: the podcast goes directly to Obsidian. This is intended for episodes you have already evaluated and approved.

---

## Step 12: RSS integration

In the 3-phase model, RSS readers are dump layers for phase 1: you subscribe to feeds without immediately judging whether each item is relevant. Only in phase 2 do you decide what goes into the vault.

### 12a. RSS feeds via NetNewsWire

NetNewsWire is a free, open-source RSS reader for macOS and iOS, with iCloud sync between both devices. It is the central dump layer for all RSS feeds — both academic and non-academic. This is especially true if you primarily work on iOS: the Zotero iOS app has no built-in RSS functionality, making NetNewsWire the most practical choice for all feeds.

**Install:**

```bash
brew install --cask netnewswire
```

Or download via [netnewswire.com](https://netnewswire.com).

**Recommended feeds:**
- Journal RSS (e.g. BMJ, NEJM, TSG)
- PubMed searches as RSS feed
- Policy sites and government newsletters
- Trade blogs and opinion pieces on health policy (e.g. Zorgvisie, Skipr)
- Substack publications by relevant authors (each has an RSS feed via `[name].substack.com/feed`)

**Useful RSS URLs:**

```
# PubMed search as RSS (replace the search term):
https://pubmed.ncbi.nlm.nih.gov/rss/search/?term=[searchterm]&format=abstract

# Journal RSS (example BMJ):
https://www.bmj.com/rss/ahead-of-print.xml

# Google Scholar alerts (set up via email and forward, or via RSS-bridge)
```

> **Phase 1 → phase 2:** Items in NetNewsWire have not yet been saved — they only exist in your feed reader. This is intentional: you browse through them and scan headlines and intros without immediately archiving anything. Only what is truly relevant gets forwarded to the vault. That is the filter moment.

**From NetNewsWire to the vault (phase 2 → phase 3):**

Interesting articles are saved via two routes:

- **Via Zotero browser extension or iOS app:** open the article, click the Zotero icon → item is saved with metadata to Zotero `_inbox`. Use this route for academic articles where you want to retain BibTeX metadata and annotation capabilities.
- **Direct to `inbox/`:** pass the URL to Claude Code with the instruction `inbox [URL]` → Claude Code fetches the content and saves it as a Markdown file in `inbox/`, without Zotero. Use this route for non-academic articles, news items, and policy documents.

> **Privacy note:** NetNewsWire stores feed data locally. No reading habits are sent to external servers.

### 12b. Academic feeds: from NetNewsWire to Zotero

For academic articles from NetNewsWire, the recommended route is to always add them to Zotero first before having them processed. This way you have BibTeX metadata and annotation capabilities available:

1. Open the article from NetNewsWire in your browser
2. Click the Zotero icon in your browser (or use the Zotero iOS app) → item is saved to `_inbox`
3. Process from `_inbox` via type 0 → type 1 in the skill

---

## Step 13: Spaced repetition (Obsidian plugin)

The Obsidian Spaced Repetition plugin uses the SM-2 algorithm to schedule flashcards based on how well you know them. Cards are created in your Markdown files and reviewed within Obsidian.

### 13a. Install plugin

1. Open Obsidian
2. Go to **Settings → Community Plugins → Browse community plugins**
3. Search for "Spaced Repetition"
4. Install the plugin by Stephen Mwangi
5. Enable the plugin via the toggle

### 13b. Flashcard format

Cards are created in regular Markdown files using the `?` separator:

```markdown
#flashcard

What is the definition of substitution care?
?
Care that is moved from secondary to primary care, maintaining quality but at lower cost.

What are the three pillars of the Integrated Care Agreement?
?
1. Appropriate care
2. Regional collaboration
3. Digitalization and data exchange
```

Cards can be in the same file as the literature note or written to `flashcards/`. The recommended approach is to place cards **in the note itself**: this keeps the card connected to its context and source reference, and during review you can immediately see where a concept came from. The `flashcards/` folder is intended for standalone concept cards that are not tied to one specific source — for example definitions or principles you want to remember independently of a paper.

### 13c. Claude Code generates flashcards automatically

After creating a literature note, you can ask Claude Code to generate flashcards:

```
Create 3–5 flashcards for the literature note just created.
Use the Obsidian Spaced Repetition format with ? as separator.
```

Claude Code adds the cards to the end of the existing note (or writes them to `flashcards/[same name].md`).

### 13d. Daily review

1. Open Obsidian
2. Click the card icon in the right sidebar (or use `Cmd + Shift + R`)
3. Review the cards scheduled for today: **Easy / Good / Hard**
4. The plugin automatically schedules the next review based on your rating

> **Privacy note:** All cards and review data are stored as local files in your vault. No cloud sync is required.

---

## Step 14: Set up filter layer per source

This is the core of the 3-phase model: phase 2, the filter moment, is set up differently for each source. Below is a per-source overview of the dump layer, the filter moment, and how you indicate what may enter the vault.

### Papers (Zotero)

| Phase | What |
|------|-----|
| Dump layer | Zotero `_inbox` collection — central collection bucket for all sources |
| Filter moment | Run `index-score.py` to rank items by relevance; read abstract in Zotero, or have Claude Code summarize via Qwen3.5:9b (locally) |
| Go | Move item to the relevant collection in your library |
| No-go | Delete item from `_inbox` — no note is created |

**Tag-based filter logic**

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

Before starting your review, run `index-score.py` to get a ranked list sorted by relevance:

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/index-score.py
```

This ranks all `_inbox` items by semantic similarity to your existing library (using ChromaDB embeddings from zotero-mcp). Scores drive the treatment per item: 🟢 ≥70 skips the summary, 🟡 40–69 gets a Qwen summary, 🔴 <40 triggers an immediate No-go suggestion.

Claude Code can also help you with the evaluation — ask for a summary of items in `_inbox`:

```
Give me an overview of the items in my Zotero _inbox collection with a 2–3 sentence
summary per item and a relevance assessment for my research on [topic].
```

Claude Code retrieves the metadata and abstract via Zotero MCP and gives a recommendation per item. You then decide which items deserve the next step.

### YouTube videos

| Phase | What |
|------|-----|
| Dump layer | Zotero `_inbox` via iOS share sheet from the YouTube app |
| Filter moment | Watch the first 5–10 minutes, or have Claude Code summarize based on metadata |
| Go | `transcript [URL]` in Claude Code |
| No-go | Delete item from `_inbox` |

### Podcasts

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

### RSS feeds

| Phase | What |
|------|-----|
| Dump layer (academic and non-academic) | NetNewsWire — unread items |
| Filter moment | Scan headline and intro |
| Go (academic) | Open article → save to Zotero via browser extension or iOS app → ends up in `_inbox` |
| Go (non-academic) | Save via Zotero Connector, or pass `inbox [URL]` to Claude Code |
| No-go | Mark item as read or delete from NetNewsWire |

### Workflow overview at a glance

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../assets/architecture-diagram-v1.12-dark.svg">
  <img src="../assets/architecture-diagram-v1.12-light.svg" alt="Architecture diagram">
</picture>

---

## Activating the research workflow skill

The skill is a markdown file that tells Claude Code how to behave during research sessions. One-time installation:

```bash
# Create the skills folder in your vault
mkdir -p ~/Documents/ResearchVault/.claude/skills

# Copy the skill file to the vault
cp research-workflow-skill.md ~/Documents/ResearchVault/.claude/skills/
```

Then add the following line to your `CLAUDE.md` (at the bottom):

```markdown
## Active skills
- Read and follow `.claude/skills/research-workflow-skill.md` during every research session.
```

From that point on, the skill is active as soon as you open Claude Code in your vault. You can start the workflow by typing: `/research` or simply "start research workflow".

---

## Daily workflow after installation

Once everything is set up, the daily workflow is straightforward:

1. **Start Zotero** (so the local API is active)
2. **Open Terminal in your vault:** `cd ~/Documents/ResearchVault && claude`
3. **Activate the skill:** type `/research` or "start research workflow"
4. Claude Code asks an intake question and guides you interactively from there

You do not need to know exactly what you are looking for — the skill is designed to help you with that.

---

## Troubleshooting

| Problem | Possible cause | Solution |
|---|---|---|
| Zotero MCP returns no results | Zotero is not open | Start Zotero and check `http://localhost:23119/` |
| Local API not available | Setting not checked | Zotero → Settings → Advanced → enable local API |
| `zotero-mcp` not found | uv path not in shell | Add `~/.local/bin` to `$PATH` in `~/.zshrc` |
| Semantic search returns no results | Database not initialized | Run `zotero-mcp update-db` |
| Claude Code does not see the MCP tool | Configuration file missing | Check `~/.claude/claude_desktop_config.json` |
| Ollama not responding | Service not started | Run `ollama serve` or `brew services start ollama` |
| yt-dlp returns no subtitles | Video has no (auto-)subtitles | Try `--sub-lang en` or check whether the video has subtitles at all |
| launchd update not running | Zotero is not open at the scheduled time | Start Zotero manually and run `update-zotero`, or choose "Auto on startup" in step 10c option 1 |
| whisper-cpp gives an error | Model not yet downloaded | Wait for the first download, or check disk space |
| Whisper transcription is inaccurate | Low audio quality or incorrect language detection | Use `--model medium` for better quality, or specify the language explicitly with `--language nl` or `--language en` if automatic detection picks the wrong language |
| NetNewsWire not syncing | No sync configured (local always works) | NetNewsWire works locally by default; iCloud sync is optional |
| Obsidian flashcards not appearing | Plugin not enabled | Settings → Community Plugins → enable Spaced Repetition |
| Flashcards not recognized | Incorrect format | Check that `?` is on its own line and `#flashcard` is present |

---

## Privacy overview of the full stack

| Component | Data local? | Notes |
|---|---|---|
| Zotero + local API | ✅ Fully | Runs on `localhost`, no cloud |
| Zotero MCP | ✅ Fully | Local connection, no external API |
| Obsidian vault | ✅ Fully | Regular files on your Mac |
| Ollama + Qwen3.5:9b | ✅ Fully | Model runs locally on M4; default for all processing tasks |
| yt-dlp | ✅ Fully | Scraping executed locally |
| whisper.cpp | ✅ Fully | Transcription locally on M4 via Metal |
| NetNewsWire | ✅ Fully | RSS data stored locally, no account |
| Obsidian Spaced Repetition | ✅ Fully | Cards and review data in vault files |
| Claude Code — default | ✅ Fully | Orchestration and Zotero MCP calls; Qwen3.5:9b does the generative work locally |
| Claude Code — `--hd` mode | ⚠️ Partially | Only on explicit `--hd` request: prompt and source content go to Anthropic API (Claude Sonnet 4.6) |

> **Conclusion:** in the default mode, no vault content, paper, transcript, or note leaves the Mac mini. Claude Code orchestrates the workflow, but the reasoning and writing work happens locally via Qwen3.5:9b. Only when you explicitly request `--hd` or "maximum quality" does the source content go to the Anthropic API. Claude Code always asks for confirmation first.

---

## Step 15: Future perspective — local orchestrator

The only component in this stack that does not run fully locally is Claude Code as orchestrator. All generation tasks (summaries, literature notes, syntheses, flashcards) already run via Qwen3.5:9b on Ollama — fully local, fully private. What goes through the Anthropic API are the prompts with which Claude Code steers the workflow: the intake, the phase monitoring, the vault conventions, the iterative Go/No-go dialogue.

For those who also want to solve this layer locally, two serious candidates are emerging.

### Open WebUI + MCPO

Open WebUI is a self-hosted chat interface (similar to the Claude.ai interface, but local) that accesses local models via Ollama. From version 0.6.31 onwards it supports MCP natively. The MCPO proxy (Model Context Protocol to OpenAPI) translates stdio-based MCP servers — such as zotero-mcp — to HTTP endpoints that Open WebUI can call. The architecture fits directly onto the existing Mac mini M4 stack: Ollama keeps running, zotero-mcp is made available via MCPO, and Open WebUI acts as the conversational interface in the browser.

**Advantages:** mature interface, actively maintained, works on macOS without Docker, Qwen3.5:9b is compatible with tool use in this configuration.
**Disadvantages:** browser-based (no terminal workflow like Claude Code), the skill logic and vault conventions must be fully rewritten as a system prompt, no native filesystem integration without an additional MCP server.

### ollmcp (mcp-client-for-ollama)

ollmcp is a terminal interface (TUI) that connects Ollama models to multiple MCP servers simultaneously. It has an agent mode with iterative tool execution, human-in-the-loop controls, and model switching. The interface is closer to how Claude Code works — everything in the terminal, no browser. You can connect zotero-mcp, choose Qwen3.5:9b, and pass the skill as a system prompt.

**Advantages:** terminal-native, close to the current workflow, supports multiple MCP servers simultaneously, human-in-the-loop is built in.
**Disadvantages:** less mature than Open WebUI, writing vault files requires an additional filesystem MCP server, the skill logic must be rebuilt as a system prompt.

### Why this is not yet worth the effort

The orchestration layer that Claude Code provides is more than tool calls. It involves phase monitoring across a longer session, vault awareness (knowing what already exists and how it should be linked), the iterative Go/No-go dialogue per item, and reliable adherence to vault conventions across multiple steps. All of this logic currently lives in the skill and CLAUDE.md, and Claude Code follows it accurately.

With a local orchestrator, the same logic must be passed as a system prompt to Qwen3.5:9b. Instruction-following in complex multi-step workflows is noticeably less reliable with local models than with Claude Sonnet — not due to a lack of language capability, but because of consistency across multiple rounds and tools. The result is achievable, but requires considerable extra work for a less robust outcome.

This is also precisely why Claude Code structurally distinguishes itself as an orchestrator from local alternatives: not in raw generation quality (for which Qwen3.5:9b is already strong enough for most tasks), but in the reliability of workflow logic across phases and tools. Whether and when local models will reach this level is an open question. The landscape is changing fast — Open WebUI, ollmcp, and similar tools are actively in development and worth continuing to follow.

---

*Installation guide version 1.12 — March 2026*
*Tested on Mac mini M4 (2024), 24 GB, macOS Sequoia*
