# The local stack

The three-phase model says *what* happens to a source. This page says *what runs it* — and the answer is: everything, on your own machine.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../assets/stack-diagram-dark.svg">
  <img src="../assets/stack-diagram-light.svg" alt="Local stack diagram">
</picture>

## What grabs hold where

| Phase | Building blocks | Role |
|---|---|---|
| Capture | NetNewsWire, Zotero Connector, iOS share sheet, `feedreader-score.py` | Get candidates into Zotero `_inbox` |
| Filter | zotero-mcp (ChromaDB embeddings), `index-score.py`, `summarize_item.py`, Ollama | Rank and preview so you can decide Go/No-go |
| Bundle | `build-zotero-bundle.py`, `fetch-fulltext.py`, yt-dlp, youtube-transcript-api, whisper.cpp | Turn any source type into one canonical Markdown bundle |
| Backend | `wiki_backend.py` → olw, claude-obsidian, or none | Compile bundles into an interlinked wiki |
| Read | Obsidian, hyalo | Browse and search the result |

## Why the wiring is the point

Each of these tools is useful on its own. Zotero manages references, whisper.cpp transcribes, Ollama runs models, Obsidian renders Markdown. None of them knows about the others.

What this repository contributes is the wiring: a podcast episode, a PDF, and a note you wrote yourself all end up in the same canonical format, scored by the same relevance model, gated by the same Go/No-go decision, and compiled by whichever backend you chose. The convergence is the work.

It also means every substitution is local. Don't want Ollama? Set `LLM_BACKEND=mlx`. Don't want olw? Change one line in `wiki-backend.toml`. Nothing in the chain assumes a cloud service exists.
