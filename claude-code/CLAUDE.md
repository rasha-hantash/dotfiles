## Prompt Framing

Before executing a new request, present a brief structured frame showing how you interpret it, then proceed immediately. No confirmation needed — the user can interrupt if the framing is wrong.

**Format:**

> **Persona:** [expert role + key lens]
> **Task:** [the core question or action]
> **Constraints:** [key boundaries — conventions, scope limits]

Then start working. If you have clarifying questions or think the user is solving the wrong problem, incorporate that into the framing and pause only for that.

**When to skip framing entirely:**

- Follow-up messages in an ongoing conversation where the frame is already established
- Simple confirmations ("yes", "looks good", "go ahead")
- Trivial requests (typo fixes, "what does X mean", one-liner questions)
- Debugging iterations within an established context
- When the task and constraints are unambiguous from context
- When the user says "just answer" or explicitly skips framing

## Dotfiles

System-level configs (shell, tmux, editor) live in `~/workspace/personal/dotfiles/` and are symlinked to their real locations. When modifying any dotfile (e.g., `~/.tmux.conf`, scripts in `~/.local/bin/`), edit the source in the dotfiles repo and the symlink propagates the change.

- **tmux config**: `dotfiles/tmux/tmux.conf` → `~/.tmux.conf`

After making changes, commit from the dotfiles repo so changes are tracked with git.

## Internal Tools

**Cove** (`~/workspace/personal/explorations/cove/`) — Rust CLI that manages multiple Claude Code sessions inside tmux. Do NOT guess how it works. If asked about cove internals (tmux pane creation, hook wiring, state detection), read its source code or its `CLAUDE.md` first.

## Convention Docs (brain-os + technical-rag)

brain-os (`~/workspace/personal/explorations/brain-os/`) is the knowledge base for reusable conventions, patterns, and learnings. When starting work in an unfamiliar area or one that might have documented conventions, scan the directory (`ls` + `grep`) to check for relevant docs before proceeding.

For deeper technical questions (language patterns, library usage, architecture decisions), use the `technical-rag` MCP tools to search indexed technical books:
- `search(question, top_k, tags)` — semantic search across all books
- `list_documents()` — see what's indexed
- `browse_sections(document_id)` — explore a book's structure

Requires the FastAPI backend running (`cd ~/workspace/personal/explorations/technical-rag/backend && uv run python main.py`).

## Project Plans

At session start, look for a plan file in the project root — any `.md` file with "plan" in the name (e.g., `PLAN.md`, `context-view-plan.md`, `debug-plan.md`). If one exists:

- **Read it first** before doing any work. The Progress section is the source of truth for what's done and what's next.
- **After completing a documented step:** Update the Progress section — check off the item (`- [x]`), add the date. If blocked or failed, note why inline.
- **On failure or deviation:** Add a note under the relevant step explaining what went wrong and the revised approach.

This is automatic — don't wait to be asked. After `/clear`, the file on disk still has progress, so re-reading it on the next session recovers state.

**Creating plan files — two-checkpoint flow:**

When a plan is ready (before calling `ExitPlanMode`), do NOT jump straight to requesting approval. Instead:

1. **Ask to save:** "Want me to save this plan to a file?" If yes, write it to `<descriptive-name>-plan.md` in the project root (e.g., `auth-migration-plan.md`, `debug-panel-plan.md`). The file name should be a short kebab-case summary of the plan's purpose. Include a `## Progress` section with all steps as unchecked items (`- [ ]`).
2. **Ask to execute:** "Want me to start executing?" The user may say no — they might want to review the file, share it, or come back later. Respect that.

Both checkpoints are mandatory. Never skip from plan approval to execution without offering to persist the plan first.

## Git Workflow — Graphite (gt)

Always use the Graphite MCP (`gt`) instead of raw `git` commands for creating branches and publishing code. Never use `git commit`, `git push`, or `git checkout -b` directly.

**Worktrees by default:** When creating PRs, always use a worktree (`isolation: "worktree"` in Task tool, or `EnterWorktree` for the main session) so changes are made on an isolated copy of the repo. This keeps `main` clean and avoids accidental commits on the wrong branch.

**Core commands:**

- Instead of `git commit`, use `gt create -m "message"` — creates a commit and a branch.
- Instead of `git push`, use `gt submit --no-interactive --publish` — publishes the current branch and all downstack branches. The `--publish` flag is required because `--no-interactive` defaults to draft mode, and draft PRs don't trigger CI/CD or Mesa reviews.
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
- Only `gt submit --no-interactive --publish` once at the end (or when the user asks to push), not after every fix.
- If the fixes are truly unrelated (different features/areas), ask before batching — but default to batching within a single debugging session.

**Example workflow for a feature with 3 diffs:**

1. Write code for diff 1 → `git add` → `gt create -m "feat: add user model"`
2. Write code for diff 2 → `git add` → `gt create -m "feat: add user API endpoints"`
3. Write code for diff 3 → `git add` → `gt create -m "feat: add user UI components"`
4. `gt submit --no-interactive --publish` — publishes the entire stack.

## Post-coding checks

After writing or modifying significant code (new features, bug fixes, refactors), use the `/ci` skill to run linters, tests, and perf pattern checks before reporting completion. Skip for documentation, config changes, or trivial edits. This applies to all agents, including teammates.

For deeper analysis, use `/perf-review` (performance review) or `/test-runner` (full test suite).

## Session Learnings

Proactively surface non-obvious insights during the session. When you notice a gotcha, surprising behavior, or useful pattern — flag it inline immediately. When applying a prior learning from brain-os, note it: *"Learning applied: [one sentence]."*

**Mandatory capture triggers** — after each of these, launch the `learnings-capturer` agent (see `~/.claude/agents/learnings-capturer.md`):

1. After `gt submit`
2. Post-compaction (review compact summary for insights)
3. Natural milestones (debugging session complete, complex issue resolved)
4. Before suggesting `/clear`

## PR Review Monitor

**Every time** a PR is created or updated via `gt submit`, launch the `pr-monitor` agent (see `~/.claude/agents/pr-monitor.md`) as a background sub-agent. This is automatic — don't wait to be asked.
