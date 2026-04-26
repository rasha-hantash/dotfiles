#!/usr/bin/env bash
# vps-bootstrap.sh — personal layer on top of claude-vps-setup's bootstrap.
#
# Runs AFTER `claude-vps-setup`'s `/setup` has provisioned and bootstrapped
# the VPS. Adds personal tooling (Rust, cove, neovim, ripgrep, fd, gh, gt)
# and symlinks dotfiles into ~/.
#
# claude-vps-setup already handles: zsh, git, curl, tmux, build-essential, jq,
# unzip, Tailscale, SSH hardening, Node, Claude Code, vps-clone/vps-sync-repo
# helpers, and the `claude --effort max` alias.
#
# Idempotent. Re-run any time to refresh dotfiles or upgrade tools.
#
# Usage on a freshly-bootstrapped VPS:
#   curl -fsSL https://raw.githubusercontent.com/rasha-hantash/dotfiles/main/scripts/vps-bootstrap.sh | bash

set -euo pipefail

DOTFILES="${DOTFILES:-$HOME/workspace/dotfiles}"
GH_USER="${GH_USER:-rasha-hantash}"
DOTFILES_REPO="${DOTFILES_REPO:-https://github.com/$GH_USER/dotfiles}"
PRIV="${PRIV:-sudo}"

log()  { printf "\033[34m\u25B8\033[0m %s\n" "$*"; }
ok()   { printf "\033[32m\u2713\033[0m %s\n" "$*"; }
skip() { printf "\033[33m\u00B7\033[0m %s\n" "$*"; }
warn() { printf "\033[33m!\033[0m %s\n" "$*"; }

[ "$(uname)" != "Linux" ] && { warn "Linux only — on macOS use setup.sh"; exit 1; }

# 1. Personal apt packages (claude-vps-setup already installed the baseline)
log "Installing personal apt packages"
$PRIV apt-get update -qq
$PRIV DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    neovim ripgrep fd-find pkg-config libssl-dev
ok "apt packages"

# 2. gh CLI
if ! command -v gh >/dev/null 2>&1; then
    log "Installing gh"
    KEYRING=/usr/share/keyrings/githubcli-archive-keyring.gpg
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg -o /tmp/gh-keyring.gpg
    $PRIV install -m 0644 /tmp/gh-keyring.gpg "$KEYRING"
    rm -f /tmp/gh-keyring.gpg
    ARCH="$(dpkg --print-architecture)"
    echo "deb [arch=$ARCH signed-by=$KEYRING] https://cli.github.com/packages stable main" \
        | $PRIV tee /etc/apt/sources.list.d/github-cli.list >/dev/null
    $PRIV apt-get update -qq
    $PRIV apt-get install -y -qq gh
    ok "gh"
else
    skip "gh already installed"
fi

# 3. gt CLI (Graphite)
if ! command -v gt >/dev/null 2>&1; then
    log "Installing gt"
    npm install -g @withgraphite/graphite-cli@stable
    ok "gt"
else
    skip "gt already installed"
fi

# 4. Rust (needed for cove)
if ! command -v cargo >/dev/null 2>&1; then
    log "Installing Rust"
    curl --proto '=https' --tlsv1.2 -fsSL https://sh.rustup.rs -o /tmp/rustup-init.sh
    sh /tmp/rustup-init.sh -y --default-toolchain stable --no-modify-path
    rm -f /tmp/rustup-init.sh
    ok "rust"
else
    skip "rust already installed"
fi
. "$HOME/.cargo/env"

# 5. cove
if ! command -v cove >/dev/null 2>&1; then
    log "Installing cove"
    cargo install cove-cli
    ok "cove"
else
    skip "cove already installed (cargo install cove-cli to upgrade)"
fi

# 6. Dotfiles clone + symlink
mkdir -p "$(dirname "$DOTFILES")"
if [ ! -d "$DOTFILES" ]; then
    log "Cloning dotfiles -> $DOTFILES"
    git clone "$DOTFILES_REPO" "$DOTFILES"
    ok "dotfiles cloned"
else
    skip "dotfiles already at $DOTFILES"
fi

log "Symlinking dotfiles"
ln -sfn "$DOTFILES/tmux/tmux.conf" "$HOME/.tmux.conf"
ln -sfn "$DOTFILES/zsh/zshrc" "$HOME/.zshrc" 2>/dev/null || true
mkdir -p "$HOME/.claude"
for d in hooks agents skills commands memory scripts assets; do
    [ -d "$DOTFILES/claude-code/$d" ] && ln -sfn "$DOTFILES/claude-code/$d" "$HOME/.claude/$d"
done
for f in CLAUDE.md settings.json keybindings.json statusline-command.sh; do
    [ -f "$DOTFILES/claude-code/$f" ] && ln -sfn "$DOTFILES/claude-code/$f" "$HOME/.claude/$f"
done
ok "dotfile symlinks"

# 7. zsh as default shell
ZSH_PATH="$(command -v zsh)"
if [ "$SHELL" != "$ZSH_PATH" ] && grep -q "^$ZSH_PATH$" /etc/shells 2>/dev/null; then
    log "Setting zsh as default shell"
    $PRIV chsh -s "$ZSH_PATH" "$USER" || warn "chsh failed — set manually if you care"
fi

cat <<'CLOSING'

  Personal layer complete. Three manual auth flows still need a browser/token:

    gh auth login          # GitHub
    gt auth                # paste token from app.graphite.dev
    claude setup-token     # paste token from claude.ai (headless-friendly)

  After that, start working:
    vps-clone <owner/repo>   # installer ships this — clones + syncs gitignored .claude/ files

CLOSING
