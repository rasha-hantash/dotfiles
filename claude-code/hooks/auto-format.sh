#!/usr/bin/env bash
# PostToolUse (Write|Edit) hook — auto-format files after Claude edits them
# Async hook: runs in background, returns systemMessage with formatter used

set -euo pipefail

# Read hook input from stdin
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null || true)

if [ -z "$FILE_PATH" ] || [ ! -f "$FILE_PATH" ]; then
  exit 0
fi

EXT="${FILE_PATH##*.}"
FORMATTER=""

case "$EXT" in
  py)
    if command -v uv &>/dev/null && uv run ruff format --check "$FILE_PATH" &>/dev/null 2>&1; then
      uv run ruff format --quiet "$FILE_PATH" 2>/dev/null && FORMATTER="uv run ruff format"
    elif command -v ruff &>/dev/null; then
      ruff format --quiet "$FILE_PATH" 2>/dev/null && FORMATTER="ruff format"
    elif command -v uv &>/dev/null && uv run black --check "$FILE_PATH" &>/dev/null 2>&1; then
      uv run black --quiet "$FILE_PATH" 2>/dev/null && FORMATTER="uv run black"
    elif command -v black &>/dev/null; then
      black --quiet "$FILE_PATH" 2>/dev/null && FORMATTER="black"
    fi
    ;;

  ts|tsx|js|jsx|json|css|md|html|yaml|yml)
    DIR=$(dirname "$FILE_PATH")
    # Try local prettier first, then global, then npx
    if [ -x "$DIR/node_modules/.bin/prettier" ]; then
      "$DIR/node_modules/.bin/prettier" --write "$FILE_PATH" &>/dev/null && FORMATTER="prettier (local)"
    elif command -v prettier &>/dev/null; then
      prettier --write "$FILE_PATH" &>/dev/null && FORMATTER="prettier"
    elif command -v npx &>/dev/null; then
      npx --yes prettier --write "$FILE_PATH" &>/dev/null 2>&1 && FORMATTER="npx prettier"
    fi
    ;;

  go)
    if command -v gofmt &>/dev/null; then
      gofmt -w "$FILE_PATH" 2>/dev/null && FORMATTER="gofmt"
    fi
    ;;

  sql)
    if command -v pg_format &>/dev/null; then
      TEMP=$(mktemp)
      pg_format "$FILE_PATH" > "$TEMP" 2>/dev/null && mv "$TEMP" "$FILE_PATH" && FORMATTER="pg_format"
      rm -f "$TEMP" 2>/dev/null || true
    fi
    ;;
esac

if [ -n "$FORMATTER" ]; then
  echo "{\"systemMessage\": \"auto-formatted $(basename "$FILE_PATH") with $FORMATTER\"}"
fi

exit 0
