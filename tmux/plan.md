# tmux Setup for Claude Code Session Tabs

## Context

You run multiple Claude Code sessions simultaneously. You want a dedicated Warp tab where tmux manages "Claude Code Session Tabs" — a sidebar on the right lists all active sessions, and a mini terminal below it lets you spin up new ones. Other Warp tabs remain plain terminals for running projects, servers, etc.

## Key Concepts

### What does "Meta" mean here?

In terminal history, "Meta" is a modifier key — like Shift or Ctrl, but from older Unix keyboards that literally had a key labeled "Meta." On modern Macs, the **Option (⌥) key** acts as Meta when configured to do so.

By default on macOS, pressing Option+↑ types a special Unicode character (because Apple designed Option to insert accented letters and symbols). Terminals like tmux never see a "key combo" — they just see a weird character arrive.

When you enable **"Option key as Meta"** in Warp, you're telling Warp: "When I press Option, don't insert special characters. Instead, send the Meta modifier signal that terminal programs understand." This is what lets tmux recognize `Option+↑` as "Meta+Up" and trigger the window-switching keybinding.

### What are "escape sequences"?

Terminals communicate through plain text streams — there's no binary protocol for "the user pressed Up Arrow." Instead, when you press a key, the terminal sends a specific sequence of characters that starts with the **Escape character** (ASCII code 27, written as `\033` or `^[`).

Examples:

- **Up Arrow** → terminal sends `\033[A` (escape, then `[A`)
- **Meta+Up** (Option+Up with Meta enabled) → terminal sends `\033[1;3A` (escape, then `[1;3A` — the `3` encodes "Meta modifier")

tmux reads these character sequences and maps them to actions. When the config says `bind -n M-Up previous-window`, it means: "When you see the escape sequence for Meta+Up, switch to the previous window."

Without "Option as Meta" enabled, pressing Option+Up sends a _different_ escape sequence (or a Unicode character), and tmux doesn't recognize it as `M-Up`.

---

## Architecture

```
Warp Tab: "Claude Sessions"      Warp Tab: "pancake"     Warp Tab: "rag"
┌──────────────────────┬───────┐ ┌─────────────────────┐ ┌────────────────┐
│                      │ CC    │ │                     │ │                │
│  Active Claude Code  │ Tabs  │ │  regular terminal   │ │ regular term   │
│  session             │       │ │                     │ │                │
│  (~76% width)        │▶1 pan │ │                     │ │                │
│                      │ 2 rag │ │                     │ │                │
│                      │ 3 ops │ │                     │ │                │
│                      ├───────┤ │                     │ │                │
│                      │$ cc-  │ │                     │ │                │
│                      │new .. │ │                     │ │                │
└──────────────────────┴───────┘ └─────────────────────┘ └────────────────┘
       tmux session                   no tmux                  no tmux
```

**Layout per tmux window:**

- **Pane 1 (left, ~76%)** — the Claude Code session
- **Pane 2 (top-right, ~75% of right column)** — sidebar script showing all session tabs
- **Pane 3 (bottom-right, ~25% of right column)** — mini terminal for `cc-new` commands

Switching windows with **Option+↑/↓** swaps the left pane to a different CC session. The sidebar auto-updates in every window.

## Warp prerequisite (one-time)

**Warp → Settings → Keyboard → "Option key as Meta"**: enable this so Option+↑/↓ sends the Meta escape sequence to tmux (see "Key Concepts" above for what this means).

## Files to create

### 1. `~/.tmux.conf`

```tmux
# --- Prefix ---
set -g prefix C-a
unbind C-b
bind C-a send-prefix

# --- General ---
set -g mouse on
set -g base-index 1
setw -g pane-base-index 1
set -g renumber-windows on
set -g default-terminal "tmux-256color"
set -ag terminal-overrides ",xterm-256color:RGB"

# --- Status bar (top, minimal — backup indicator) ---
set -g status-position top
set -g status-style 'bg=#1e1e2e fg=#cdd6f4'
set -g status-left ' #[bold]#S#[nobold] │ '
set -g status-left-length 20
set -g status-right ''
set -g status-justify left

# Window tabs in status bar
setw -g window-status-format ' #I:#W '
setw -g window-status-current-format ' #I:#W '
setw -g window-status-current-style 'bg=#f38ba8 fg=#1e1e2e bold'
setw -g window-status-style 'fg=#6c7086'
setw -g window-status-separator ''

# --- Session switching (Option+Up/Down) ---
bind -n M-Up previous-window
bind -n M-Down next-window

# --- Sidebar + mini-terminal auto-creation ---
# When a new window is created, split the right column into sidebar + mini-terminal
set-hook -g after-new-window '\
    split-window -h -l 24 "~/.local/bin/tmux-sidebar" ; \
    split-window -v -p 25 ; \
    select-pane -t :.1 \
'
```

### 2. `~/.local/bin/tmux-sidebar`

```bash
#!/usr/bin/env bash
# Persistent sidebar showing all Claude Code session tabs

SESSION=$(tmux display-message -p '#S')

while true; do
    printf '\033[2J\033[H'

    printf '\033[1;37m CC Session Tabs \033[0m\n'
    printf '───────────────────────\n'

    tmux list-windows -t "$SESSION" -F '#{window_index}|#{window_active}|#{window_name}' | \
    while IFS='|' read -r idx active name; do
        if [ "$active" = "1" ]; then
            printf ' \033[1;33m▶ %s  %s\033[0m\n' "$idx" "$name"
        else
            printf ' \033[90m  %s  %s\033[0m\n' "$idx" "$name"
        fi
    done

    printf '───────────────────────\n'
    printf '\033[90m ⌥↑/↓  switch\033[0m\n'

    sleep 1
done
```

### 3. `~/.local/bin/cc-new`

```bash
#!/usr/bin/env bash
# Add a new Claude Code session tab
# Usage: cc-new <name> [directory]

NAME=${1:?"Usage: cc-new <name> [directory]"}
DIR=${2:-$(pwd)}
SESSION=$(tmux display-message -p '#S')

# Create new window — the after-new-window hook handles sidebar + mini-terminal
tmux new-window -t "$SESSION" -n "$NAME" -c "$DIR"

# Start claude in the main pane (pane 1)
tmux send-keys -t "$SESSION:$NAME.1" "claude" Enter
```

### 4. `~/.local/bin/cc-start`

```bash
#!/usr/bin/env bash
# Start the Claude Code session manager
# Usage: cc-start [name] [directory]
#   cc-start                        → starts with a session named "session-1" in CWD
#   cc-start pancake ~/workspace/personal/pancake  → starts with a named first session

SESSION="cc"
NAME=${1:-"session-1"}
DIR=${2:-$(pwd)}

# Re-attach if session already exists
if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "Session '$SESSION' already exists. Re-attaching..."
    tmux attach -t "$SESSION"
    exit 0
fi

# Create session with first window
tmux new-session -d -s "$SESSION" -n "$NAME" -c "$DIR"

# Manually set up layout for first window (after-new-window hook doesn't fire for initial window)
tmux split-window -t "$SESSION:$NAME" -h -l 24 "~/.local/bin/tmux-sidebar"
tmux split-window -v -p 25
tmux select-pane -t "$SESSION:$NAME.1"

# Start claude in main pane
tmux send-keys -t "$SESSION:$NAME.1" "claude" Enter

# Attach
tmux attach -t "$SESSION"
```

## Setup steps

1. `brew install tmux` (if not already installed)
2. **Warp**: Settings → Keyboard → enable "Option key as Meta"
3. Create scripts directory: `mkdir -p ~/.local/bin`
4. Write all 4 files listed above
5. Make scripts executable: `chmod +x ~/.local/bin/tmux-sidebar ~/.local/bin/cc-new ~/.local/bin/cc-start`
6. Ensure PATH includes `~/.local/bin` — add to `~/.zshrc` if needed: `export PATH="$HOME/.local/bin:$PATH"`

## Workflow

1. Open a Warp tab → run `cc-start pancake ~/workspace/personal/pancake`
2. tmux starts with one CC session running `claude` in the pancake directory
3. Sidebar on the right shows "▶ 1 pancake"
4. Click into the **mini terminal** (bottom-right pane) → `cc-new rag ~/workspace/personal/technical-rag`
5. New session tab appears, sidebar updates to show both
6. **Option+↑/↓** to switch between session tabs
7. Add more: `cc-new ops ~/workspace/personal/ops` from any mini terminal
8. Other Warp tabs remain plain terminals — no tmux, no sidebar

## Managing sessions

- **Add session**: `cc-new <name> [dir]` from the mini terminal
- **Rename session**: `Ctrl+a ,` then type a new name
- **Close session**: exit Claude Code → the window closes → sidebar auto-updates
- **Kill session**: `Ctrl+a &` to force-kill the current window
- **Create plain window** (no claude): `Ctrl+a c` — still gets sidebar+mini-terminal via hook
- **Re-attach**: just run `cc-start` again if detached

## Verification

1. Run `cc-start pancake ~/workspace/personal/pancake` — verify 3-pane layout appears
2. Verify sidebar shows "▶ 1 pancake" in the top-right
3. Verify mini terminal is accessible in the bottom-right (click into it)
4. From mini terminal, run `cc-new test /tmp` — verify new window is created with layout
5. Verify Option+↑/↓ switches between session tabs
6. Verify sidebar highlights the active session in each window
7. Verify Claude Code starts in the main pane of each window
