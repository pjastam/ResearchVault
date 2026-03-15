# Step 15: Future perspective — local orchestrator

The only component in this stack that does not run fully locally is Claude Code as orchestrator. All generation tasks (summaries, literature notes, syntheses, flashcards) already run via Qwen3.5:9b on Ollama — fully local, fully private. What goes through the Anthropic API are the prompts with which Claude Code steers the workflow: the intake, the phase monitoring, the vault conventions, the iterative Go/No-go dialogue.

For those who also want to solve this layer locally, two serious candidates are emerging.

## Open WebUI + MCPO

Open WebUI is a self-hosted chat interface (similar to the Claude.ai interface, but local) that accesses local models via Ollama. From version 0.6.31 onwards it supports MCP natively. The MCPO proxy (Model Context Protocol to OpenAPI) translates stdio-based MCP servers — such as zotero-mcp — to HTTP endpoints that Open WebUI can call. The architecture fits directly onto the existing Mac mini M4 stack: Ollama keeps running, zotero-mcp is made available via MCPO, and Open WebUI acts as the conversational interface in the browser.

**Advantages:** mature interface, actively maintained, works on macOS without Docker, Qwen3.5:9b is compatible with tool use in this configuration.
**Disadvantages:** browser-based (no terminal workflow like Claude Code), the skill logic and vault conventions must be fully rewritten as a system prompt, no native filesystem integration without an additional MCP server.

## ollmcp (mcp-client-for-ollama)

ollmcp is a terminal interface (TUI) that connects Ollama models to multiple MCP servers simultaneously. It has an agent mode with iterative tool execution, human-in-the-loop controls, and model switching. The interface is closer to how Claude Code works — everything in the terminal, no browser. You can connect zotero-mcp, choose Qwen3.5:9b, and pass the skill as a system prompt.

**Advantages:** terminal-native, close to the current workflow, supports multiple MCP servers simultaneously, human-in-the-loop is built in.
**Disadvantages:** less mature than Open WebUI, writing vault files requires an additional filesystem MCP server, the skill logic must be rebuilt as a system prompt.

## Why this is not yet worth the effort

The orchestration layer that Claude Code provides is more than tool calls. It involves phase monitoring across a longer session, vault awareness (knowing what already exists and how it should be linked), the iterative Go/No-go dialogue per item, and reliable adherence to vault conventions across multiple steps. All of this logic currently lives in the skill and CLAUDE.md, and Claude Code follows it accurately.

With a local orchestrator, the same logic must be passed as a system prompt to Qwen3.5:9b. Instruction-following in complex multi-step workflows is noticeably less reliable with local models than with Claude Sonnet — not due to a lack of language capability, but because of consistency across multiple rounds and tools. The result is achievable, but requires considerable extra work for a less robust outcome.

This is also precisely why Claude Code structurally distinguishes itself as an orchestrator from local alternatives: not in raw generation quality (for which Qwen3.5:9b is already strong enough for most tasks), but in the reliability of workflow logic across phases and tools. Whether and when local models will reach this level is an open question. The landscape is changing fast — Open WebUI, ollmcp, and similar tools are actively in development and worth continuing to follow.
