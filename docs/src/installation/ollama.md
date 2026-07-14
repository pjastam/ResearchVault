# Step 6: Install Ollama

## Local vs. cloud — what happens where?

It is important to understand what runs locally in this workflow and what goes through the cloud:

| Step | Where | Notes |
|------|------|-------------|
| Zotero MCP (querying library) | ✅ Local | Connection via `localhost` |
| yt-dlp (fetching transcripts) | ✅ Local | Scraping on your Mac |
| whisper.cpp (transcribing audio) | ✅ Local | M4 Metal GPU |
| Semantic search (Zotero MCP) | ✅ Local | Local vector database |
| **Reasoning, summarizing, writing syntheses** | ✅ **Local** | mistral-small:22b via Ollama (default, driven by olw); Anthropic API only when `--hd` is used |

In the default mode, all generative work — compiling bundles into wiki drafts, concept pages, Phase-2 previews — is handled locally by Ollama. The primary model is **mistral-small:22b**, run by olw (obsidian-llm-wiki) via `wiki.toml`; Qwen3.5:9b remains only as a fallback used by `summarize_item.py`. Claude Code orchestrates the workflow but does not send source content to the Anthropic API. No tokens, no data transfer.

**The honest trade-off:** local models are less capable than Claude Sonnet for complex or nuanced tasks. For simple summaries and previews the difference is small; for writing rich wiki pages or drawing subtle connections between sources, Claude Sonnet is noticeably better. Add `--hd` to any request to switch to Claude Sonnet 4.6 via the Anthropic API for that task — Claude Code always announces this and asks for confirmation before making the API call.

---

## 6a. Install

```bash
brew install ollama
```

## 6b. Download models

For an M4 Mac mini with 24 GB memory, **mistral-small:22b** is the recommended default model for all local processing tasks in the workflow. It is the primary model driven by olw (obsidian-llm-wiki) during `olw compile`:

```bash
ollama pull mistral-small:22b   # ~13 GB — primary model, used by olw
```

mistral-small:22b offers strong reasoning and multilingual quality (including Dutch) at a size that still fits comfortably on 24 GB while leaving headroom for the vector database and other local services.

```bash
# Fallback model — used by summarize_item.py for Phase-2 previews:
ollama pull qwen3.5:9b   # ~6.6 GB — lighter fallback, 256K context, multilingual
```

Qwen3.5:9b has a context window of 256K tokens and explicit multilingual training (201 languages, including Dutch). It is no longer the primary model — it is only a fallback that `summarize_item.py` uses for quick Phase-2 preview summaries.

```bash
# Optional smaller alternative for memory-constrained systems:
ollama pull phi3           # ~2.3 GB — very compact
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

mistral-small:22b is the primary engine for generative tasks. The main path runs through olw (obsidian-llm-wiki), which reads its model choice from `wiki.toml` and calls Ollama during `olw compile` to turn canonical bundles into wiki drafts. For one-off or fallback generation outside the olw pipeline, the workflow uses a dedicated helper script — `.claude/ollama-generate.py` — to call Ollama via its REST API rather than the CLI.

**Why a helper script instead of `ollama run`?**

The Ollama CLI (`ollama run mistral-small:22b < file.txt`) produces terminal output with ANSI escape codes and a loading spinner. When this output is captured by Claude Code's bash tool, the result contains hundreds of lines of control characters that need to be stripped before the content is usable. The helper script avoids this entirely by talking directly to the Ollama REST API at `http://localhost:11434/api/generate`.

**Usage (fallback helper, outside the olw pipeline):**

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/ollama-generate.py \
  --input  inbox/source.txt \
  --output raw/notes/note.md \
  --prompt "Write a note in the same language as the source text..."
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

The `CLAUDE.md` in your vault already contains the privacy rule and points to the olw pipeline as the standard path, with `ollama-generate.py` as the fallback helper — no further configuration is needed per task.
