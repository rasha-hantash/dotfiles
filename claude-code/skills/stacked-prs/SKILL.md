---
name: stacked-prs
description: Break features into stacked, independently-reviewable PRs. Use when planning branches/PRs for any multi-part change, when a diff is growing past ~200 lines, or when the user asks how to split work. Applies in ALL repos — Graphite repos use gt; non-Graphite repos (e.g. basata-ai) use plain git/gh mechanics included here.
---

# Stacked PRs

Personal engineering standard (Rasha): every reviewable concern ships as its own PR, stacked so later work builds on earlier work without waiting for merges. Reference: https://graphite.com/blog/stacked-prs — this skill codifies the practice for repos with and without Graphite.

## Why (the one-paragraph version)

A reviewer can hold ~200 lines in their head. In a 500-line feature PR, a 2-line config omission is invisible; in a 40-line config-only PR, it IS the review. Stacks also unblock you: you keep building on diff 2 while diff 1 sits in review, and a revert/cherry-pick targets one concern instead of the whole feature.

## Slicing heuristics

Propose the stack structure BEFORE writing code and get confirmation. Slice by **reviewer concern**, not by file type:

1. **Data/config contracts first** — schemas, tool registries, env-var files, migrations. Small, high-blast-radius diffs a reviewer must eyeball line-by-line (e.g. per-env tool IDs: staging AND production).
2. **Core logic** — the implementation against those contracts.
3. **Wiring/integration** — routing, squad wiring, feature flags, glue.
4. **Tests + docs** — if they'd bloat an earlier diff. Tests for a diff's logic belong IN that diff; end-to-end/scenario tests can be their own.

A slice is right-sized when: it's independently revertable, its description is one sentence without "and", and CI passes on it alone. If a stack entry has no diff to show (e.g. "tests" turns out empty), that absence is a finding — say so.

Anti-patterns: slicing by file type ("all JSON in PR 1"), stacking unrelated features (separate stacks), a "misc fixes" diff (each fix is its own diff or belongs with its cause).

## Mechanics — Graphite repos (personal projects)

Per global CLAUDE.md: `gt create -m` per diff, `gt submit --no-interactive --publish` once per stack, `gt modify` to amend, `gt sync` after merges. Share the Graphite PR link. In worktrees, after the first `gt create`: `gt track -p main --force` (reparent past the worktree branch).

## Mechanics — plain git/gh repos (all basata-ai repos: NO Graphite, gt fails there)

Build the stack as branch-on-branch:

```bash
git checkout -b feat/x-1-contracts origin/develop   # diff 1
# ...commit...
git checkout -b feat/x-2-logic                      # diff 2, based on diff 1
# ...commit...
git checkout -b feat/x-3-wiring                     # diff 3
```

Open PRs with explicit bases — this is what makes GitHub render only each diff's own changes:

```bash
gh pr create --base develop        --head feat/x-1-contracts ...
gh pr create --base feat/x-1-contracts --head feat/x-2-logic ...
gh pr create --base feat/x-2-logic --head feat/x-3-wiring ...
```

**Maintaining the stack** — the key primitive is `--update-refs` (git ≥ 2.38): amend any lower diff, then from the top branch:

```bash
git rebase --update-refs feat/x-1-contracts   # moves every stacked branch in one rebase
git push --force-with-lease origin feat/x-1-contracts feat/x-2-logic feat/x-3-wiring
```

Set it once and forget: `git config --global rebase.updateRefs true`.

**When the bottom PR merges:**

- GitHub auto-retargets child PRs to the new base when the merged branch is deleted — verify it happened.
- If the repo **squash-merges** (check the merge commit), the child's history still contains the old commits; rebase them out explicitly:
  ```bash
  git rebase --onto origin/develop feat/x-1-contracts feat/x-2-logic --update-refs
  git push --force-with-lease ...
  ```
  Plain merge commits don't need this — a normal rebase onto develop suffices.

## Stack etiquette

- Every PR description opens with its position: `Stack 2/3 — depends on #NNN, followed by #MMM`.
- Never force-push a lower branch without immediately rebasing + pushing the ones above (reviewers see phantom diffs otherwise).
- One stack = one feature. Iterative fixes within a session amend the existing diff (`gt modify` / `git commit --amend` + update-refs), not new stack entries.
- Release-branch fix flow (basata): the stack targets `release/vX.Y.x`, and each merged diff gets its own `Cherry-pick:` PR back to develop — per-fix, not one bundle.
