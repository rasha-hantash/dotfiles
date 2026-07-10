---
name: emr-data-exposure
description: Convention for adding per-org control over what EMR data a consumer sees — hiding, suppressing, or exposing a field/record across the voice read-back and/or the FE chart (basata-ai repos). Use when a ticket asks to filter, redact, omit, or reveal EMR data for a specific org (e.g. "don't read back RPC/RDM appointments", "hide the visit type", "surface the location address only on request", a new redaction/visibility setting).
---

# EMR Data Exposure (Basata)

**The question this answers:** "I need org X to see (or not see) some EMR field/record — where does that code go, and what shape does it take?"

**Grounded in:** ENG-726 (Grace: location address + provider name + per-org RPC/RDM exclusion + per-org visit-type suppression) and the `hiddenEmrDocumentTypeIds` precedent. Companion playbook: the `voice-agent-capability` skill (this skill is the deep-dive behind its "structural over prompt-level" gate). Team-facing narrative: **Skill: emr-data-exposure** in RAS.

Plain `git`/`gh` here — Graphite fails on basata-ai repos. Worktree before any edit.

## The invariants (enforce even without fetching anything)

1. **No generalized redaction engine — one narrowly-named setting per need.** Per-org data filtering is deliberately ad-hoc (YAGNI). Each need gets its own org-settings key with a specific noun; do NOT build a general `redactFields` / `hiddenFields` abstraction, and do NOT overload one key across unrelated concerns (documents ≠ appointment types ≠ visit type). Precedents, all separate keys: `hiddenEmrDocumentTypeIds`, `excludedAppointmentTypePrefixes`, `suppressVisitType`.

2. **Pick the layer by blast radius — "should the FE chart still see it?"**
   - **No, hide it everywhere → gateway layer** (`CachingEmrGateway`, e.g. `hiddenEmrDocumentTypeIds`). Affects ALL consumers (voice + FE chart + anything else on the gateway).
   - **Yes, only the voice agent shouldn't say it → voice display path** (the controller + the display DTO, e.g. `excludedAppointmentTypePrefixes` and `suppressVisitType` in `AgentsToolController.handleGetAppointment` / `IDisplayAppointment`). The FE chart uses the shared gateway path and is untouched.
   - Getting this wrong is the classic bug: filtering in the wrong layer either silently blanks the FE chart or leaks the field to voice anyway.

3. **Keep per-org logic OUT of the shared EMR client.** Multi-org clients (`EllkayClient`, the Athena family) stay org-agnostic — they return full data; consumers decide what to show. All per-org hiding converges _above_ the client (gateway or controller). Reason: the same client backs the FE chart, so client-level filtering would break it. If you're reaching for `organization` inside a client method to decide what to return, you're in the wrong file.

4. **Suppress at the data layer, never in the prompt.** To stop the agent from saying something, don't carry the field into the DTO/description the agent receives — then the agent never has the data and there is zero prompt-adherence risk. Do NOT rely on a prompt instruction like "don't mention X" (gpt-4.1 doesn't reliably obey, same reason a tool that must never fire gets _detached_, not warned against). Structural > prompt-level, always.

5. **Fail-safe, backwards-compatible defaults — adding the feature changes nothing until an org opts in.** The read contract must no-op when the key is unset:
   - list-shaped → coerce any `Collection` to `List<String>`, **return empty when unset** (`getExcludedAppointmentTypePrefixes`) → no filtering.
   - boolean-shaped → `Boolean.TRUE.equals(settings.get(KEY))` so **absent/false = the safe/legacy behavior** (`suppressVisitType`: absent = disclose).
   - Default direction = **don't hide** (opt-in to hide), so every org that hasn't configured it keeps its prior behavior. If you find yourself defaulting to hide-for-everyone, you're forcing every other org to opt back _out_ — invert it. Mirror the shape/naming of the nearest existing opt-in key.

6. **It's a data change, not a schema migration.** Org `settings` is a schemaless JSON blob in a single TEXT column (`OrganizationEntity.settings`, `@Convert(JsonMapConverter)`). A new key is org-configs JSON → synced into `organization.settings` (`generate_sql.py` / the settings PATCH). **No Flyway migration.** Locally the sync isn't automatic — set it directly: `update organization set settings = (settings::jsonb || '{"KEY": VALUE}'::jsonb)::text where id='<org>';` (the column is TEXT, so cast to jsonb, merge, cast back).

7. **Config-surface discipline is the review gate (claude[bot] blocks without it).** Every new org-settings key needs, in the **backend** PR body:
   - a **Config surface** section stating the **Reuse / Extend / New** decision + shape/naming rationale + the fail-safe read contract, and
   - a **linked companion `organization-configs` PR** that sets the exact key name / type / values.

   Missing either → blocked. Before merge, **cross-check** the org-config values field-by-field against what the code reads (name, JSON type, value) — a drift ships a silent no-op with green tests.

8. **Scope suppression to the exact display path — don't break flows that need the field.** Dropping a field from the read-back must not remove it where it's required. ENG-726: visit type is nulled in `IDisplayAppointment` (read-back) but kept in `IDisplayAppointmentSlot` (scheduling needs it to book) and `IAppointment` (FE chart). Suppress on the display DTO, not the domain type.

## Fast triage

| Ticket says…                                         | Layer                                                         | Key shape            | Default         |
| ---------------------------------------------------- | ------------------------------------------------------------- | -------------------- | --------------- |
| hide record/field from **everyone** (voice + chart)  | `CachingEmrGateway`                                           | list of ids/prefixes | empty = show    |
| agent must not **read back** a record type           | controller filter                                             | list of prefixes     | empty = include |
| agent must not **speak** a field, but chart keeps it | display DTO (omit field)                                      | boolean opt-in       | false = speak   |
| surface a field **only on request**                  | separate structured DTO field, kept OUT of `buildDescription` | n/a                  | —               |

House style while you're in there: no org/agent name in Java (no "Grace" — generic "the agent"/"a caller"); why-style comments at neighbor density; AssertJ `.describedAs()` on every new assertion.
