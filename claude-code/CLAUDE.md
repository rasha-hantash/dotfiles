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

## Validate Before Fixing

When you notice a problem, suboptimality, or potential improvement, do three things before proposing a fix:

1. **State your UX assumption** — what belief about the user's situation makes this an issue?
2. **Quantify the impact** — how often does it trigger? What's the actual cost?
3. **Check before proceeding** (for assumption-dependent and scope-expanding fixes)

**When to just proceed vs. when to check:**

| Category                                                                      | Action                              | Examples                                                                                                                     |
| ----------------------------------------------------------------------------- | ----------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **Aligned** — fix is obvious from context, convention, or prior feedback      | Just do it                          | Typo, style fix, following documented pattern, iterative debugging, applying a brain-os convention                           |
| **Assumption-dependent** — fix depends on how the user experiences the system | State assumption + quantify + check | "This is slow" (slow for whom?), "needs error handling" (does it actually fail?), "should use X not Y" (deployment context?) |
| **Scope-expanding** — fix touches something beyond what was asked             | Always check                        | Refactoring adjacent code, adding dependencies, changing interfaces, proposing architectural alternatives                    |

**The mental test:** "If I'm wrong about one assumption, does this fix become pointless or harmful?" If yes → state the assumption, check. If no → just do it.

**Collateral changes — explain, don't ask.** Small collateral improvements while doing requested work (rewriting a loop, deleting a stale line, tidying adjacent code) are fine without stopping to ask — but every one MUST be called out in the response with a one-line what + why. Never leave an unexplained diff; Rasha reviews by asking "why did we change this?" and the answer should already be in the message. Two things still require asking first: starting/stopping services or databases, and anything scope-expanding per the table above. When discussing a file, always give its directory/path.

**Examples:**

- "This function is O(n²)" → **Assumption:** n grows large enough to matter. **Measure:** n is always < 20, runs once per request. **Verdict:** fine, move on.
- "This uses the Anthropic SDK but claude -p would work" → **Assumption:** this runs interactively and latency matters. If it's a background batch job, the SDK adds complexity for no UX benefit. **Action:** state assumption, check.
- "This API call has no retry logic" → **Assumption:** failures are user-visible. **Measure:** called 500x/day, failures cause errors. **Verdict:** worth fixing, just do it.
- "These tests are slow" → **Assumption:** test speed bottlenecks the dev loop. **Measure:** full suite takes 3s. **Verdict:** not a problem.

## Verify Before Asserting

Any factual claim about system state — what a branch contains, what an API returns, which config is deployed where, whether a file/field/behavior exists — must be verified with a tool call BEFORE it is stated, not offered as an assumption for Rasha to check. If verification requires a permission (production reads, credentials, an external service), proactively ask for that specific permission instead of shipping an unverified claim. On the rare occasion something can't be verified, label it explicitly ("unverified — would need X to confirm"). Rasha should never have to reply "validate that" — proactive verification is the default.

## Ritual Promotion — second-occurrence rule

The moment the same multi-step ritual, fix, or workaround is performed for the SECOND time (within a session, or recognized from memory/brain-os as recurring), immediately propose promoting it to a skill or script: one or two lines — proposed name, what it automates, where it lives. Create it only after Rasha approves. Never let a ritual reach a third repetition unproposed.

## Dotfiles

System-level configs (shell, tmux, editor) live in `~/workspace/personal/explorations/dotfiles/` and are symlinked to their real locations. When modifying any dotfile (e.g., `~/.tmux.conf`, scripts in `~/.local/bin/`), edit the source in the dotfiles repo and the symlink propagates the change.

- **tmux config**: `dotfiles/tmux/tmux.conf` → `~/.tmux.conf`
- **Claude Code config**: `dotfiles/claude-code/` → `~/.claude/` (settings.json, CLAUDE.md, hooks/, commands/, agents/, skills/)

**After modifying ANY file under `~/.claude/`**, you MUST commit and push from the dotfiles repo (`~/workspace/personal/explorations/dotfiles/`). These files are symlinked — the edit propagates automatically, but it's not tracked in git until you commit in dotfiles. Use `gt create` + `gt submit --no-interactive --publish` from the dotfiles repo. This applies to hooks, settings.json, CLAUDE.md, commands, agents, and skills.

## Internal Tools

**Cove** (`~/workspace/personal/explorations/cove/`) — Rust CLI that manages multiple Claude Code sessions inside tmux. Do NOT guess how it works. If asked about cove internals (tmux pane creation, hook wiring, state detection), read its source code or its `CLAUDE.md` first.

## Convention Docs (brain-os + technical-rag)

brain-os (`~/workspace/personal/explorations/brain-os/`) is the knowledge base for reusable conventions, patterns, and learnings. A UserPromptSubmit hook auto-injects relevant docs based on keyword matching, but it may miss some. When working in an unfamiliar area, read `brain-os/index.md` — it's the canonical catalog of all convention docs with one-line descriptions. If the hook didn't inject something that looks relevant in the index, read the full doc directly.

### Knowledge Source Priority

When multiple knowledge sources have opinions on the same topic, follow this priority order:

1. **Brain-os convention docs** (auto-injected + index above) — manually curated, highest authority
2. **Installed public skills** — generic domain best practices, fill gaps where convention docs have no opinion
3. **technical-rag MCP** — deep reference for specific concepts from indexed technical books
4. **Brain-os claude learnings** (auto-injected when relevant) — raw session insights, unrefined, treat as supplementary

Brain-os conventions override public skills. Public skills override generic model knowledge.

### technical-rag

For deeper technical questions (language patterns, library usage, architecture decisions), use the `technical-rag` MCP tools to search indexed technical books:

- `search(question, top_k, tags)` — semantic search across all books
- `list_documents()` — see what's indexed
- `browse_sections(document_id)` — explore a book's structure

Requires the FastAPI backend running (`cd ~/workspace/personal/explorations/technical-rag/backend && uv run python main.py`).

## Project Plans

Plans live in **Linear documents**, not repo files.

**When a plan is ready (plan mode):** The plan presented for approval MUST state its Linear destination in a header line — e.g. `Plan doc → ENG-726`, `Plan doc → project "[CS] Referral Management"`, or `Plan doc → RAS team`. Approving the plan approves the destination; Rasha corrects it via plan feedback if wrong. Destination rules: a ticket referenced in the conversation → that issue; otherwise a clearly-mapped project → that project; ambiguous or personal work → the private **RAS** team (never guess a public team). After approval, write the plan to Linear automatically — do not ask whether to save it. The document title is a descriptive statement of what the plan achieves (e.g., "Reliable Learnings Capture — No Lost Knowledge"), not just a feature name. Include a `## Progress` section with all steps as unchecked items (`- [ ]`).

**NEVER ask to execute, and NEVER start executing on your own.** Plan approval means the plan is approved — nothing more. After saving the plan to Linear, share the doc link and end the turn. Execution begins only when Rasha explicitly says so ("go", "execute the plan", "start"). Do not ask "want me to start executing?" — she will say when.

**During execution (once told to):** Update the Linear doc's Progress section as steps complete — check off items (`- [x]`), add the date. On failure or deviation, add a note under the relevant step explaining what went wrong and the revised approach. The plan is a living document, not a snapshot. This is automatic — don't wait to be asked.

**At session start / when resuming:** If the work maps to a Linear issue or project, check its attached documents for a plan doc — its Progress section is the source of truth for what's done and what's next. (Legacy: some repos still contain committed `*-plan.md` files from the old convention; if one exists in the project root, read it too.)

**Pre-build validation — validate before building:** For plans involving multiple integrations, external APIs, or unfamiliar system behavior, surface and validate all technical assumptions BEFORE presenting the plan. Read `brain-os/claude/pre-build-validation.md` for the full process. The short version: list every assumption as validated/unvalidated/blocker, probe the unvalidated ones empirically (run commands, check APIs, test flags), and fix wrong assumptions in the plan before asking to execute. Do not present a plan with unvalidated assumptions on the critical path.

## Test-Driven Development

When building new features with testable behavior, write the test first, then the implementation. Follow RED-GREEN-REFACTOR: write a failing test (RED), write the minimum code to make it pass (GREEN), then clean up (REFACTOR). This applies to unit tests, integration tests, and API contract tests. Skip TDD for: UI/styling work, exploratory prototypes, config changes, and one-off scripts.

## Git Workflow — Graphite (gt)

Always use the Graphite MCP (`gt`) instead of raw `git` commands for creating branches and publishing code. Never use `git commit`, `git push`, or `git checkout -b` directly.

**Exception — plain-git repos:** basata-ai repos (and any repo without Graphite) use plain `git`/`gh` — `gt` fails there. In those repos use the stacked-prs skill's plain-git mechanics (`gh pr create --base`, `git rebase --update-refs`); the worktree-first rule still applies. `validate-bash.py` allow-lists these roots.

**Worktrees FIRST — before any edits (git repos only):** In any **git repository**, ALWAYS enter a worktree (`EnterWorktree` for main session, `isolation: "worktree"` for agents) BEFORE attempting any file edits. Do not try to edit first and wait for the branch guard to block you — proactively create the worktree as the very first step when you know edits are coming. Name worktrees descriptively based on the task (e.g., `reliable-learnings-capture`, `fix-sidebar-crash`). This applies to all repos, not just the current project. **If the current directory is NOT a git repository, skip worktree creation entirely and edit files directly.** Do not attempt `EnterWorktree` in non-git directories — it will fail. The `worktree-guard` hook enforces this automatically.

**Core commands:**

- Instead of `git commit`, use `gt create -m "message"` — creates a commit and a branch.
- Instead of `git push`, use `gt submit --no-interactive --publish` — publishes the current branch and all downstack branches. The `--publish` flag is required because `--no-interactive` defaults to draft mode, and draft PRs don't trigger CI/CD or automated PR review.
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

Proactively surface non-obvious insights during the session. When you notice a gotcha, surprising behavior, or useful pattern — flag it inline immediately. When applying a prior learning from brain-os, note it: _"Learning applied: [one sentence]."_

When the user asks to record a learning, write it **directly to the appropriate convention doc** in brain-os (e.g., `unix/xdg-conventions.md`, `rust/rust-conventions.md`, `claude/claude.md`). If it doesn't fit an existing directory, create a new topic directory (e.g., `design/`, `devops/`, `testing/`). Do not write to `claude-learnings/` — that directory is deprecated. Convention docs are what get auto-injected into sessions; anything not in a convention doc is invisible.

**Proactive capture triggers** — at these moments, check if there are non-obvious insights worth adding to brain-os convention docs:

1. After `gt submit`
2. Post-compaction (review compact summary for insights)
3. Natural milestones (debugging session complete, complex issue resolved)
4. Before suggesting `/clear`

## Agent Teams

When a task clearly involves 3+ independent work streams (e.g., "build a fullstack feature with frontend, backend, and tests"), proactively propose using Agent Teams in the framing step. Don't wait to be asked — suggest it so the user can confirm.

## PR Review Monitor

**Every time** a PR is created or updated (via `gt submit`, or plain `git push`/`gh` in non-Graphite repos) **in a repo that has an automated PR reviewer configured**, launch the `pr-monitor` agent (see `~/.claude/agents/pr-monitor.md`) as a background sub-agent. This is automatic — don't wait to be asked. Skip repos with no reviewer configured (e.g. personal dotfiles) — the agent definition includes the preflight check.

**The reviewer varies by repo — don't assume a specific one.** basata-ai repos use the **Claude GitHub bot** (`claude[bot]` via `.github/workflows/claude.yml`), which only auto-runs on non-draft PR open/ready and must be re-triggered with an `@claude review` / `@claude re-review` comment (a plain push does not re-review). Other repos may use a different bot. Detect the actual reviewer from the repo's prior review activity / workflows rather than defaulting to any one tool.
