#!/usr/bin/env bash
# brew-sync.sh — Keep Brewfile in sync with installed packages
# Runs via launchd to auto-capture new installs AND removals.
#
# How it works:
#   1. Dumps current brew state to Brewfile (overwrites)
#   2. If Brewfile changed, commits and pushes via Graphite
#
# Deletions are tracked too — if you uninstall an app,
# the next sync removes it from the Brewfile.

set -euo pipefail

DOTFILES="${DOTFILES_DIR:-$HOME/workspace/personal/explorations/dotfiles}"
BREWFILE="$DOTFILES/Brewfile"
LOG="$HOME/.local/state/brew-sync/sync.log"

mkdir -p "$(dirname "$LOG")"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

if ! command -v brew &>/dev/null; then
    log "ERROR: brew not found"
    exit 1
fi

# Dump current state (captures installs AND removals)
log "Dumping brew state..."
brew bundle dump --file="$BREWFILE" --force --no-lock 2>>"$LOG"

# Check if anything changed
cd "$DOTFILES"
if git diff --quiet "$BREWFILE" 2>/dev/null; then
    log "No changes to Brewfile"
    exit 0
fi

# Something changed
log "Brewfile changed, committing..."
git add "$BREWFILE"

if command -v gt &>/dev/null; then
    gt create -m "chore: auto-sync Brewfile" 2>>"$LOG" &&     gt submit --no-interactive --publish 2>>"$LOG" &&     log "Brewfile synced and pushed via Graphite"
else
    log "ERROR: gt not found, skipping push"
    exit 1
fi
