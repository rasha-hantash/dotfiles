## Prompt Framing

Before executing a new request, present a structured frame showing how you interpret it. If you have clarifying questions, disagreements, or think the user is solving the wrong problem — incorporate that into the framing, don't do a separate step.

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

## Dotfiles

System-level configs (shell, tmux, editor) live in `~/workspace/personal/dotfiles/` and are symlinked to their real locations. When modifying any dotfile (e.g., `~/.tmux.conf`, scripts in `~/.local/bin/`), edit the source in the dotfiles repo and the symlink propagates the change.

- **tmux config**: `dotfiles/tmux/tmux.conf` → `~/.tmux.conf`

After making changes, commit from the dotfiles repo so changes are tracked with git.

## Convention Docs (brain-os)

brain-os (`~/workspace/personal/explorations/brain-os/`) is the knowledge base for reusable conventions, patterns, and learnings. When starting work in an unfamiliar area or one that might have documented conventions, scan the directory (`ls` + `grep`) to check for relevant docs before proceeding.

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

**Goal:** Capture non-obvious insights, gotchas, and patterns as PRs to brain-os. Sessions can end abruptly (cove kill, context limit), so capture continuously — never defer to "session end."

**Proactive surfacing:** When you notice a non-obvious gotcha, surprising library behavior, a debugging technique that worked, a UI/UX pattern worth codifying, or any development insight — flag it immediately in the conversation. Don't wait.

**Mandatory capture triggers — act on these automatically:**

1. **After `gt submit`** — After publishing any PR, launch a background agent (`isolation: "worktree"`, working in the brain-os repo) to review the session and capture uncaptured learnings. This is mandatory, same as the PR monitor.
2. **Pre-compaction reminder** — The pre-compact hook injects a learnings reminder with session ID and previous learnings context. When you see it, immediately capture learnings before context is compressed. This is your last chance.
3. **Natural milestones** — After finishing a debugging session, resolving a complex issue, or completing a substantial piece of work, check for learnings worth capturing.

**Session-aware chaining:** Learnings compound across compaction cycles within a session. The pre-compact hook injects the session ID prefix and any previously captured learnings from `~/.claude/session-learnings-chain.md`. Use these to avoid duplicating earlier captures and to build on them.

**How to capture (background agent workflow):**

1. **Get session ID** from the pre-compact system message (look for `Session ID prefix: <id>`). Use the first 8 chars as `session_short`. If not available, fall back to `$CLAUDE_SESSION_ID` env var or use `"unknown"`.
2. **Check for existing PRs** from this session: `gh pr list --search "learnings/${session_short}" --state open`
3. **If existing PR found**, read its content with `gh pr view`. Compare with new learnings:
   - **Same topic area** → checkout branch, append to the learnings file, `gt modify`, `gt submit --no-interactive --publish`
   - **Different topic** → create a new file and branch (step 4-6)
   - **When in doubt, append** — fewer PRs is better for review.
4. Agent works in a brain-os worktree (`~/workspace/personal/explorations/brain-os/`).
5. **Create learnings file:** `claude-learnings/YYYY-MM-DD-<session_short>-<slug>.md`
6. Each learning entry includes:
   - **What:** the insight or gotcha
   - **Context:** what we were doing when we discovered it
   - **Suggested destination:** which brain-os doc this might belong in (e.g., `rust/rust-conventions.md`, `frontend-conventions.md`, or "new doc: X")
7. **Branch via** `gt create` under `learnings/<session_short>/` namespace (e.g., `learnings/abc12345/terminal-escape-gotchas`).
8. **Submit:** `gt submit --no-interactive --publish`
9. **Update chain file:** Write to `~/.claude/session-learnings-chain.md` with a summary of ALL learnings captured so far this session (not just the latest). This file is read by the pre-compact hook on the next compaction cycle to provide continuity.
10. Shares the Graphite PR link with the user.

**What counts as a learning:** non-obvious gotchas, debugging techniques that worked, architecture patterns, tool/library quirks, workflow improvements. **What doesn't:** session-specific context, things already documented, trivial/well-known facts.

## PR Review Monitor — Mandatory Post-Submit Step

**Every time** a PR is created or updated via `gt submit`, immediately launch a background sub-agent to monitor for CI/CD status and review comments. This is not optional — do it automatically without being asked.

**What the sub-agent monitors:**

1. **CI/CD checks** — poll `gh pr checks <number>` until all checks pass or fail. If a check fails, read the failure details and fix the issue (e.g., `cargo fmt`, clippy warnings, test failures). After fixing, `gt modify` + `gt submit --no-interactive --publish` and resume polling.
2. **Review comments** — poll `gh api repos/{owner}/{repo}/pulls/{number}/comments` for Mesa or human review comments. Triage and address actionable feedback.

**Polling cadence:** Check every 30 seconds for the first 5 minutes, then every 60 seconds after that. Stop after 15 minutes if everything is green and no new comments.

**Sub-agent launch:** Use `Task` tool with `run_in_background: true`. The sub-agent should have access to the worktree where the PR branch lives so it can make fixes if CI fails.
