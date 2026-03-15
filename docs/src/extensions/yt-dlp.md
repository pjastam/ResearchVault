# Step 10: yt-dlp & semantic search

## 10a. Install yt-dlp (YouTube transcripts)

With yt-dlp you can retrieve transcripts from YouTube videos and store them as sources in your vault. This is useful for lectures, conference recordings, interviews, and other academic video content.

### Install

```bash
brew install yt-dlp
```

Verify the installation:

```bash
yt-dlp --version
```

### Retrieve a transcript

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

### Integrating into the vault workflow

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

### Multiple videos at once (search results)

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

---

## 10b. Better semantic embeddings (optional)

The default local model (`all-MiniLM-L6-v2`) is free and fast. If you want better search results and are willing to use an OpenAI API key exclusively for embeddings (not for text generation):

```bash
zotero-mcp setup --semantic-config-only
```

Then choose `openai` as the embedding model and enter your API key. Afterwards, reinitialize the database:

```bash
zotero-mcp update-db --fulltext --force-rebuild
```

---

## 10c. Automatic database updates

Every time you add new papers to Zotero, the semantic search database must be updated in order to find those papers. You can do this manually, but automation is more convenient.

### Option 1: Via the Zotero MCP setup wizard (simplest)

```bash
zotero-mcp setup --semantic-config-only
```

For the update frequency, choose **"Daily"** or **"Auto on startup"**. With "Auto on startup" the database is updated every time Claude Code calls Zotero MCP — this is the most hands-off approach.

> **About "unknown" as model name:** After running `zotero-mcp setup-info`, the embedding model name may be displayed as `unknown`. This is normal behavior: the default local model (`all-MiniLM-L6-v2`) is used, but the name is not reported back by setup-info. Your installation is working fine. Verification is done not via the terminal but via Claude Code: after running `zotero-mcp update-db`, ask Claude Code to semantically search for a term that exists in your library. If that returns results, the database is working correctly.

### Option 2: Handy alias in your shell profile

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

### Option 3: Automated via macOS launchd (background task)

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
