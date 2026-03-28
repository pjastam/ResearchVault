# Step 6: Install Ollama

## Local vs. cloud — what happens where?

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

## 6a. Install

```bash
brew install ollama
```

## 6b. Download models

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

## 6c. Start Ollama

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

## 6d. How Ollama is used in the workflow

Qwen3.5:9b is the default engine for all generative tasks. The workflow uses a dedicated helper script — `.claude/ollama-generate.py` — to call Ollama via its REST API rather than the CLI.

**Why a helper script instead of `ollama run`?**

The Ollama CLI (`ollama run qwen3.5:9b < file.txt`) produces terminal output with ANSI escape codes and a loading spinner. When this output is captured by Claude Code's bash tool, the result contains hundreds of lines of control characters that need to be stripped before the content is usable. The helper script avoids this entirely by talking directly to the Ollama REST API at `http://localhost:11434/api/generate`.

The script also prepends `/no_think` to the prompt, which tells Qwen3.5:9b to skip its internal reasoning step and produce output directly. This saves time and keeps the output clean.

**Usage:**

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/ollama-generate.py \
  --input  inbox/source.txt \
  --output literature/note.md \
  --prompt "Write a literature note in the same language as the source text..."
```

The script prints only status lines (`Input: ...`, `Model: ...`, `Written: ...`) — never the source content or the generated text. This ensures source content does not appear in Claude Code's context.

**Test whether Ollama is reachable:**

```bash
echo "Test" > /tmp/test.txt
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/ollama-generate.py \
  --input /tmp/test.txt \
  --output /tmp/test-out.txt \
  --prompt "Say only: works."
cat /tmp/test-out.txt
```

If this returns a short response, Ollama and the helper script are ready for use.

**Default rule in CLAUDE.md**

The `CLAUDE.md` in your vault already contains the privacy rule and points to `ollama-generate.py` as the standard tool — no further configuration is needed per task.
