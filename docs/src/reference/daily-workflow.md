# Activating the skill & daily workflow

## Activating the research workflow skill

The skill is a markdown file that tells Claude Code how to behave during research sessions. One-time installation:

```bash
# Create the skills folder in your vault
mkdir -p ~/Documents/ResearchVault/.claude/skills

# Copy the skill file to the vault
cp research-workflow-skill.md ~/Documents/ResearchVault/.claude/skills/
```

Then add the following line to your `CLAUDE.md` (at the bottom):

```markdown
## Active skills
- Read and follow `.claude/skills/research-workflow-skill.md` during every research session.
```

From that point on, the skill is active as soon as you open Claude Code in your vault. You can start the workflow by typing: `/research` or simply "start research workflow".

---

## Daily workflow after installation

Once everything is set up, the daily workflow is straightforward. Phase 0 runs automatically — no action required.

1. **Browse the filtered feed** at `http://localhost:8765/filtered.html` (or in NetNewsWire via `http://localhost:8765/filtered.xml`). Items are sorted by relevance score. Send interesting ones to Zotero `_inbox` via the browser extension or iOS app.
2. **Start Zotero** (so the local API is active)
3. **Open Terminal in your vault:** `cd ~/Documents/ResearchVault && claude`
4. **Activate the skill:** type `/research` or "start research workflow"
5. Claude Code asks an intake question and guides you interactively from there

You do not need to know exactly what you are looking for — the skill is designed to help you with that.

### Full session flow

1. Browse the filtered feed and forward interesting items to Zotero `_inbox`
2. Start Zotero
3. Open Terminal, navigate to your vault, and start Claude Code:
   ```bash
   cd ~/Documents/ResearchVault
   claude
   ```
4. Activate the research workflow:
   ```
   /research
   ```
   or just type: `start research workflow`
5. Optionally, run `index-score.py` first to prioritize your review:
   ```bash
   ~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/index-score.py
   ```
   This ranks all `_inbox` items by semantic similarity to your existing library (using the ChromaDB embeddings from zotero-mcp), so you know which items to focus on.
6. Claude Code retrieves all items from your Zotero `_inbox` and presents each one with a short summary and relevance assessment — the summary is generated locally by Qwen3.5:9b. You respond **Go** or **No-go** per item.
7. For each **Go**: Claude Code moves the item to the correct Zotero collection and writes a structured literature note in `literature/`.
8. For each **No-go**: Claude Code removes the item from `_inbox` (after your confirmation).
9. At the end of the session, Claude Code shows a summary: X approved, Y removed. If new papers were added, update the semantic search database. Use the quick version for metadata only, or the recommended full version for much better search results (5–20 min on Apple Silicon):
   ```bash
   zotero-mcp update-db            # quick (metadata only)
   zotero-mcp update-db --fulltext # recommended (includes full text)
   ```
   Or use the alias: `update-zotero` (equivalent to `--fulltext`). Check database status with `zotero-mcp db-status`.
