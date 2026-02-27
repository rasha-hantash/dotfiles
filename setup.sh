#!/usr/bin/env bash
# setup.sh — Install CCS (Claude Code Sessions)
# Symlinks configs and adds ccs to PATH

set -euo pipefail

DOTFILES="$(cd "$(dirname "$0")" && pwd)"

# Colors
C_PEACH=$'\033[38;2;250;179;135m'
C_BLUE=$'\033[38;2;137;180;250m'
C_GREEN=$'\033[38;2;166;227;161m'
C_RED=$'\033[38;2;243;139;168m'
C_OVERLAY=$'\033[38;2;108;112;134m'
C_BOLD=$'\033[1m'
C_R=$'\033[0m'

info()  { printf "${C_BLUE}%s${C_R}\n" "$*"; }
ok()    { printf "${C_GREEN}  ✓${C_R} %s\n" "$*"; }
warn()  { printf "${C_PEACH}  !${C_R} %s\n" "$*"; }
err()   { printf "${C_RED}  ✗${C_R} %s\n" "$*"; }

# Symlink helper — asks before overwriting existing files or directories
link_file() {
    local src="$1" dst="$2" name="$3"

    if [ -L "$dst" ]; then
        local current
        current=$(readlink "$dst")
        if [ "$current" = "$src" ]; then
            ok "$name already linked"
            return
        fi
        warn "$name symlink exists → $current"
        printf "    Replace with → %s? [y/N] " "$src"
        read -r confirm
        if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
            warn "Skipped $name"
            return
        fi
        rm "$dst"
    elif [ -d "$dst" ]; then
        warn "$name exists at $dst (is a directory)"
        printf "    Back up to %s.bak and replace with symlink? [y/N] " "$dst"
        read -r confirm
        if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
            warn "Skipped $name"
            return
        fi
        mv "$dst" "$dst.bak"
        ok "Backed up to $dst.bak"
    elif [ -e "$dst" ]; then
        warn "$name exists at $dst (not a symlink)"
        printf "    Back up to %s.bak and replace? [y/N] " "$dst"
        read -r confirm
        if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
            warn "Skipped $name"
            return
        fi
        mv "$dst" "$dst.bak"
        ok "Backed up to $dst.bak"
    fi

    mkdir -p "$(dirname "$dst")"
    ln -s "$src" "$dst"
    ok "$name → $dst"
}

printf "\n${C_BOLD}${C_PEACH}CCS${C_R} ${C_BOLD}— Claude Code Sessions${C_R}\n\n"

# ── Check dependencies ──
info "Checking dependencies..."

missing=0

if command -v tmux &>/dev/null; then
    ok "tmux $(tmux -V | awk '{print $2}')"
else
    err "tmux not found — install with: brew install tmux"
    missing=1
fi

if command -v cargo &>/dev/null; then
    ok "cargo $(cargo --version | awk '{print $2}')"
else
    err "cargo not found — install Rust: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    missing=1
fi

if command -v claude &>/dev/null; then
    ok "claude CLI found"
else
    warn "claude CLI not found — install from https://docs.anthropic.com/en/docs/claude-code"
    warn "CCS will still install, but sessions won't launch Claude without it"
fi

# Check for Ghostty
if [ -d "/Applications/Ghostty.app" ]; then
    ok "Ghostty found"
else
    warn "Ghostty not found — keybind shortcuts require Ghostty"
    warn "Download from https://ghostty.org/"
fi

if [ "$missing" -eq 1 ]; then
    err "Missing required dependencies. Install them and re-run setup."
    exit 1
fi

printf "\n"

# ── Symlink configs ──
info "Linking configs..."

link_file "$DOTFILES/tmux/tmux.conf" "$HOME/.tmux.conf" "tmux config"
link_file "$DOTFILES/ghostty/config" "$HOME/.config/ghostty/config" "Ghostty config"
link_file "$DOTFILES/claude-code/keybindings.json" "$HOME/.claude/keybindings.json" "Claude Code keybindings"
link_file "$DOTFILES/claude-code/settings.json" "$HOME/.claude/settings.json" "Claude Code settings"
link_file "$DOTFILES/claude-code/settings.local.json" "$HOME/.claude/settings.local.json" "Claude Code local settings"
link_file "$DOTFILES/claude-code/CLAUDE.md" "$HOME/.claude/CLAUDE.md" "Claude Code global instructions"
link_file "$DOTFILES/claude-code/statusline-command.sh" "$HOME/.claude/statusline-command.sh" "Claude Code statusline"
link_file "$DOTFILES/claude-code/hooks" "$HOME/.claude/hooks" "Claude Code hooks"
link_file "$DOTFILES/claude-code/agents" "$HOME/.claude/agents" "Claude Code agents"
link_file "$DOTFILES/claude-code/skills" "$HOME/.claude/skills" "Claude Code skills"

printf "\n"

# ── Build CCS binary ──
info "Building CCS..."

if command -v cargo &>/dev/null; then
    (cd "$DOTFILES/ccs" && cargo build --release 2>&1) && ok "ccs binary built" || {
        err "cargo build failed"
        exit 1
    }
else
    err "cargo not found — skipping build"
    exit 1
fi

BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

link_file "$DOTFILES/ccs/target/release/ccs" "$BIN_DIR/ccs" "ccs"

# Clean up old script symlinks if they exist
for old_link in "$BIN_DIR/tmux-sidebar"; do
    if [ -L "$old_link" ]; then
        rm "$old_link"
        ok "Removed old symlink: $(basename "$old_link")"
    fi
done

# Check if ~/.local/bin is in PATH
if ! echo "$PATH" | tr ':' '\n' | grep -qx "$BIN_DIR"; then
    printf "\n"
    warn "$BIN_DIR is not in your PATH"
    printf "    Add this to your shell profile (~/.zshrc or ~/.bashrc):\n"
    printf "    ${C_OVERLAY}export PATH=\"\$HOME/.local/bin:\$PATH\"${C_R}\n"
fi

printf "\n"

# ── Reload tmux if running ──
if [ -n "${TMUX:-}" ]; then
    tmux source-file "$HOME/.tmux.conf" 2>/dev/null && ok "Reloaded tmux config" || true
fi

# ── Done ──
printf "${C_GREEN}${C_BOLD}Done!${C_R}\n\n"
printf "Get started:\n"
printf "  ${C_PEACH}ccs start myproject ~/path/to/project${C_R}\n\n"
printf "Shortcuts (in Ghostty):\n"
printf "  ${C_BLUE}⌘J${C_R}  Claude Code    ${C_BLUE}⌘P${C_R}  Sessions\n"
printf "  ${C_BLUE}⌘M${C_R}  Terminal       ${C_BLUE}⌘;${C_R}  Exit\n\n"
