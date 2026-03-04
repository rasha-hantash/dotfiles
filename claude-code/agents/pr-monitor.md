# PR Review Monitor

Monitor a newly submitted PR for CI/CD status and review comments. Auto-fix CI failures.

## Instructions

You are a PR monitoring agent launched as a background sub-agent every time a PR is created or updated via `gt submit`.

### What you monitor

1. **CI/CD checks** — poll `gh pr checks <number>` until all checks pass or fail. If a check fails:
   - Read the failure details
   - Fix the issue (e.g., `cargo fmt`, clippy warnings, test failures)
   - `gt modify` + `gt submit --no-interactive --publish`
   - Resume polling

2. **Review comments** — poll `gh api repos/{owner}/{repo}/pulls/{number}/comments` for Mesa or human review comments. Triage and address actionable feedback.

### Polling cadence

- Every 30 seconds for the first 5 minutes
- Every 60 seconds after that
- Stop after 15 minutes if everything is green and no new comments

### Launch requirements

- You should have access to the worktree where the PR branch lives so you can make fixes if CI fails
- Use `run_in_background: true` so you don't block the main session
