#!/bin/bash
set -e

echo "ResearchVault — initial setup"
echo "=============================="
echo ""

# Check if settings.local.json already exists
if [ -f ".claude/settings.local.json" ]; then
  echo "Warning: .claude/settings.local.json already exists."
  read -p "Overwrite? (y/N) " -n 1 -r
  echo ""
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
  fi
fi

# Auto-detect home path
HOME_PATH="$HOME"
echo "Home path detected: $HOME_PATH"
echo ""

# Ask for Zotero library ID
echo "Enter your Zotero library ID."
echo "Find it by running: zotero-mcp setup-info"
echo "Or log in at zotero.org → Settings → Feeds/API (look for 'Your userID')."
echo ""
read -p "Zotero library ID: " LIBRARY_ID

if [ -z "$LIBRARY_ID" ]; then
  echo "Error: library ID cannot be empty."
  exit 1
fi

# Generate settings.local.json from template
sed "s|/YOUR-PATH|$HOME_PATH|g; s|YOUR-LIBRARY-ID|$LIBRARY_ID|g" \
  .claude/settings.local.json.template > .claude/settings.local.json

echo ""
echo "Done: .claude/settings.local.json created."
echo ""
echo "You can now start Claude Code:"
echo "  claude"
