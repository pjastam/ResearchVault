# Privacy overview

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
