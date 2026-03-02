## Permission Surfacing

Before starting exploratory or multi-step work, present a summary of the tools and actions you'll need (e.g., "I'll need to read files in X, grep for Y, run Z commands") so the user can batch-approve upfront rather than getting interrupted by individual permission prompts.

## Response Protocol

Before acting on a request, consider whether you have clarifying questions, disagreements, or think I'm solving the wrong problem entirely. If you do, lead with that before answering — be direct, not diplomatic. If the request is clear and you have no pushback, just proceed.

## Prompt Framing

Before executing a new request, present a structured frame showing how you interpret it. This replaces the old hat-picking convention with full transparency.

**Format:**

> **Persona:** [expert role + key lens, e.g., "Backend engineer — focusing on API design and data modeling"]
> **Constraints:** [key boundaries — conventions to follow, things to avoid, scope limits]
>
> **Context:** [files, images, prior conversation, or domain knowledge being used]
> **Task:** [the core question or action]
> **Output:** [what the deliverable looks like — code, explanation, list, plan, etc.]
>
> Should I proceed with this framing?

**This is a real checkpoint.** Always wait for the user to confirm the framing before doing any work (exploring code, asking follow-up questions, writing code). Present the framing, ask "Should I proceed with this framing?" using AskUserQuestion (Yes/No), and only continue after getting a "Yes." If the user says "No," ask what to change and re-present the updated framing for another round of confirmation.

**When to skip framing:**

- Follow-up messages in an ongoing conversation where the frame is already established
- Simple confirmations ("yes", "looks good", "go ahead")
- Trivial requests (typo fixes, "what does X mean", one-liner questions with obvious answers)
- When the user says "just answer" or explicitly skips framing

**How it works with Response Protocol:**
If you have pushback (per Response Protocol), incorporate it into the framing — e.g., present an alternative task interpretation or flag that the user might be solving the wrong problem. Don't do two separate steps.

## Frontend Structure Convention

See `brain-os/frontend-conventions.md` — "Directory Structure — Co-location Pattern" section.

## Backend Structured Logging Convention

See `brain-os/logging-conventions.md`.

## Dotfiles

System-level configs (shell, tmux, editor) live in `~/workspace/personal/dotfiles/` and are symlinked to their real locations. When modifying any dotfile (e.g., `~/.tmux.conf`, scripts in `~/.local/bin/`), edit the source in the dotfiles repo and the symlink propagates the change.

- **tmux config**: `dotfiles/tmux/tmux.conf` → `~/.tmux.conf`
- **CC session scripts**: `dotfiles/tmux/bin/` → `~/.local/bin/` (cove, cc-start, cc-new, tmux-sidebar)

After making changes, commit from the dotfiles repo so changes are tracked with git.

## Convention Docs (brain-os)

brain-os (`~/workspace/personal/brain-os/`) is the knowledge base for reusable conventions, patterns, and learnings. When starting work in an unfamiliar area or one that might have documented conventions, scan the directory (`ls` + `grep`) to check for relevant docs before proceeding. The backlinks below cover known categories, but new docs may exist from triaged session learnings.

When working on code, read the relevant convention doc before making changes:

- **Rust** (general): Read `/Users/rashasaadeh/workspace/personal/brain-os/rust/rust-conventions.md`
- **Tauri backend** (`src-tauri/`): Read `/Users/rashasaadeh/workspace/personal/brain-os/rust/tauri.md`
- **TypeScript / React frontend** (`src/`): Read `/Users/rashasaadeh/workspace/personal/brain-os/frontend-conventions.md`
- **TanStack Router** (routing, navigation, route files): Read `/Users/rashasaadeh/workspace/personal/brain-os/tanstack-router-guide.md`
- **Backend logging**: Read `/Users/rashasaadeh/workspace/personal/brain-os/logging-conventions.md`
- **PR review monitor**: Read `/Users/rashasaadeh/workspace/personal/brain-os/claude/pr-review-monitor.md`
- **Pre-build validation** (complex features): Read `/Users/rashasaadeh/workspace/personal/brain-os/claude/pre-build-validation.md`
- **Git** (hooks, branching, worktrees, Graphite gotchas): Read `/Users/rashasaadeh/workspace/personal/brain-os/git/git.md`

## Git Workflow — Graphite (gt)

Always use the Graphite MCP (`gt`) instead of raw `git` commands for creating branches and publishing code. Never use `git commit`, `git push`, or `git checkout -b` directly.

**Core commands:**

- Instead of `git commit`, use `gt create -m "message"` — creates a commit and a branch.
- Instead of `git push`, use `gt submit --no-interactive` — publishes the current branch and all downstack branches.
- After `gt submit`, always share the **Graphite PR link** (`https://app.graphite.com/github/pr/...`) with the user, not the GitHub PR link. Graphite is the primary review UI.
- Use `gt modify` to amend the current branch and rebase upstack PRs.
- Use `gt sync` to pull latest trunk and rebase all open stacks.

**Stacking strategy — one stack per feature:**

- Group related changes for the same feature into a single stack. Each diff (commit) in the stack should be a focused, reviewable unit of work within that feature.
- Different features get different stacks. Never mix unrelated features into one stack.
- Before writing code, propose the stack structure (how many diffs, what each one covers) and get confirmation before proceeding.
- Keep each diff small and self-contained — it should be independently reviewable even though it's part of a larger feature stack.

**Iterative fixes in a single conversation:**

When debugging or applying multiple fixes across conversational turns within the same session, batch them into a single branch/PR rather than creating a new stack per fix. Graphite's merge queue is slow even for one PR — don't multiply that.

- On the first fix, `gt create` as usual to start the branch.
- On subsequent fixes in the same conversation, use `gt modify` to amend the existing branch instead of creating new ones.
- Only `gt submit --no-interactive` once at the end (or when the user asks to push), not after every fix.
- If the fixes are truly unrelated (different features/areas), ask before batching — but default to batching within a single debugging session.

**Example workflow for a feature with 3 diffs:**

1. Write code for diff 1 → `git add` → `gt create -m "feat: add user model"`
2. Write code for diff 2 → `git add` → `gt create -m "feat: add user API endpoints"`
3. Write code for diff 3 → `git add` → `gt create -m "feat: add user UI components"`
4. `gt submit --no-interactive` — publishes the entire stack.

## Frontend Testing Philosophy

Use Playwright for all actual frontend tests. Use Claude-in-Chrome as a development-time assistant to look at pages, help write those Playwright tests, and debug when things go wrong. Claude-in-Chrome is the pair programmer who can see the screen — not the test runner.

- **Playwright** — deterministic, headless, runs in CI, has proper assertions. Owns regression tests and every user-facing flow.
- **Claude-in-Chrome** — use for "does this look right?" checks during development, writing new Playwright tests (look at the page first, then write the test), debugging failing tests (reproduce visually), and responsive design spot-checks.
- Prefer semantic selectors (`getByRole`, `getByText`, `getByTestId`) over CSS selectors in Playwright tests.

## Post-coding checks

After writing or modifying significant code (new features, bug fixes, refactors), use the `/ci` skill to run linters, tests, and perf pattern checks before reporting completion. Skip for documentation, config changes, or trivial edits. This applies to all agents, including teammates.

For deeper analysis, use `/perf-review` (performance review) or `/test-runner` (full test suite).

## Session Learnings

**Proactive surfacing:** When you notice a non-obvious gotcha, surprising library behavior, a debugging technique that worked, a UI/UX pattern worth codifying, or any development insight — flag it immediately in the conversation. Don't wait until the end.

**End-of-session capture:** Before wrapping up a session, review the conversation for learnings and create a file in `~/workspace/personal/brain-os/claude-learnings/` with the format `YYYY-MM-DD-<short-slug>.md`. Each learning entry should include:

- **What:** the insight or gotcha
- **Context:** what we were doing when we discovered it
- **Suggested destination:** which brain-os doc this might belong in (e.g., `rust/rust-conventions.md`, `frontend-conventions.md`, or "new doc: X")

Then open a PR to brain-os via `gt create` + `gt submit --no-interactive` so the user can triage and merge.

## PR Review Monitor — Mandatory Post-Submit Step

**Every time** a PR is created or updated via `gt submit`, immediately launch a background sub-agent to monitor for Mesa review comments and address them. This is not optional — do it automatically without being asked.

**Full behavior, polling logic, triage rules, and launch config**: See `brain-os/claude/pr-review-monitor.md`.
