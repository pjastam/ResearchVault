# Step 11: Podcast integration (whisper.cpp)

With whisper.cpp you can transcribe podcasts and other audio recordings entirely locally on your M4 Mac mini. The M4 chip executes this via Metal (the GPU) extremely fast: one hour of audio takes approximately 3–5 minutes.

## 11a. Install whisper.cpp

```bash
brew install whisper-cpp
```

Verify the installation:

```bash
whisper-cpp --version
```

## 11b. Download and transcribe a podcast

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

### Language

Whisper detects the language automatically based on the first few seconds of audio. For most monolingual podcasts (Dutch or English) this works fine and you do not need to configure anything. Only pass `--language` explicitly if you encounter problems, for example with multilingual content or if automatic detection picks the wrong language:

```bash
# Only needed if detection fails:
whisper-cpp --model small --language nl ~/Documents/ResearchVault/inbox/[file].mp3
whisper-cpp --model small --language en ~/Documents/ResearchVault/inbox/[file].mp3
```

In the daily workflow, Claude Code lets the language be detected automatically based on metadata (podcast title, channel, description) and only passes `--language` explicitly if that metadata is unclear.

### Models and quality

| Model | Size | Speed (1 hour audio) | Quality |
|---|---|---|---|
| `base` | ~145 MB | ~2 min | Good for clear speech |
| `small` | ~465 MB | ~4 min | Recommended starting point |
| `medium` | ~1.5 GB | ~8 min | Better for accents, fast speech |
| `large` | ~3 GB | ~15 min | Best quality |

Models are automatically downloaded on first use.

## 11c. Process in the vault

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

## 11d. Shortcut: full pipeline in one step

You can also have Claude Code run the full pipeline with a single instruction:

```
podcast https://[url-to-episode]
```

Claude Code downloads the audio, automatically determines the language based on metadata, runs whisper.cpp, and processes the transcript into a literature note — see also the skill (step "activate skill"). The Zotero `_inbox` step is skipped: the podcast goes directly to Obsidian. This is intended for episodes you have already evaluated and approved.
