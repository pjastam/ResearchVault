# Choosing a backend

ResearchVault writes canonical bundles to `raw/`. Turning those into a wiki is a separate job, done by a backend you configure in `wiki-backend.toml` in your vault root.

## Two properties that matter

**Locality** — `local` or `cloud`. A cloud backend sends bundle content (paper text, transcripts, your notes) to a third-party API. A local backend does not.

**Invocation** — `cli` or `session`. A `cli` backend can be driven entirely by a subprocess. A `session` backend does part of its work inside an interactive Claude Code session, which means the dispatcher cannot see or gate that step.

Both are mandatory declarations. There is no default in either direction.

## The guardrail

A vault that holds confidential material declares `confidential = true` and carries a `.confidential` marker file. On such a vault the dispatcher refuses, without fallback:

- any backend with `locality` other than `local`
- any backend with `invocation` other than `cli`
- any backend that does not declare `force_args`

`force_args` is appended to every command on a confidential vault. It exists because a declared locality is a promise, not a fact: olw itself accepts `--provider groq|openai|azure` and reads three layers of configuration. Forcing the provider on the command line means no configuration layer can override it.

## Available backends

| Backend | Locality | Invocation | Notes |
|---|---|---|---|
| [olw](olw.md) | local | cli | Default. Full pipeline: ingest, compile, approve, reject |
| [claude-obsidian](claude-obsidian.md) | cloud | session | Only `capture` is a subprocess; the wiki step is an Agent Skill |
| [none](none.md) | local | cli | ResearchVault stops at `raw/`; you drive the wiki yourself |
