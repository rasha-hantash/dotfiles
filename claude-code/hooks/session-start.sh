#!/usr/bin/env bash
# SessionStart hook — inject environment variables into every Bash call
# Uses CLAUDE_ENV_FILE for persistent env vars across the session

set -euo pipefail

if [ -z "${CLAUDE_ENV_FILE:-}" ]; then
  exit 0
fi

# Core Python settings
echo 'export PYTHONDONTWRITEBYTECODE=1' >> "$CLAUDE_ENV_FILE"
echo 'export PYTHONUNBUFFERED=1' >> "$CLAUDE_ENV_FILE"

# Suppress noisy tool output
echo 'export NO_UPDATE_NOTIFIER=1' >> "$CLAUDE_ENV_FILE"
echo 'export NODE_NO_WARNINGS=1' >> "$CLAUDE_ENV_FILE"
echo 'export NO_COLOR=1' >> "$CLAUDE_ENV_FILE"

# Consistent locale
echo 'export LANG=en_US.UTF-8' >> "$CLAUDE_ENV_FILE"

# Auto-add node_modules/.bin to PATH if it exists in the project
CWD=$(echo '' | python3 -c "import sys,json; print(json.load(sys.stdin).get('cwd',''))" 2>/dev/null || true)
if [ -n "$CWD" ] && [ -d "$CWD/node_modules/.bin" ]; then
  echo "export PATH=\"$CWD/node_modules/.bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"
fi

exit 0
