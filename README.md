# Dotfiles

System-level configs for [Cove](https://github.com/rasha-hantash/cove) (Claude Code session manager), tmux, Ghostty, and Claude Code.

## Install

```bash
git clone https://github.com/rasha-hantash/dotfiles.git
cd dotfiles
./setup.sh
```

The setup script symlinks configs, builds Cove from source, and adds it to your PATH. It won't overwrite existing configs without asking.

## What's included

```
ghostty/config              # Ghostty theme + Cove keybinds
tmux/tmux.conf              # tmux config (Ctrl+A prefix, Catppuccin theme)
ccs/                        # Cove source (built by setup.sh)
claude-code/keybindings.json # Claude Code keybindings (Tab for autocomplete)
```

## Keyboard shortcuts

All shortcuts work from any pane. They use Ghostty keybinds to send tmux prefix sequences.

| Shortcut  | Action                                      |
| --------- | ------------------------------------------- |
| `⌘J`      | Focus Claude Code pane                      |
| `⌘M`      | Focus terminal pane                         |
| `⌘P`      | Focus session navigator                     |
| `⌘;`      | Detach (exit Cove, return to shell)         |
| `↑` / `↓` | Switch sessions (when navigator is focused) |
| `Enter`   | Select session and jump to Claude Code      |

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
