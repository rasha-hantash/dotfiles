---
name: voice-agent-capability
description: Playbook for building, extending, or fixing Basata voice-agent capabilities and EMR integrations (basata-ai repos). Use when a task touches VAPI agents, prompts/tools/squads in organization-configs, emr-gateway/EllkayClient, Hamming tests, or call analytics.
---

# Voice-Agent Capability Work (Basata)

**Source of truth:** Linear ENG doc "SOP: Building a Voice-Agent Capability End-to-End" — https://linear.app/basataai/document/sop-building-a-voice-agent-capability-end-to-end-agent-playbook-ed2808b8bb74. Fetch it via the Linear MCP for full detail; below are the invariants to enforce even without it.

One workflow, no modes: Phase 1 (scope/validate) and the completion audit always run; other phases apply per their conditions. Plain `git`/`gh` here — Graphite fails on basata-ai repos. Worktree before any edit.

## Non-negotiable gates

1. **Scope:** read the org's integration `@type` before believing the ticket's code-path framing (CS = Athena Practice brand but `EllkayIntegration` type → `EllkayClient`). Post decision-required questions (product prefs, data policy, practice semantics) on the ticket NOW for standup; don't build past one that changes the implementation.
2. **Validate empirically before building:** probe sandbox endpoints with a throwaway script. For writes, a 2xx is not verification — read the record back field-by-field.
3. **Config:** `vars.yml` gets BOTH staging and production tool IDs from day one (#795 incident). Gate: `python scripts/organization-configs.py validate` (venv).
4. **Structural over prompt-level:** filter data server-side, not in prompts; a tool that must never fire gets detached, not warned against (gpt-4.1 fires attached tools regardless).
5. **Local E2E:** ngrok → signing-proxy :9000 → backend :3001 (setup: `ellkay-audit/LOCAL-E2E.md`). ⚠️ Replicate/deploy scripts read the MAIN checkout, not your worktree — verify before every deploy. Record test-call VAPI IDs in the ticket.
6. **Hamming tests** live in organization-configs (`ml-config/agents/<agent>/tests.yml`), same PR as the config. The test workflow stays green on failures — read the step-summary heading.
7. **New caller intent → analytics category** (classifier label + prompt boundaries + categories.json + tasks.json + extraction prompts — pattern: org-configs#825).
8. **Completion audit before Done:** ACs verified on a running env (not the diff); side-effect surfaces grepped; deployed where the customer feels it; every decision-question has a recorded answer (deliberate non-action counts, unrecorded doesn't); descoped work has a ticket.
