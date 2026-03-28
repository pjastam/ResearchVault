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

## 4d. Set up a Zotero API key (required for write access)

The local Zotero API (port 23119) is read-only. To allow Claude Code to remove processed items from your `_inbox` collection automatically, you need a Zotero web API key with write access.

**Create the key:**

1. Go to [zotero.org/settings/keys](https://www.zotero.org/settings/keys)
2. Click **Create new private key**
3. Give it a name (e.g. "Claude Code")
4. Enable **Allow library access** and **Allow write access** under *Personal Library*
5. Click **Create** and copy the key

**Find your library ID:**

Your library ID is visible in the Zotero web interface URL after logging in, or you can retrieve it from the local API:

```bash
curl -s http://localhost:23119/api/users/0/items?limit=1 | python3 -c "import json,sys; items=json.load(sys.stdin); print(items[0]['library']['id'])"
```

**Store the credentials:**

Add these lines to your `~/.zprofile` (persistent across sessions):

```bash
export ZOTERO_API_KEY=your_api_key_here
export ZOTERO_LIBRARY_ID=your_library_id_here
export ZOTERO_LIBRARY_TYPE=user
```

Also create a `.env` file in your vault root (used by the helper scripts):

```bash
cat > ~/Documents/ResearchVault/.env << EOF
ZOTERO_API_KEY=your_api_key_here
ZOTERO_LIBRARY_ID=your_library_id_here
ZOTERO_LIBRARY_TYPE=user
EOF
```

The `.env` file is already listed in `.gitignore` so it will not be committed to version control.
