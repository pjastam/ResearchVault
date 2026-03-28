# Privacy overview

| Component | Data local? | Notes |
|---|---|---|
| Zotero + local API | ✅ Fully | Runs on `localhost`, no cloud |
| Zotero MCP | ✅ Fully | Local connection; write operations use Zotero web API with your own key |
| Obsidian vault | ✅ Fully | Regular files on your Mac |
| Ollama + Qwen3.5:9b | ✅ Fully | Model runs locally on M4; default for all generative tasks |
| yt-dlp | ✅ Fully | Scraping executed locally |
| whisper.cpp | ✅ Fully | Transcription locally on M4 via Metal |
| NetNewsWire | ✅ Fully | RSS data stored locally, no account |
| Obsidian Spaced Repetition | ✅ Fully | Cards and review data in vault files |
| Claude Code — orchestration | ⚠️ Partially | Workflow instructions and metadata go to the Anthropic API; **source content must not** |
| Claude Code — `--hd` mode | ⚠️ Partially | Only on explicit `--hd` request: prompt and source content go to Anthropic API (Claude Sonnet 4.6) |

## The content privacy rule

The most important privacy boundary in this workflow is not which tools you use — it is **whether source content appears in Claude Code's context**.

Claude Code communicates with the Anthropic API in every session. This is unavoidable: it is how the orchestration layer works. What you can control is whether the *content* of your papers, transcripts, or articles gets included in that communication.

**The rule:** source content (full text of papers, article HTML, transcripts) must never be returned as output of a Bash command. The moment text appears as tool output, it has reached the Anthropic API.

**The safe pipeline:**

```bash
# 1. Fetch full text and write to file — only length/status is printed
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/fetch-fulltext.py ITEMKEY inbox/bron.txt

# 2. Generate note via Ollama REST API — content stays local
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/ollama-generate.py \
  --input inbox/bron.txt \
  --output literature/notitie.md \
  --prompt "..."

# 3. Remove source file
rm inbox/bron.txt
```

What goes to the Anthropic API in this pipeline: only the prompt instruction and metadata (title, authors, year). What stays local: the full content of the paper or transcript.

**What this means in practice:**

- `fetch-fulltext.py` writes the Zotero attachment text to a local file and prints only `Saved: inbox/bron.txt (12,345 chars)`.
- `ollama-generate.py` calls the Ollama REST API directly (no CLI, no ANSI codes) and writes the result to the output file.
- Neither tool prints source content to the terminal or to Claude Code's context.

> **Conclusion:** in the default mode, no paper content, transcript, or note text leaves the Mac mini. Claude Code orchestrates the workflow (instructions go to Anthropic), but all generative work runs locally via Qwen3.5:9b. Only when you explicitly request `--hd` does source content go to the Anthropic API — Claude Code always asks for confirmation first.
