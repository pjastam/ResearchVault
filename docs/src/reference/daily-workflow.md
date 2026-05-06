# Activating the skill & daily workflow

## Activating the research workflow skill

The skill is a markdown file that tells Claude Code how to behave during research sessions. One-time installation:

```bash
# Create the skills folder in your vault
mkdir -p ~/Documents/ResearchVault/.claude/skills

# Copy the skill file to the vault
cp SKILL.md ~/Documents/ResearchVault/.claude/skills/
```

Then add the following line to your `CLAUDE.md` (at the bottom):

```markdown
## Active skills
- Read and follow `.claude/skills/SKILL.md` during every research session.
```

From that point on, the skill is active as soon as you open Claude Code in your vault. You can start the workflow by typing: `/research` or simply "start research workflow".

---

## Daily workflow after installation

Once everything is set up, the daily workflow is straightforward. The feedreader runs automatically — no action required.

1. **Browse the filtered feed** at `http://localhost:8765/filtered.html` (or in NetNewsWire via the three type-specific Atom feeds). Items are sorted by relevance score. Send interesting ones to Zotero `_inbox` via the Zotero browser extension or iOS app. Press 👎 on clearly off-topic items to give a negative signal to the learning loop.
2. **Open Terminal in your vault:** `cd ~/Documents/ResearchVault && claude`
3. **Activate the skill:** type `/research` or "start research workflow"
4. Claude Code asks an intake question and guides you interactively from there

You do not need to know exactly what you are looking for — the skill is designed to help you with that.

### Full session flow

1. Browse the filtered feed and forward interesting items to Zotero `_inbox`
2. Open Terminal, navigate to your vault, and start Claude Code:

   ```bash
   cd ~/Documents/ResearchVault
   claude
   ```

3. Activate the research workflow:

   ```text
   /research
   ```

   or just type: `start research workflow`

4. Optionally, run `index-score.py` first to prioritize your review:

   ```bash
   ~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/index-score.py
   ```

   This ranks all `_inbox` items by semantic similarity to your existing library (using the ChromaDB embeddings from zotero-mcp), so you know which items to focus on.

5. Claude Code retrieves all items from your Zotero `_inbox` and presents each one with a short summary and relevance assessment — the summary is generated locally by Qwen3.5:9b. You respond **Go** or **No-go** per item.
6. For each **Go**: Claude Code writes a structured literature note using the safe pipeline below.
7. For each **No-go**: Claude Code removes the item from `_inbox` (after your confirmation).
8. At the end of the session, Claude Code shows a summary: X approved, Y removed. The Zotero semantic search database is updated automatically each day as part of the nightly batch job (`nl.pietstam.nachtelijke-taken` daemon, runs at 06:00) — no manual action needed before a session. If you process items later in the day and want the database to reflect them immediately, run:

   ```bash
   zotero-mcp update-db --fulltext # recommended (includes full text, 5–20 min on Apple Silicon)
   ```

   Or use the alias: `update-zotero`. Check database status with `zotero-mcp db-status`.

---

## Helper scripts

The workflow uses three helper scripts in `.claude/`. They keep source content out of Claude Code's context and handle Zotero write operations.

### `fetch-fulltext.py` — retrieve and save attachment text

Fetches the full text of a Zotero attachment and saves it to a local file. Only prints status; never prints content.

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/fetch-fulltext.py ITEMKEY vault/.cache/bron.txt
# Output: Saved: vault/.cache/bron.txt (12,345 chars, type: application/pdf)
```

### `ollama-generate.py` — generate text via Ollama REST API

Calls Ollama's REST API directly (no CLI, no ANSI codes). Prepends `/no_think` to suppress Qwen3.5:9b's reasoning step. Prints only status lines.

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/ollama-generate.py \
  --input  vault/.cache/bron.txt \
  --output vault/llm-notes/notitie.md \
  --prompt "Write a literature note in Dutch..."
# Output: Input: vault/.cache/bron.txt (12,345 chars) | Written: vault/llm-notes/notitie.md (3,200 chars)
```

### `zotero-remove-from-inbox.py` — remove processed item from `_inbox`

Removes the item from the `_inbox` collection in Zotero via the web API. Requires `ZOTERO_API_KEY` in the environment or `.env` file (see step 4d).

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/zotero-remove-from-inbox.py ITEMKEY
# Output: Item ITEMKEY removed from _inbox.
```
