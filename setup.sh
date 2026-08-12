#!/bin/bash
set -e

echo "ResearchVault — initial setup"
echo "=============================="
echo ""

# ── 1. Dependency checks ──────────────────────────────────────────────────────

echo "Checking dependencies..."

# Backend uitlezen uit vault/wiki-backend.toml — olw-specifieke stappen zijn
# alleen relevant wanneer olw ook daadwerkelijk de geconfigureerde backend is.
# Sentinelnamen (__unset__/__unreadable__) gebruiken dubbele underscores zodat ze nooit
# kunnen botsen met een echte backendnaam.
BACKEND=$(python3 - <<'PY' 2>/dev/null || echo "__unreadable__"
import tomllib, pathlib
p = pathlib.Path("vault/wiki-backend.toml")
print(tomllib.loads(p.read_text())["backend"] if p.is_file() else "__unset__")
PY
)
echo "Wiki backend: $BACKEND"

if [ "$BACKEND" = "__unset__" ]; then
  echo "  ⚠ vault/wiki-backend.toml missing — run: python3 .claude/migrate-wiki-backend.py vault --apply"
elif [ "$BACKEND" = "__unreadable__" ]; then
  # Config bestaat maar is onleesbaar (kapotte TOML, ontbrekende `backend`-sleutel).
  # Nooit stil doorlopen: zonder deze tak zou het script "✓ olw" tonen en de gebruiker
  # in de waan laten dat alles klopt, terwijl geen enkele backend-stap kan werken.
  echo "  ✗ vault/wiki-backend.toml exists but could not be read — check its TOML syntax and 'backend' key"
  DEP_MISSING=1
elif [ "$BACKEND" != "olw" ]; then
  echo "  ✓ backend '$BACKEND' configured — see docs → 'Wiki backends' for its requirements"
elif ! command -v olw &>/dev/null; then
  echo "  ✗ olw (obsidian-llm-wiki) not found — install: uv tool install obsidian-llm-wiki"
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
# Alleen relevant wanneer olw ook daadwerkelijk de geconfigureerde backend is.

if [ "$BACKEND" = "olw" ]; then
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
fi

echo ""
echo "Setup complete. Start Claude Code:"
echo "  claude"
echo ""
echo "Run the wiki pipeline:"
if [ "$BACKEND" = "olw" ]; then
  echo "  (cd vault && olw ingest --all)   # process vault/raw/ → wiki/"
  echo "  (cd vault && olw review)         # approve/reject drafts"
elif [ "$BACKEND" = "__unset__" ] || [ "$BACKEND" = "__unreadable__" ]; then
  echo "  configure a wiki backend first — see docs → 'Wiki backends'"
else
  echo "  see docs → 'Wiki backends' for the $BACKEND workflow"
fi
