# Plan: Brown/Earth-Tone Terminal Theme

## Context

The current terminal uses Catppuccin Mocha (cool blue/purple tones). The user likes the warm brown palette from the Clove screenshot — dark chocolate background, golden-amber accents, warm tan text — and wants to adopt it across the terminal setup.

Both Ghostty and tmux colors are intentionally coordinated (background colors match so pane borders disappear), so both configs must update together.

## Color Palette (extracted from screenshot)

| Role         | Hex       | Description                          |
| ------------ | --------- | ------------------------------------ |
| Background   | `#1c1412` | Very dark chocolate                  |
| Active BG    | `#161010` | Slightly darker (focused panes)      |
| Foreground   | `#d4b896` | Warm parchment                       |
| Accent       | `#c49a3c` | Golden amber (prompts, borders)      |
| Dim text     | `#6b5444` | Muted brown                          |
| Terracotta   | `#a65a3e` | Red replacement (active tab, errors) |
| Olive        | `#8a7a3a` | Green replacement                    |
| Sienna       | `#9c6b5a` | Magenta replacement                  |
| Taupe        | `#7a6652` | Blue replacement                     |
| Tan          | `#a89070` | Cyan replacement                     |
| Cream        | `#ede0cc` | Bright white                         |
| Dark brown   | `#302420` | ANSI black                           |
| Medium brown | `#5a4a3a` | Bright black (comments)              |
| Selection    | `#3a2a1e` | Selection background                 |
| Dark panel   | `#2a1e18` | Message/overlay bg                   |

## Changes

### 1. `ghostty/config` — Full brown palette

Replace background/foreground and add ANSI palette + cursor/selection colors:

```
# Warm brown — matches tmux unfocused bg so borders disappear
background = 1c1412
foreground = d4b896
cursor-color = c49a3c
selection-background = 3a2a1e
selection-foreground = ede0cc

# ANSI palette (brown/earth tones)
palette = 0=#302420
palette = 1=#a65a3e
palette = 2=#8a7a3a
palette = 3=#c49a3c
palette = 4=#7a6652
palette = 5=#9c6b5a
palette = 6=#a89070
palette = 7=#d4b896
palette = 8=#5a4a3a
palette = 9=#c47050
palette = 10=#b8a050
palette = 11=#dab060
palette = 12=#9c8a70
palette = 13=#c48a70
palette = 14=#c4aa88
palette = 15=#ede0cc
```

Keep all existing keybinds and settings unchanged.

### 2. `tmux/tmux.conf` — Coordinated brown theme

Update all color references from Catppuccin Mocha to matching browns:

| Setting                    | Old (Catppuccin) | New (Brown) |
| -------------------------- | ---------------- | ----------- |
| Pane border fg             | `#f9e2af`        | `#c49a3c`   |
| Pane border bg / window bg | `#1e1e2e`        | `#1c1412`   |
| Window active bg           | `#181825`        | `#161010`   |
| Status bar bg              | `#1e1e2e`        | `#1c1412`   |
| Status bar fg              | `#cdd6f4`        | `#d4b896`   |
| Status left (label)        | `#b4befe`        | `#c49a3c`   |
| Status left separator      | `#45475a`        | `#3a2a1e`   |
| Status right (clock)       | `#6c7086`        | `#6b5444`   |
| Active tab bg              | `#fab387`        | `#a65a3e`   |
| Active tab fg              | `#1e1e2e`        | `#1c1412`   |
| Inactive tab fg            | `#6c7086`        | `#6b5444`   |
| Message bg                 | `#313244`        | `#2a1e18`   |
| Message fg                 | `#cdd6f4`        | `#d4b896`   |

## Files Modified

- `ghostty/config` — add palette, update bg/fg
- `tmux/tmux.conf` — update all color values

## Verification

1. Restart Ghostty (or `ghostty +reload-config`) to pick up new colors
2. Open a tmux session — check that pane borders blend with background
3. Verify text readability: `ls --color`, `git log`, syntax-highlighted code
4. Check tmux status bar shows golden accents on dark brown
