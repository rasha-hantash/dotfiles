---
name: voice-agent-release
description: Release/deploy process for basata-ai repos (basata + organization-configs in lockstep). Use when cutting a release, deploying to staging/proofing/production, fixing on a release branch, or cherry-picking back to develop.
---

# Basata Release & Deploy

**Source of truth:** Linear ENG doc "SOP: Voice-Agent Release & Deploy" — https://linear.app/basataai/document/sop-voice-agent-release-and-deploy-organization-configs-basata-2efcadbeec58. Fetch via Linear MCP for full detail; invariants below.

Two repos ship in lockstep (`basata` images + `organization-configs`), same branch model: `develop` → staging (auto on push), `release/vX.Y.x` → proofing (manual), production = manual `deploy-production.yml` dispatch of a **GitHub Release tag** + org-configs version, allowlisted deployers only, never rebuilds.

## Non-negotiable rules

1. **Fixes during a release merge into `release/vX.Y.x` FIRST**, ship as a patch tag, then flow back to develop: automated in `basata` (`auto-cherry-pick.yml`), **manual in organization-configs** — open the `Cherry-pick:` PR immediately or the next release cut regresses production (#823→#824 lesson).
2. **Pre-cut checklist:** every org's `vars.yml` has staging AND prod tool IDs (#795); all prior `Cherry-pick:` PRs merged; `scripts/organization-configs.py validate` passes; Hamming smoke PASS on staging — judged by the **step-summary heading**, the workflow stays green on test failures.
3. **VAPI-side deploys** (`scripts/vapi/deploy_vapi_assistants.py <target>`) are branch-gated per env; scripts resolve the MAIN checkout, not worktrees.
4. **Manual VAPI-dashboard edits are drift** — fold any hotfix back into organization-configs immediately or the next scripted deploy overwrites it.
5. **Post-deploy:** real test call per changed org; BetterStack + webhook logs; Linear releases flipped Done; cherry-picks confirmed.
6. **Guardrail sync to Hamming is automated in CI — except transient agents.** `organization-configs`' `sync-monitoring.yml` pushes guardrail definitions to Hamming on merge to `develop` (→ staging) and on release published (→ prod), dispatching the runner's sync — **no manual run for normal agents** (`sync_monitoring.sh` / `workflow_dispatch` is only for a targeted re-sync). **Transient outbound agents** (no standing VAPI assistant, e.g. cost-share / PIV squad members) are the exception: they can't be linked by name, so the auto-sync fails `No Hamming agent found with name '<PREFIX> - <AGENT>'` and their calls orphan unevaluated. One-time bootstrap: create the Hamming agent with the matching `externalAgentId` (the VAPI id on the call) and ingest call logs with that `external_agent_id` (`HammingClient.create_call_log`) so calls attribute to it. After adding such an agent, treat a red / `[FAIL]`-containing sync-monitoring run as "not linked yet."
