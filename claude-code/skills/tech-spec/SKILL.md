---
name: tech-spec
description: Validated tech-spec workflow — turn a scope doc/PRD into a tech spec with zero unresolved known-unknowns and a PR-by-PR rollout plan. Use when the user asks to prepare/write/draft a tech spec, validate an MVP scope, de-risk a feature before building, surface known unknowns, or audit what's reusable vs net-new for a planned feature. Trigger phrases: "tech spec", "spec this out", "known unknowns", "what can we reuse", "validate this scope/PRD".
---

# Tech Spec — validated, code-grounded, PR-planned

Turn input docs (scope doc, PRD, prior specs, designs) into a tech spec whose every claim is verified. **Do not write the spec until Phase 3 is fully green.**

Ask up front if not provided: the feature, input doc links, target repos, the Linear project the spec belongs to, and which doc wins when inputs conflict.

## Phase 1 — Ingest & reconcile

- Read every input doc and the relevant designs (Paper/Figma) plus any local design-plan notes in the workspace.
- List every place the inputs contradict each other — scope docs, PRDs, prior specs, and designs routinely disagree after meetings. Ask which doc is source of truth if unclear (default: the most recently decided scope doc).
- Check Linear project documents for prior specs/plans; the new spec typically supersedes rather than edits them.

## Phase 2 — Reuse audit (verify, never inherit)

- **Pull latest develop in every target repo first** (`git status -sb`, `git pull --ff-only origin develop`). Auditing a stale checkout invalidates everything downstream.
- Fan out Explore agents over the repos to map what already exists vs. net-new. Then **re-verify the load-bearing claims first-hand** — read the exact files/lines yourself before asserting them.
- Treat every claim inherited from PM docs or prior specs as unverified until you've read the code (prior specs regularly cite classes that don't exist or miss ones that do).
- Look for prior art in adjacent orgs/configs — a capability "we'd have to build" is often already live for another customer.

## Phase 3 — Known-unknowns register

Split every open item into exactly three buckets:

- **(a) Product decisions** only the user/team can make → batch to the user in plain language, **one decision per question**, with a recommendation. Never bundle several questions into one bullet.
- **(b) Technical assumptions** → validate **empirically** (probe the API, decrypt the config with sops, run the script, sample real data), never by inference. Paste real output. If something can't be verified (needs a dashboard, prod creds, a vendor), label it "unverified — needs <X>" and say who can get it.
- **(c) Externals** → name an owner (use git blame/log to find who provisioned the thing) and state exactly what unblocks it.

As the user makes decisions, **record them into the scope doc immediately** (update the Linear doc; annotate resolved "Uncertain" items rather than deleting them, to preserve comment anchors). Flag anything blocker-shaped — missing creds, missing environments, missing config, compliance gaps — the moment you find it, prefixed 🔴.

Save verified findings and user decisions to project memory as you go — this work spans sessions.

## Phase 4 — Write the spec

Only once (a) is answered and (b) is verified. Save to Linear in the feature's project. Structure:

1. **One-page summary** + reuse-vs-net-new table (the digestible view — lead with it).
2. **Validated current state** — every claim carries a clickable GitHub link to develop with line anchors (`https://github.com/<org>/<repo>/blob/develop/<path>#L<n>`) so the reader can validate in one click. Include a "corrections to prior specs" subsection so stale claims don't propagate.
3. **Architecture** — data-model delta, end-to-end flow, and the extensibility constraints for known follow-up features.
4. **Decision log** — table of every decision with date.
5. **Known-unknowns register** — verified items collapsed; open externals as a table with owners.
6. **PR-by-PR rollout** — every PR independently testable with a stated test gate; dependencies explicit; nothing user-visible until a feature flag flips. Include a `## Progress` checklist (PRs + externals).
7. **Risks** — each with its mitigation and where the plan tests it.

## Throughout

- Verify before asserting: any factual claim about system state needs a tool call behind it.
- Estimates, timelines, and "already exists" claims from any source are hypotheses until checked.
- The deliverable of early phases is **questions and findings**, not the spec — don't start writing prose until the register is green.
