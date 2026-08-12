# The raw/ bundle format (v1)

This is the contract. Everything before it is ResearchVault; everything after it is a replaceable backend.

One Markdown file per source at `raw/{citekey}__{itemKey}.md`, or `raw/notes/{slug}.md` for promoted personal notes. Written by `build-zotero-bundle.py` and `promote-to-raw.py`. Verbatim — no LLM has touched the content.

## Structure

| Part | Content |
|---|---|
| YAML frontmatter | `citekey`, item key, title, authors, year, DOI, journal, tags, `exporter_version` |
| Abstract | From Zotero `abstractNote` |
| Child notes | Verbatim, HTML converted to Markdown |
| Annotations | Per page: highlighted text plus your comment |
| Full text | Extracted PDF text, or the transcript for video and podcast sources |

Personal notes carry `source_type: personal` instead of Zotero metadata.

## Stability

The format is versioned through `exporter_version` in the frontmatter. A backend may rely on the sections above being present and on unknown frontmatter fields being ignorable.

## Why this is the contract

A backend that can read this format can replace the current one. The corollary matters just as much: **no backend-specific assumption may leak into `raw/`**. Bundles stay neutral so that swapping the engine stays a configuration change.
