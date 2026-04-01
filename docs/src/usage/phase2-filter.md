# Phase 2: Go/No-go in Claude Code

Phase 2 is the filter step. Items in Zotero `_inbox` are reviewed one by one; you decide which ones enter the vault (Go) and which ones do not (No-go).

---

## Starting a Phase 2 session

Make sure Zotero is running (the local API must be active), then:

```bash
cd ~/Documents/ResearchVault && claude
```

Start the review with either of these:

```
beoordeel inbox
```

or via the workflow menu:

```
/research  →  [0]
```

Optionally, run `index-score.py` first to pre-rank items:

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/index-score.py
```

This scores each `_inbox` item by semantic similarity to your existing Zotero library (0–100) and prints a sorted list. Claude Code uses these scores during the review session.

---

## How Claude Code reviews each item

The treatment depends on the item's Zotero tag and its relevance score.

### Tag-based treatment

| Zotero tag | What Claude Code does |
|---|---|
| `✅` | Previously approved — skip the Go/No-go question and go directly to Phase 3 |
| `📖` | You have already read it — only ask Go/No-go, no summary generated |
| No tag, `/unread`, or any other tag | Score-based treatment (see below) |

### Score-based treatment (for untagged items)

| Score | Treatment |
|---|---|
| 🟢 ≥70 | Show title + score; ask Go/No-go directly — strong match, no summary needed |
| 🟡 40–69 | Generate a 2–3 sentence summary via Qwen3.5:9b (local); ask Go/No-go |
| 🔴 <40 | Propose No-go ("Score: X — low match with your library. No-go?"); you can still choose Go |

Claude Code asks for one Go/No-go decision at a time, giving you space to decide per item.

---

## Go

**Go** means: this item is approved for Phase 3.

Claude Code moves the item to the appropriate Zotero collection and begins processing — or asks whether you want to process it immediately or later in the session.

When the resulting literature note is created, the `status` field in the frontmatter is set based on the Zotero tag:
- `status: read` — if the item had a `✅` tag (you had already read it)
- `status: unread` — in all other cases

---

## No-go

**No-go** means: this item will not enter the vault.

Claude Code always asks for confirmation before deleting. After confirmation, the item is permanently removed from Zotero `_inbox`. No note is created. There is no intermediate option — a No-go is final.

---

## High-definition mode

For a higher-quality summary, add `--hd` to activate Claude Sonnet 4.6 instead of the local Qwen model:

```
beoordeel inbox --hd
```

Claude Code will ask for explicit confirmation before sending any content to the Anthropic API.

---

## End of session

At the end of the session, Claude Code shows a summary: `X items approved, Y items removed.`

If new papers were added to your Zotero library, update the semantic search database:

```bash
update-zotero          # full update including full text (recommended)
zotero-mcp db-status   # check current database status
```

This ensures that new additions are included in future relevance scores.
