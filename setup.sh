#!/bin/bash
set -e

echo "ResearchVault — initial setup"
echo "=============================="
echo ""

# ── 1. Dependency checks ──────────────────────────────────────────────────────

echo "Checking dependencies..."

if ! command -v olw &>/dev/null; then
  echo "  ✗ olw (obsidian-llm-wiki) not found — install: pip install obsidian-llm-wiki"
  DEP_MISSING=1
else
  echo "  ✓ olw"
fi

if ! command -v zotero-mcp &>/dev/null; then
  echo "  ✗ zotero-mcp not found — install: uv tool install zotero-mcp-server"
  DEP_MISSING=1
else
  echo "  ✓ zotero-mcp"
fi

if ! curl -s --max-time 2 http://localhost:11434/api/tags &>/dev/null; then
  echo "  ⚠ Ollama not reachable at http://localhost:11434 (start before running olw)"
else
  echo "  ✓ Ollama"
fi

echo ""
if [ -n "$DEP_MISSING" ]; then
  echo "Fix missing dependencies above before continuing."
  echo ""
fi

# ── 2. settings.local.json ────────────────────────────────────────────────────

SKIP_SETTINGS=0

if [ -f ".claude/settings.local.json" ]; then
  echo "Warning: .claude/settings.local.json already exists."
  read -p "Overwrite? (y/N) " -n 1 -r
  echo ""
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Skipping settings.local.json."
    SKIP_SETTINGS=1
  fi
fi

if [ "$SKIP_SETTINGS" -eq 0 ]; then
  HOME_PATH="$HOME"
  echo "Home path detected: $HOME_PATH"
  echo ""

  echo "Enter your Zotero library ID."
  echo "Find it by running: zotero-mcp setup-info"
  echo "Or log in at zotero.org → Settings → Feeds/API (look for 'Your userID')."
  echo ""
  read -p "Zotero library ID: " LIBRARY_ID

  if [ -z "$LIBRARY_ID" ]; then
    echo "Error: library ID cannot be empty."
    exit 1
  fi

  sed "s|/YOUR-PATH|$HOME_PATH|g; s|YOUR-LIBRARY-ID|$LIBRARY_ID|g" \
    .claude/settings.local.json.template > .claude/settings.local.json

  echo ""
  echo "Done: .claude/settings.local.json created."
  echo ""
fi

# ── 3. kytmanov global config (~/.config/olw/config.toml) ─────────────────────

VAULT_PATH="$(pwd)/vault"
OLW_CONFIG="$HOME/.config/olw/config.toml"

echo "Configuring kytmanov (olw)..."
echo "  vault path: $VAULT_PATH"

if [ -f "$OLW_CONFIG" ]; then
  # Update vault line in existing config, preserve other settings
  python3 -c "
import re, sys
path = '$OLW_CONFIG'
vault = '$VAULT_PATH'
content = open(path).read()
if re.search(r'^vault\s*=', content, re.MULTILINE):
    content = re.sub(r'^vault\s*=.*$', 'vault = \"' + vault + '\"', content, flags=re.MULTILINE)
else:
    content = 'vault = \"' + vault + '\"\n' + content
open(path, 'w').write(content)
"
  echo "  Updated: $OLW_CONFIG"
else
  mkdir -p "$HOME/.config/olw"
  cat > "$OLW_CONFIG" <<EOF
vault = "$VAULT_PATH"
provider_name = "ollama"
provider_url = "http://localhost:11434"
EOF
  echo "  Created: $OLW_CONFIG"
fi

echo ""
echo "Setup complete. Start Claude Code:"
echo "  claude"
echo ""
echo "Run the wiki pipeline:"
echo "  (cd vault && olw ingest --all)   # process vault/raw/ → wiki/"
echo "  (cd vault && olw review)         # approve/reject drafts"
