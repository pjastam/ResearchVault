---
paths:
  - "literature/**"
  - "syntheses/**"
  - "concepts/**"
  - "authors/**"
  - "debates/**"
  - "inbox/**"
  - "projects/**"
---
Prefer `hyalo` CLI for operations on markdown files in this vault:
- **Search/filter**: `hyalo find --property status=unread --format text`
- **Tag filter**: `hyalo find --tag risicoverevening --format text`
- **Body search**: `hyalo find "moral hazard" --format text`
- **Title regex**: `hyalo find --property 'title~=zorginkoop' --format text`
- **Read frontmatter/metadata**: `hyalo find --file literature/auteur2024kw.md --format text`
- **Read content/sections**: `hyalo read literature/auteur2024kw.md` or `hyalo read <path> --section "TLDR"`
- **Mutate frontmatter**: `hyalo set --file <path> --property status=read`
- **Move/rename** (rewrites wikilinks): `hyalo mv literature/oud.md literature/nieuw.md`
- **Backlinks**: `hyalo backlinks literature/auteur2024kw.md --format text`

Fall back to Edit for body prose changes, Write for new files, and Read when
hyalo doesn't cover the operation (e.g. reading raw markdown for rewriting).

Use `--format text` for compact output. Run `hyalo <command> --help` if unsure.
