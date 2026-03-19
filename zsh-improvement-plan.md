> **Archived 2026-03-17** — 100%, Phase 6 explicitly deferred

# Zsh Configuration Improvement Plan

Improvements to apply on top of the baseline zsh configs in `zsh/`. Each phase is independent and can be done incrementally.

## Phase 1: Reorganize content across zshenv / zprofile / zshrc

**Principle:** `.zshenv` runs for ALL shells (interactive, non-interactive, scripts, cron). `.zprofile` runs once per login session. `.zshrc` runs for every interactive shell.

**Move to `.zshenv`** (needed by non-interactive shells):

- `GOPATH` + go bin PATH (fix current `GO_PATH` typo and `/$GO_PATH` bug on lines 215-216)
- Cargo PATH
- `EDITOR` (not currently set — add `export EDITOR=nvim` or preferred editor)
- `LANG=en_US.UTF-8`

**Move to `.zprofile`** (login-time, run once):

- PostgreSQL PATH
- pnpm HOME + PATH
- Bun install + PATH
- Windsurf PATH
- De-duplicate `$HOME/.local/bin` (appears 3x currently — keep 1 in `.zprofile`)

## Phase 2: Secret management

- `~/.zsh_secrets` already created during symlink setup
- `zsh/zsh_secrets.template` has all variable names with empty values
- Ensure `chmod 600 ~/.zsh_secrets` on all machines
- Never source secrets in `.zshenv` (would expose to non-interactive scripts)

## Phase 3: Plugin improvements

**Current plugins:** `git docker docker-compose zsh-syntax-highlighting colored-man-pages` + `zsh-autosuggestions` (via brew)

| Action  | Plugin                                                 | Reason                                                                 |
| ------- | ------------------------------------------------------ | ---------------------------------------------------------------------- |
| REPLACE | `zsh-syntax-highlighting` → `fast-syntax-highlighting` | 2-10x faster, better accuracy, actively maintained                     |
| ADD     | `z`                                                    | Frecency-based directory jumping (`z proj` → last visited project dir) |
| ADD     | `history-substring-search`                             | Type partial command + up arrow to search history                      |
| ADD     | `fzf`                                                  | Fuzzy Ctrl+R history, Ctrl+T file finder, Alt+C directory jump         |
| MOVE    | `zsh-autosuggestions`                                  | From brew source to oh-my-zsh custom plugin for consistency            |
| KEEP    | `git`, `docker`, `docker-compose`, `colored-man-pages` | Useful completions and aliases, no perf cost                           |

**Install custom plugins (one-time):**

```sh
# fast-syntax-highlighting (replaces zsh-syntax-highlighting)
git clone https://github.com/zdharma-continuum/fast-syntax-highlighting \
  ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/fast-syntax-highlighting

# zsh-autosuggestions (move from brew to oh-my-zsh custom)
git clone https://github.com/zsh-users/zsh-autosuggestions \
  ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-autosuggestions

# history-substring-search
git clone https://github.com/zsh-users/zsh-history-substring-search \
  ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-history-substring-search
```

**Updated plugins line:**

```sh
plugins=(
  git
  docker
  docker-compose
  z
  fzf
  history-substring-search
  zsh-autosuggestions
  colored-man-pages
  fast-syntax-highlighting  # must be last
)
```

Remove the separate `source $(brew --prefix)/share/zsh-autosuggestions/zsh-autosuggestions.zsh` line.

## Phase 4: Lazy-load NVM

NVM adds ~400-800ms to shell startup. Replace eager init with lazy loading:

```sh
# Lazy-load NVM — only initializes when you first call nvm, node, npm, npx, or yarn
export NVM_DIR="$HOME/.nvm"
lazy_load_nvm() {
  unset -f nvm node npm npx yarn
  [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
  [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
}
nvm()  { lazy_load_nvm; nvm "$@"; }
node() { lazy_load_nvm; node "$@"; }
npm()  { lazy_load_nvm; npm "$@"; }
npx()  { lazy_load_nvm; npx "$@"; }
yarn() { lazy_load_nvm; yarn "$@"; }
```

**Measure before/after:** `time zsh -i -c exit`

## Phase 5: Cleanup

- Fix `GO_PATH` → `GOPATH` and `/$GO_PATH` → `$GOPATH` (current code produces invalid path `/~/go`)
- Replace hardcoded `/Users/rashasaadeh/` with `$HOME` in bun completions, pipx PATH, Windsurf PATH, cargo PATH
- De-duplicate PATH entries (`$HOME/.local/bin` appears 3 times)

## Phase 6: Modular structure (defer)

After cleanup, zshrc will be ~50 lines. Skip splitting into separate sourced files unless it grows past 150 lines. Revisit if aliases or functions accumulate.

## Progress

- [x] Phase 1: Reorganize content across zshenv / zprofile / zshrc (2026-03-06)
- [x] Phase 2: Create zsh_secrets.template (2026-03-06, included in initial PR)
- [x] Phase 3: Plugin improvements (2026-03-06)
- [x] Phase 4: Lazy-load NVM (2026-03-06)
- [x] Phase 5: Cleanup — merged with Phase 1 (GO_PATH fix, $HOME normalization, PATH dedup) (2026-03-06)
- [ ] Phase 6: Modular structure (deferred — only if file grows past 150 lines)

## Testing after merge

### 1. Install custom plugins (one-time, required before opening a new shell)

```sh
# fast-syntax-highlighting (replaces zsh-syntax-highlighting)
git clone https://github.com/zdharma-continuum/fast-syntax-highlighting \
  ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/fast-syntax-highlighting

# zsh-autosuggestions (move from brew to oh-my-zsh custom)
git clone https://github.com/zsh-users/zsh-autosuggestions \
  ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-autosuggestions

# history-substring-search
git clone https://github.com/zsh-users/zsh-history-substring-search \
  ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-history-substring-search
```

Also ensure `fzf` is installed: `brew install fzf`

### 2. Measure shell startup time (before and after)

```sh
# Run BEFORE sourcing the new config (in current shell)
time zsh -i -c exit

# Open a new terminal tab (sources new config), then run again
time zsh -i -c exit
```

Expect ~400-800ms improvement from NVM lazy-loading.

### 3. Verify env vars are in the right files

```sh
# zshenv vars should be available in non-interactive shells (scripts)
zsh -c 'echo "EDITOR=$EDITOR GOPATH=$GOPATH LANG=$LANG"'

# zprofile vars should be available in login shells
zsh -l -c 'echo "PATH includes local/bin: $(echo $PATH | grep -o "$HOME/.local/bin")"'
```

### 4. Test new plugins

```sh
# z — cd to a few directories first, then jump back by keyword
cd ~/workspace/personal/explorations/brain-os
cd ~/workspace/personal/explorations/dotfiles
z brain    # should jump to brain-os

# fzf — fuzzy history search
# Press Ctrl+R, type a partial command, select with arrow keys

# history-substring-search
# Type a partial command (e.g., "git"), press Up arrow to cycle matches

# fast-syntax-highlighting
# Type a command — valid commands should be green, invalid should be red
```

### 5. Test NVM lazy-loading

```sh
# NVM shouldn't be loaded yet (wrapper functions in place)
type nvm       # should show "nvm is a shell function"

# First call triggers lazy load
node --version # should work, but takes a moment on first call

# Subsequent calls are instant
node --version # fast now
```

### 6. Verify secrets still load

```sh
# Should show your API keys (if ~/.zsh_secrets exists)
echo $ANTHROPIC_API_KEY | head -c 10
```

### Rollback

If something breaks, the original files are still in git history. To revert:

```sh
cd ~/workspace/personal/explorations/dotfiles
git log --oneline -5  # find the commit before the changes
git checkout <commit> -- zsh/zshrc zsh/zprofile zsh/zshenv
```
