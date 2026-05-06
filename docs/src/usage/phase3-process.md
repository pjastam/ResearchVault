# Phase 3: processing to the vault

Phase 3 converts approved Zotero items into canonical bundles in `vault/raw/`, then kytmanov compiles them into the wiki. No LLM is involved in the bundle creation step — it is pure format conversion.

---

## Canonical bundle creation

All item types (papers, YouTube videos, podcasts, web articles) follow the same pipeline:

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/build-zotero-bundle.py \
  --item-key ITEMKEY
# → {"status": "ok", "path": "vault/raw/{citekey}__{ITEMKEY}.md"}
```

The script collects verbatim from Zotero:
- YAML frontmatter (citekey, item key, title, creators, year, DOI, journal, tags, source_type)
- Abstract (`abstractNote`)
- Child notes (HTML → Markdown)
- PDF annotations, grouped by page (highlight text + user comments)
- Full PDF text (via `fetch-fulltext.py`) or transcript (for YouTube/podcast)

No source content reaches Claude Code. Only the JSON status object is returned.

---

## YouTube videos

YouTube items follow an **eager transcript pipeline**: when you mark a video ✅ in the feedreader, `attach-transcript.py` runs automatically and stores a cleaned transcript as an attachment in the Zotero item — so the full text is available when `build-zotero-bundle.py` runs.

**If the transcript attachment is missing** (e.g. for manually added items), run it explicitly:

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/attach-transcript.py ITEMKEY
```

Then build the bundle as normal.

---

## Podcasts

Podcast episodes added from Overcast (via iOS share sheet) arrive in Zotero `_inbox` as overcast.fm URLs. After a Go decision:

1. Download audio via yt-dlp, transcribe locally via whisper.cpp
2. Attach transcript to Zotero item via `attach-transcript.py`
3. Build canonical bundle: `build-zotero-bundle.py --item-key ITEMKEY`

---

## kytmanov processing

After building bundles, run kytmanov to update the wiki:

```bash
(cd vault && olw ingest)    # bundles → wiki/sources/ + wiki/concepts/
(cd vault && olw review)    # approve/reject drafts in wiki/.drafts/ (optional)
```

---

## After processing

After each session, check whether:

- Relevant syntheses in `vault/wiki/syntheses/` need updating
- kytmanov concepts in `vault/wiki/concepts/` are accurate

If new papers were added to Zotero, update the semantic search database:

```bash
update-zotero
```
