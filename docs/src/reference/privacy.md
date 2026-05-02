# Privacy overview

| Component | Data local? | Notes |
|---|---|---|
| Zotero + local API | ✅ Fully | Runs on `localhost`, no cloud |
| Zotero MCP + Web API | ⚠️ Partially | Read operations local; removing items from `_inbox` uses the Zotero Web API — item metadata (URL, title, type) goes to zotero.org |
| Obsidian vault | ✅ Fully | Regular files on your Mac |
| Ollama + Qwen3.5:9b | ✅ Fully | Model runs locally on M4; default for all generative tasks |
| yt-dlp | ✅ Fully | Scraping executed locally |
| whisper.cpp | ✅ Fully | Transcription locally on M4 via Metal |
| NetNewsWire | ✅ Fully | RSS data stored locally, no account |
| FreshRSS (Docker) | ✅ Fully | Self-hosted on Home Assistant Green (always-on); read/unread sync stays on your Tailscale network |
| feedreader (score/server/learn) | ✅ Fully | Runs locally; scoring uses local ChromaDB embeddings |
| ttyd | ✅ Fully | Browser terminal runs locally on Mac mini |
| Obsidian Spaced Repetition | ✅ Fully | Cards and review data in vault files |
| Claude Code — orchestration | ⚠️ Partially | Workflow instructions and metadata go to the Anthropic API; **source content must not** |
| Claude Code — `--hd` mode | ⚠️ Partially | Only on explicit `--hd` request: prompt and source content go to Anthropic API (Claude Sonnet 4.6) |

## The content privacy rule

The most important privacy boundary in this workflow is not which tools you use — it is **whether source content appears in Claude Code's context**.

Claude Code communicates with the Anthropic API in every session. This is unavoidable: it is how the orchestration layer works. What you can control is whether the *content* of your papers, transcripts, or articles gets included in that communication.

**The rule:** source content (full text of papers, article HTML, transcripts) must never be returned as output of a Bash command. The moment text appears as tool output, it has reached the Anthropic API.

**The safe pipeline — single subagent call:**

```bash
# One command: fetch, generate, prepend frontmatter, clean up — only JSON status returned
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/process_item.py \
  --item-key ITEMKEY \
  --title "Title of paper" \
  --authors "Smith, John" \
  --year 2024 \
  --citation-key smith2024keyword \
  --zotero-url "zotero://select/library/1/items/ITEMKEY" \
  --tags "health-economics" \
  --status unread
# → {"status": "ok", "path": "literature/smith2024keyword.md"}
```

What goes to the Anthropic API in this pipeline: only the item key and metadata (title, authors, year, tags). What stays local: the full text, the Qwen3.5:9b generation, the note body, and the final `.md` file.

**What `process_item.py` does internally (all local):**

1. `fetch-fulltext.py` — fetches the Zotero attachment and writes it to `inbox/_tmp_ITEMKEY.txt`; prints only file size and status.
2. `ollama-generate.py` — calls the Ollama REST API directly (no CLI, no ANSI codes), generates the note body, writes to a temp file.
3. Frontmatter is built from the metadata arguments and prepended to the note body.
4. The final note is written to `literature/[citation-key].md`.
5. Temp files in `inbox/` are removed.

Neither tool ever prints source content to the terminal or to Claude Code's context. Claude Code only sees the JSON status object.

> **Conclusion:** in the default mode, no paper content, transcript, or note text leaves the Mac mini. Claude Code orchestrates the workflow (instructions go to Anthropic), but all generative work runs locally via Qwen3.5:9b. Only when you explicitly request `--hd` does source content go to the Anthropic API — Claude Code always asks for confirmation first.
