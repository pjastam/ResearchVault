# Step 3: Set up Python environment

Zotero MCP requires Python 3.10 or higher. On Apple Silicon, `uv` works best as a fast, modern package manager.

## 3a. Install uv (recommended)

```bash
brew install uv
```

Verify the installation:

```bash
uv --version
```

## 3b. Check Python version

```bash
python3 --version
```

If the version is lower than 3.10, install a newer version:

```bash
brew install python@3.12
```
