# Step 3: Set up Python environment

ResearchVault requires Python 3.11 or higher (`tomllib`, used to read `wiki-backend.toml`, is standard library from 3.11 onward). On Apple Silicon, `uv` works best as a fast, modern package manager.

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

If the version is lower than 3.11, install a newer version:

```bash
brew install python@3.12
```
