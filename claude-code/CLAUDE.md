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

Follow this co-location pattern for React frontends. The core principle: shared code lives at the top level, page-specific code lives with the page.

### Next.js (App Router)

**Top-level directories** (`frontend/`) hold code shared across multiple pages:

- `components/` — reusable components used by more than one page
- `lib/` — shared utilities, API clients, helpers
- `types/` — shared TypeScript type definitions
- `hooks/` — shared custom React hooks (if needed)

**Page-scoped directories** (`app/<route>/`) hold code used only by that page:

- `components/` — components specific to this page
- `hooks/` — custom hooks specific to this page
- `lib/` — constants and helpers specific to this page
- `types/` — type definitions specific to this page

**Key rules:**

- Use barrel files (`index.ts`) for clean imports from each subdirectory.
- Follow Next.js App Router conventions (`page.tsx`, `layout.tsx`, `'use client'` directive).

### TanStack Router (Vite / Tauri)

**Top-level directories** (`src/`) hold code shared across multiple routes:

- `components/` — reusable components used by more than one route
- `api/` — shared API clients, query definitions, type definitions
- `lib/` — shared utilities and helpers
- `hooks/` — shared custom React hooks (if needed)
- `data/` — shared static/mock data

**Route-scoped directories** (`src/routes/<route>/`) hold code used only by that route:

- `components/` — components specific to this route
- `hooks/` — custom hooks specific to this route
- `lib/` — constants and helpers specific to this route
- `types/` — type definitions specific to this route

**Key rules:**

- Route files (`__root.tsx`, `index.tsx`, `about.tsx`) live in `src/routes/` and define the route component + loader. TanStack Router's file-based routing generates `routeTree.gen.ts` automatically.
- Use barrel files (`index.ts`) for clean imports from each subdirectory.

### General rules (all frameworks)

- If something is used by multiple pages/routes, it belongs at the top level. If it's only used by one page/route, co-locate it with that page/route.
- Each page/route directory is a self-contained module with its own `components/`, `hooks/`, `lib/`, and `types/` subdirectories as needed.

## Backend Structured Logging Convention

Always use structured JSON logging for any backend. Set this up at the entry point of the application.

**Core principles (language-agnostic):**

- Output logs as JSON to stdout.
- Always include source location (file and line number) in every log line.
- Initialize a single global/default logger so all code uses the same configuration.
- Use structured key-value pairs for all log data. Never use string interpolation or `fmt.Sprintf` in log messages.
- Log messages should be short, lowercase, descriptive labels (e.g., `"query failed"`, `"change accepted"`, `"version mismatch"`).
- Propagate request-scoped fields (like `request_id`) through context so they appear in every log within a request automatically.
- Use middleware to inject a `request_id` (UUID) into context at the start of every request.

**Log levels:**

- `Error` — unexpected failures (DB errors, encoding failures).
- `Warn` — bad client input (invalid IDs, missing headers).
- `Info` — successful business events (change created, request completed) and version conflicts.
- `Debug` — query-level detail (query executed, document not found).

**Data transformation logging:** When code silently filters, strips, or transforms data (e.g., removing null rows, stripping invalid characters, truncating fields), always log at `Info` level with context about what was changed. These are low-volume (only fire when something anomalous happens) and need to be visible in production for diagnosing data quality issues. Include enough structured fields to identify the source (file, page, table index, count of items affected).

### Example: Go with `log/slog`

**Logger initialization:**

- Use `slog.NewJSONHandler(os.Stdout, opts)` for JSON output to stdout.
- Always enable `AddSource: true` in `slog.HandlerOptions` so every log line includes the source file and line number.
- Set the default logger with `slog.SetDefault(...)` so all code uses the same logger.

**Context-aware logging:**

- Create a custom `ContextHandler` that wraps `slog.Handler` and extracts `slog.Attr` values from `context.Context` before logging. This allows request-scoped fields (like `request_id`) to appear in every log automatically.
- Provide an `AppendCtx(ctx, attrs...)` helper to attach attributes to context.
- Use middleware to inject a `request_id` (UUID) into context at the start of every request.

**Logging style:**

- Always use `slog.InfoContext(ctx, ...)`, `slog.ErrorContext(ctx, ...)`, etc. — never the non-context variants inside request handlers — so request-scoped fields are always included.
- Use structured key-value pairs: `slog.InfoContext(ctx, "change created", "document_id", id, "query_ms", duration)`.

## Dotfiles

System-level configs (shell, tmux, editor) live in `~/workspace/personal/dotfiles/` and are symlinked to their real locations. When modifying any dotfile (e.g., `~/.tmux.conf`, scripts in `~/.local/bin/`), edit the source in the dotfiles repo and the symlink propagates the change.

- **tmux config**: `dotfiles/tmux/tmux.conf` → `~/.tmux.conf`
- **CC session scripts**: `dotfiles/tmux/bin/` → `~/.local/bin/` (cove, cc-start, cc-new, tmux-sidebar)

After making changes, commit from the dotfiles repo so changes are tracked with git.

## Convention Docs (brain-os)

When working on code, read the relevant convention doc before making changes:

- **Rust** (general): Read `/Users/rashasaadeh/workspace/personal/brain-os/rust/rust-conventions.md`
- **Tauri backend** (`src-tauri/`): Read `/Users/rashasaadeh/workspace/personal/brain-os/rust/tauri.md`
- **TypeScript / React frontend** (`src/`): Read `/Users/rashasaadeh/workspace/personal/brain-os/frontend-conventions.md`
- **TanStack Router** (routing, navigation, route files): Read `/Users/rashasaadeh/workspace/personal/brain-os/tanstack-router-guide.md`

## Git Workflow — Graphite (gt)

Always use the Graphite MCP (`gt`) instead of raw `git` commands for creating branches and publishing code. Never use `git commit`, `git push`, or `git checkout -b` directly.

**Core commands:**

- Instead of `git commit`, use `gt create -m "message"` — creates a commit and a branch.
- Instead of `git push`, use `gt submit --no-interactive` — publishes the current branch and all downstack branches.
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

## PR Review Monitor

After pushing a PR (via `gt submit` or `git push`), automatically launch a background sub-agent to monitor for review comments and address them.

**Trigger:** Any time a PR is created or updated and pushed to a remote.

**Sub-agent behavior:**

1. Poll `gh api repos/{owner}/{repo}/pulls/{pr_number}/comments` and `gh api repos/{owner}/{repo}/pulls/{pr_number}/reviews` every 3 minutes.
2. Track addressed comment IDs to avoid re-processing.
3. When new review comments are detected:
   - Read each comment and the referenced file(s) locally.
   - Read relevant convention docs (brain-os, project CLAUDE.md) for context before making changes.
   - Make focused, minimal code changes that address only what the reviewer asked for.
   - Triage each comment into one of three actions:
     - **Address**: Make the code change and reply on the PR comment confirming the fix.
     - **Partially address**: Make a partial change, reply explaining what was done and what was intentionally left as-is (with reasoning).
     - **Reject**: Do not change the code. Reply on the PR comment with a clear explanation of why the feedback doesn't apply (e.g., the code already handles it, it's a deliberate design decision, or the reviewer misread the code).
   - Use `gh api` to reply to each review comment with the resolution (addressed, partially addressed, or rejected with reasoning).
   - For addressed and partially addressed comments, commit with: `fix: address review feedback — [brief description]` and include `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`.
   - Push to the PR branch.
4. Continue monitoring after pushing fixes.
5. Stop after 30 minutes of no new comments (10 polling cycles).

**Permission gating:**

Before launching the sub-agent, create the sentinel file so the PreToolUse hook auto-allows `git add/commit/push` and `sleep`:

```bash
touch ~/.claude/.pr-review-active
```

Instruct the sub-agent to remove the sentinel when it finishes (after the final polling cycle):

```bash
rm -f ~/.claude/.pr-review-active
```

**Sub-agent launch config:**

- Use `Task` tool with `subagent_type: "general-purpose"`, `run_in_background: true`, `mode: "bypassPermissions"`.
- Pass the repo path, branch name, PR number, owner/repo, and any project-specific context.
