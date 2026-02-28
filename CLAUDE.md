# Dotfiles

System-level configs (shell, tmux, editor) managed from this repo and symlinked to their real locations.

## Structure

- `tmux/tmux.conf` → `~/.tmux.conf`
- `tmux/bin/` → `~/.local/bin/` (session management scripts)
- `ghostty/config` → Ghostty terminal config
- `claude-code/` → Claude Code settings
- `setup.sh` — installs symlinks

## Cove (Claude Code Session Manager)

Cove manages Claude Code sessions inside tmux — creating windows with a 3-pane layout (Claude pane, sidebar navigator, mini terminal).

### Rust rewrite (Feb 2026)

Cove was originally written in bash/zsh (`tmux/bin/ccs` and `tmux/bin/tmux-sidebar`). It was rewritten in Rust after hitting fundamental shell scripting limitations:

**Silent failures:** tmux commands (split-window, respawn-pane) would fail without any error reported. Layout setup chains 4+ tmux commands with no intermediate error detection — if one fails midway, the window is left in a broken state.

**Quoting/escaping:** Passing directory paths through tmux → shell → program required careful quoting. Paths with spaces or special characters silently broke. The git history shows a fix specifically for launching claude "directly without shell echo" because wrapping it in a shell caused unwanted prompts.

**Race conditions in the sidebar:** The interactive sidebar (key input + real-time window list refresh) required multiple rounds of fixes for: arrow key drops during rapid pressing (key draining with nested timeouts), selection sync when another sidebar instance switched windows, and render flickering. Shell has no concurrency primitives, so all of this was timing hacks (`read -t 0.1`, `read -t 0.02`, tick counters).

**Terminal compatibility:** The tab/ghost-text autocomplete issue required a 3-layer fix across tmux config, Ghostty config, and Claude Code keybindings. It worked initially, then broke again on Warp and iTerm. Shell has no way to abstract over terminal differences.

**No structured data:** Session/window state was managed by parsing `tmux list-windows` output with string manipulation. No types, no validation.

**Repeated edge-case fixes:** The git history shows a pattern of incremental patches (duplicate session name rejection, sidebar blink elimination, detach keybind fix, pane respawn logic) rather than feature work — a sign the tool had outgrown shell scripting.

### Convention docs

- Shell scripting limitations: `brain-os/unix/shell-scripting-limitations.md`
- Terminal/escape sequence reference: `brain-os/unix/terminals.md`
