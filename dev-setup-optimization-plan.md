# Dev Setup Optimization Plan

Prioritized optimizations for the Claude Code + tmux + dotfiles workflow, identified from a full audit of CLAUDE.md, hooks, brain-os, and project configs.

## High Impact

### 1. Slim down global CLAUDE.md

The global CLAUDE.md is loaded into every session and consumes significant context. Most of its content is event-specific (learnings capture, PR review monitor, plan checkpoints) and only relevant when those events fire.

**Action:** Move event-specific instructions into the agents/skills that execute them:

- Session learnings capture workflow → `~/.claude/agents/learnings-capturer.md`
- PR review monitor protocol → `~/.claude/agents/pr-monitor.md`
- Plan file two-checkpoint flow → a dedicated skill or agent instruction

The global CLAUDE.md should contain only the minimal rules every session needs: framing protocol, dotfiles location, gt-over-git, pre-coding context gate, post-coding checks.

**Metric:** Measure CLAUDE.md line count before/after. Target: <100 lines (currently ~200+).

### 2. Batch promote brain-os learnings

9 learnings (13+ insights) all have `Status: pending`. The capture pipeline works but the promotion pipeline doesn't exist yet. Insights are trapped in session-specific files instead of in destination docs.

**Action:**

- Promote each pending learning into its suggested destination doc
- Add inline provenance at destination (`_Source: claude-learnings/...`\_)
- Update audit trail: set status to `promoted`, fill `Promoted to` and `Promoted on`
- Create missing destination docs: `graphite-conventions.md`, `dotfiles-conventions.md`

### 3. MCP-ify technical-rag system

The pre-coding context gate requires a manual round-trip: Claude stops, asks user, user queries RAG, pastes result back. This breaks flow on every non-trivial Rust task.

**Action:** Expose the technical-rag system as an MCP server so Claude Code can query it directly. The context gate becomes automatic — Claude fetches relevant conventions before writing code.

### 4. Clean up stale plan files in cove

`context-fix-plan.md` and `integration-cove-plan.md` are untracked in cove root. Either commit them (if in-progress) or delete them (if completed).

## Medium Impact

### 5. Profile hook latency

10 hook registrations fire across session lifecycle. PostToolUse on Bash fires 3 separate hooks. `validate-bash.py` (184 lines) runs on every Bash call.

**Action:**

- Add timestamp logging to hooks and measure per-hook latency over a session
- Identify any hooks adding perceptible delay (>100ms)
- Consolidate or simplify hot-path hooks (especially the bash validator, which overlaps with Claude Code's own permission system)

### 6. Add brain-os index

No README or table of contents. CLAUDE.md says "scan the directory" but there's no fast discovery mechanism.

**Action:** Add `README.md` to brain-os root with a one-line summary per convention doc and the learnings directory structure.

### 7. Prune ~/.claude/ storage (1.5GB)

- `debug/` — 330MB
- `telemetry/` — 258MB
- `projects/` — 466MB (84 projects, many likely stale)

**Action:** Delete debug logs older than 30 days. Remove project directories for repos no longer active. Consider a periodic cleanup script.

### 8. Add shell aliases for terminal pane

No shell aliases exist for common operations. The terminal pane (bottom-right in cove layout) is used for manual commands but has no shortcuts.

**Action:** Add aliases to zshrc (via dotfiles):

- `cb` → `cargo build`
- `ct` → `cargo test`
- `cc` → `cargo clippy -- -D warnings`
- `cf` → `cargo fmt`
- `gs` → `gt sync`
- `gst` → `gt state`

## Lower Impact

### 9. Remove unused gopls plugin

`gopls-lsp` is installed but Go isn't a primary language. Consuming plugin resources without benefit.

**Action:** Uninstall via Claude Code plugin management unless Go work is planned.

### 10. Scope auto-format hook per project

The auto-format PostToolUse hook checks file extension on every Write/Edit across all languages. Single-language projects (like cove = Rust) do unnecessary detection.

**Action:** Consider project-level hook overrides that skip extension detection for known single-language repos. Low priority — current overhead is minimal.

## Progress

- [ ] 1. Slim down global CLAUDE.md (move event-specific instructions to agents/skills)
- [ ] 2. Batch promote brain-os learnings (9 pending → promoted)
- [ ] 3. MCP-ify technical-rag system
- [ ] 4. Clean up stale plan files in cove
- [ ] 5. Profile hook latency
- [ ] 6. Add brain-os index README
- [ ] 7. Prune ~/.claude/ storage
- [ ] 8. Add shell aliases for terminal pane
- [ ] 9. Remove unused gopls plugin
- [ ] 10. Scope auto-format hook per project
