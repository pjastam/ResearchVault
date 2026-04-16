# Troubleshooting

| Problem | Possible cause | Solution |
|---|---|---|
| Zotero MCP returns no results | Zotero is not open | Start Zotero and check `http://localhost:23119/` |
| Local API not available | Setting not checked | Zotero → Settings → Advanced → enable local API |
| `zotero-mcp` not found | uv path not in shell | Add `~/.local/bin` to `$PATH` in `~/.zshrc` |
| Semantic search returns no results | Database not initialized | Run `zotero-mcp update-db` |
| Claude Code does not see the MCP tool | Configuration file missing | Check `~/.claude/claude_desktop_config.json` |
| Ollama not responding | Service not started | Run `ollama serve` or `brew services start ollama` |
| yt-dlp returns no subtitles | Video has no (auto-)subtitles | Try `--sub-lang en` or check whether the video has subtitles at all |
| launchd update not running | Nightly daemon did not fire (check `~/Library/Logs/nachtelijke-taken.log`) | Run `update-zotero` manually; verify the daemon is loaded with `sudo launchctl list \| grep nachtelijke` |
| whisper-cpp gives an error | Model not yet downloaded | Wait for the first download, or check disk space |
| Whisper transcription is inaccurate | Low audio quality or incorrect language detection | Use `--model medium` for better quality, or specify the language explicitly with `--language nl` or `--language en` if automatic detection picks the wrong language |
| NetNewsWire not syncing across devices | FreshRSS account not connected | Add FreshRSS account in NetNewsWire → Settings → Accounts → FreshRSS; use API URL `http://[mac-ip]:8080/api/greader.php` and the API password from FreshRSS Profile → API Management |
| FreshRSS container not running | Docker Desktop not started | Open Docker Desktop from Launchpad; verify with `docker ps` |
| feedreader HTML reader not loading | feedreader-server.py not running | Check with `sudo launchctl list \| grep feedreader`; restart with `sudo launchctl kickstart system/nl.researchvault.feedreader-server` |
| Action buttons (✅/📖/👎) in NNW don't work | JavaScript not enabled | NetNewsWire → Settings → Article Content → enable "Enable JavaScript" |
| Action buttons give no result | ZOTERO_API_KEY not set | Add `export ZOTERO_API_KEY="..."` to `~/.zprofile` and restart the feedreader-server agent |
| ttyd terminal button not working | ttyd not running | Check with `sudo launchctl list \| grep ttyd`; verify port 7681 is open |
| Obsidian flashcards not appearing | Plugin not enabled | Settings → Community Plugins → enable Spaced Repetition |
| Flashcards not recognized | Incorrect format | Check that `?` is on its own line and `#flashcard` is present |
