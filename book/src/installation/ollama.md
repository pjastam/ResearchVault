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
