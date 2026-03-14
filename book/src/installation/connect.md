# Step 8: Connect Claude Code to Zotero MCP

## 8a. Edit the configuration file

Claude Code reads the MCP configuration from `~/Library/Application Support/Claude/claude_desktop_config.json`. This is the same location used by Claude Desktop. Create or edit this file:

```bash
mkdir -p ~/Library/Application\ Support/Claude
nano ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

Insert the following (or add the `zotero` section to an existing file):

```json
{
  "mcpServers": {
    "zotero": {
      "command": "zotero-mcp",
      "env": {
        "ZOTERO_LOCAL": "true"
      }
    }
  }
}
```

Save with `Ctrl + O`, `Enter`, then `Ctrl + X`.

## 8b. Verify the MCP configuration

```bash
zotero-mcp setup-info
```

This shows the installation path and the configuration as Zotero MCP sees it. Note down the **userID** shown — you will need it in the next step.

## 8c. Configure Claude Code permissions

Claude Code's permission settings for this vault are stored in `.claude/settings.local.json`. This file contains your home path and Zotero library ID, so it is not checked into version control. Generate it from the template using the setup script:

```bash
cd ~/Documents/ResearchVault
./setup.sh
```

The script:
1. Auto-detects your home path
2. Asks for your Zotero library ID (the userID from `zotero-mcp setup-info`)
3. Writes `.claude/settings.local.json` with the correct paths

> **Note:** If you ever move your vault or reinstall tools, re-run `./setup.sh` to regenerate the file.
