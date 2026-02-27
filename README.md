# CCS — Claude Code Sessions

A tmux-based session manager for running multiple [Claude Code](https://docs.anthropic.com/en/docs/claude-code) instances side by side. Each session gets a dedicated layout with Claude Code, a terminal, and a session navigator — all controlled with keyboard shortcuts.

```
┌──────────────────────────────────┐
│                                  │
│          claude code             │
│                                  │
├──────────────────────┬───────────┤
│      terminal        │ sessions  │
└──────────────────────┴───────────┘
```

## Requirements

- [Ghostty](https://ghostty.org/) terminal
- [tmux](https://github.com/tmux/tmux) (3.3+)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI (`claude`)

## Install

```bash
git clone https://github.com/rasha-hantash/dotfiles.git
cd dotfiles
./setup.sh
```

The setup script symlinks configs and adds `ccs` to your PATH. It won't overwrite existing configs without asking.

## Usage

```bash
ccs start myproject ~/code/myproject    # Start CCS with a session
ccs start backend ~/code/backend        # Add another session tab
ccs list                                # List active sessions
ccs kill backend                        # Kill a specific session
ccs all-kill                            # Kill all sessions
```

To re-attach after detaching: `ccs start` (detects the existing session and re-attaches).

### Worktrees

To work on multiple branches of the same repo in parallel, start a new session and either create the worktree yourself or let Claude do it:

```bash
# Option A: Create a worktree yourself, then start a session in it
git -C ~/code/myproject worktree add ~/code/myproject-fix fix-branch
ccs start myproject-fix ~/code/myproject-fix

# Option B: Start a session on the same repo and ask Claude to create a worktree
ccs start myproject-fix ~/code/myproject
# Then tell Claude: "work in a worktree for fix-branch"
```

Use the session navigator (`⌘P` + arrow keys) to switch between them. Session names must be unique.

## Keyboard shortcuts

All shortcuts work from any pane. They use Ghostty keybinds to send tmux prefix sequences.

| Shortcut  | Action                                      |
| --------- | ------------------------------------------- |
| `⌘J`      | Focus Claude Code pane                      |
| `⌘M`      | Focus terminal pane                         |
| `⌘P`      | Focus session navigator                     |
| `⌘;`      | Detach (exit CCS, return to shell)          |
| `↑` / `↓` | Switch sessions (when navigator is focused) |
| `Enter`   | Select session and jump to Claude Code      |

### Why these keys?

Ghostty keybinds can't override keys that are bound to macOS menu items. `⌘D` and `⌘+Shift+D` are Ghostty's built-in split shortcuts, and `⌘E` is macOS "Use Selection for Find" — all three get intercepted before the keybind config applies. The keys above (`J`, `M`, `P`, `;`) are free at both the Ghostty and macOS level.

## What's included

```
ghostty/config              # Ghostty theme + CCS keybinds
tmux/tmux.conf              # tmux config (Ctrl+A prefix, Catppuccin theme)
tmux/bin/ccs                # Session manager script
tmux/bin/tmux-sidebar       # Interactive session navigator
claude-code/keybindings.json # Claude Code keybindings (Tab for autocomplete)
```

## Customizing keybinds

Edit `ghostty/config` to change shortcuts. The format is:

```
keybind = cmd+KEY=text:\x01TMUX_KEY
```

`\x01` is Ctrl+A (the tmux prefix). The tmux key mappings are defined in `tmux/tmux.conf`:

```
bind f select-pane -t :.1    # Claude Code (top)
bind m select-pane -t :.2    # Terminal (bottom-left)
bind s select-pane -t :.3    # Session navigator (bottom-right)
bind d detach-client          # Detach
```

When choosing new Ghostty keybinds, avoid keys that conflict with Ghostty defaults (`⌘D`, `⌘T`, `⌘W`, `⌘N`, `⌘K`, etc.) or macOS system shortcuts (`⌘C`, `⌘V`, `⌘Q`, `⌘H`, `⌘E`). Run `ghostty +list-keybinds --default` to see all Ghostty defaults.
