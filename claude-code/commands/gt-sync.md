---
description: Sync all git repos in ~/workspace/personal/explorations/ using Graphite (gt sync), cleaning up merged branches and resolving issues.
---

## Your Task

Sync all git repos in `~/workspace/personal/explorations/` using Graphite. For each repo, pull the latest trunk, rebase open stacks, and clean up merged/stale branches.

## Steps

### 1. Discover repos

List all directories in `~/workspace/personal/explorations/` that contain a `.git` directory. Print the list so the user can see which repos will be synced.

### 2. Sync each repo

For each repo, run the following process **sequentially** (one repo at a time):

1. **Print a header** with the repo name so progress is clear.
2. **Check for uncommitted changes**: Run `git -C <repo_path> status --porcelain`. If there are uncommitted changes, **skip this repo** and warn the user — `gt sync` requires a clean working tree.
3. **Check for Graphite initialization**: Look for a `.graphite_repo_config` file in the repo root. If missing, skip the repo and note it's not Graphite-initialized.
4. **Run `gt sync`** using the Graphite MCP tool with args `["sync", "--no-interactive", "--force"]` and `cwd` set to the repo path. The `--force` flag auto-deletes merged branches without prompting. `--no-interactive` prevents any interactive prompts.
5. **Check the result**:
   - **Success**: Log that the repo synced successfully.
   - **Conflict or error**: If `gt sync` fails or reports conflicts:
     a. Run `git -C <repo_path> status` and `git -C <repo_path> diff` to understand the conflict.
     b. **Stop processing other repos.**
     c. Present the conflict details to the user.
     d. Propose a specific resolution (e.g., "accept theirs for lockfiles, rebase and resolve for code changes, or abort and skip").
     e. Ask the user: "How would you prefer for me to resolve this?" with your proposed solution as the recommended option.
     f. After the user responds, execute their chosen resolution, then continue with the remaining repos.

### 3. Clean up stale worktree branches and orphaned worktrees

After `gt sync` succeeds for a repo, clean up leftover branches and worktrees. For every branch (excluding main/trunk), apply this decision tree:

1. **Has a worktree directory?** Check `git worktree list` and `.claude/worktrees/`.
   - **Yes, with uncommitted changes** (`git -C <worktree_path> status --porcelain` is non-empty): Commit them (`git -C <worktree_path> add -A && git -C <worktree_path> commit -m "wip: uncommitted worktree changes"`), push, and create a PR via `gh pr create`. Note in summary.
   - **Yes, clean**: Continue to step 2.
   - **Orphaned directory** (exists on disk but not in `git worktree list`): Remove the directory.

2. **Has commits ahead of main?** (`git -C <repo_path> log main..<branch> --oneline`)
   - **Yes**: Leave it alone — it has real work.
   - **No** (0 commits ahead): Delete the branch (`git update-ref -d refs/heads/<branch>`) and remove its worktree if one exists (`git worktree remove <path>`).

3. **Prune**: Run `git -C <repo_path> worktree prune` to finalize cleanup.

Track counts of: branches deleted, worktrees removed, and uncommitted work saved.

### 4. Summary

After all repos are processed, print a summary table:

```
Repo            | Status
----------------|------------------
brain-os        | Synced (2 branches deleted, 1 worktree pruned)
cove            | Synced (3 worktree branches cleaned)
dork            | Skipped (dirty working tree)
nugget          | Synced (1 branch deleted)
```

Include counts of branches deleted, worktree branches cleaned, and worktrees pruned if any were cleaned up during sync.

## Important

- Always use the Graphite MCP tool (`mcp__graphite__run_gt_cmd`) for `gt` commands, never raw `gt` via Bash.
- If a repo has worktrees (check `git -C <repo_path> worktree list`), note them in the output but still attempt sync — `gt sync` handles worktrees.
- Do NOT skip repos just because they have no open stacks — `gt sync` still pulls the latest trunk, which is valuable.
- Be concise in output. Don't over-explain each step, just show progress and results.
