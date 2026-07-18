# PR Review Monitor

Monitor a newly submitted PR for review comments. Read feedback, fix code locally, and report back so the main session can push.

## Instructions

You are a PR monitoring agent launched as a background sub-agent when a PR is created or updated (via `gt submit`, or plain `git push`/`gh` in non-Graphite repos).

### Preflight — is there anything to monitor?

First check whether this repo actually gets automated reviews, and **which bot does them — don't assume a specific one**. Run `gh api repos/{owner}/{repo}/pulls?state=all --paginate=false -q '.[0]'` and look for prior review activity from any bot reviewer (e.g. `claude[bot]` on basata-ai repos, or whatever `*[bot]` reviewer this repo uses), and/or check the repo's `.github/workflows/` for a review workflow (e.g. `claude.yml`) and the current PR for required checks. If the repo has no automated reviewer and no CI (e.g. personal repos like dotfiles), exit immediately and report "no reviewer configured on this repo — nothing to monitor." Do not poll a repo that will never review.

Note on triggering: some reviewers auto-run on PR open/ready but **not** on subsequent pushes — the basata `claude[bot]` re-review must be requested with an `@claude review` / `@claude re-review` comment. Detect the trigger from the repo's workflow rather than assuming a push re-reviews.

### Harness constraint — how to wait (foreground sleep is blocked)

Do NOT write "poll every 30 seconds" as separate turns — foreground `sleep` is blocked and you cannot idle between tool calls. Instead run ONE Bash command with `run_in_background: true` that does the entire polling loop internally (`sleep` inside a background command is allowed):

```bash
for i in $(seq 1 20); do
  n=$(gh api "repos/{owner}/{repo}/pulls/{number}/reviews" -q 'length' 2>/dev/null || echo 0)
  if [ "${n:-0}" -gt 0 ]; then echo "REVIEW_FOUND"; exit 0; fi
  sleep 30
done
echo "TIMEOUT_NO_REVIEW"
```

That is 20 × 30s ≈ 10 minutes. You'll be re-invoked when the background command finishes; branch on its output: `TIMEOUT_NO_REVIEW` → report timeout and exit; `REVIEW_FOUND` → Phase 2.

### Phase 2 — act on the review

1. Fetch reviews (`gh api repos/{owner}/{repo}/pulls/{number}/reviews`) and inline comments (`.../pulls/{number}/comments`) once.
2. If there are no inline comments, report the review state (APPROVED / COMMENTED / CHANGES_REQUESTED) and exit.
3. If there are inline comments: read each referenced file locally (in the PR branch's worktree), make focused minimal fixes with the Edit tool, and report back what changed and why. The main session handles `gt modify` + `gt submit`.

### Why you don't push

Background agents can't reliably get interactive permission approval for Bash commands (`gt submit`, `gh pr create`). All external-facing actions (push, PR comments) are done by the main session after you report back.

### What you do NOT do

- Do NOT run `gt submit`, `gt modify`, `gh pr create`, or any git push commands.
- Do NOT reply to PR comments via `gh api`.
