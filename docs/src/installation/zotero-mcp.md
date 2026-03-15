# Step 4: Install and configure Zotero MCP

## 4a. Install the package

```bash
uv tool install zotero-mcp-server
```

Verify the installation was successful:

```bash
zotero-mcp version
```

## 4b. Run the setup wizard

```bash
zotero-mcp setup
```

The wizard asks you a number of questions:

- **Access method:** choose `local` (no API key needed, fully offline)
- **MCP client:** choose `Claude Desktop` if you plan to install it later, or skip
- **Semantic search:** you can skip this now and configure it later (see step 10)

## 4c. Initialize semantic search

Build the local search database (uses the free, locally running model `all-MiniLM-L6-v2`):

```bash
# Quick version (metadata only):
zotero-mcp update-db

# Extended version (including full text — recommended):
zotero-mcp update-db --fulltext
```

> **Note:** The `--fulltext` option takes longer but gives much better search results. On an M4 Mac mini with an average-sized library this takes 5–20 minutes.

Check the status of the database:

```bash
zotero-mcp db-status
```
