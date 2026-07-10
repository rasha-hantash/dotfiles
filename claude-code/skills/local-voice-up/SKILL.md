---
name: local-voice-up
description: Bring up the Basata local voice-agent E2E stack (docker bundle + signing proxy + ngrok + VAPI squad replication) so a real phone call reaches the local backend, and optionally run auto-graded Hamming tests (agents-tests-runner) against the local squad. Use when testing voice-agent changes locally, when the user says "local E2E", "test this with a call", "run hamming locally", or mentions ngrok/signing-proxy/replicate-vapi-squad/agents-tests-runner.
---

# Local Voice E2E Bring-Up (Basata)

Call path: `caller → VAPI squad (personal org) → ngrok → signing-proxy :9000 → basata-backend :3001 → emr-gateway :3004 → EMR sandbox`. **Gotchas** (why steps fail): brain-os `voice/local-e2e.md` — read it if any step here surprises you.

## Phase 1 — stack + proxy + tunnel (per-machine variance lives here)

```bash
BUNDLE=~/workspace/basata-ai/basata-devops/out/$USER   # generate with dw.py if missing
cd "$BUNDLE" && docker compose up -d                    # backend :3001, emr-gateway :3004
# Port collisions (usually :5432 from another project's *-db container): stop the squatter, retry.
# Host ports reading connection-refused right after `up` is usually a daemon-busy blip — verify with
# `docker port ${USER}-basata-backend` + in-container /actuator/health before assuming it's down.

# Sign with the CONTAINER's live secret, NOT the bundle .env — the .env value drifts from the running
# container (regenerated after boot) and causes "Invalid webhook signature". (brain-os voice/local-e2e.md)
WEBHOOKS_SHARED_SECRET="$(docker exec ${USER}-basata-backend printenv WEBHOOKS_SHARED_SECRET)" \
  python3 ~/workspace/basata-ai/ellkay-audit/signing-proxy.py &   # HMAC-signs for /api/agents/tools/**

# PERMANENT reserved domain (ngrok paid) → stable URL, so Phase 2 replicate runs ONCE, not per restart.
pkill -f "ngrok http" 2>/dev/null; sleep 2              # only one agent may hold the domain (ERR_NGROK_334)
ngrok http --url=ngrok-local-rasha.ngrok.app 9000 &     # reserved domain → proxy :9000  (NOT :80)
echo "https://ngrok-local-rasha.ngrok.app" > /tmp/ngrok_url.txt
# Free-tier fallback (no reserved domain): `ngrok http 9000` → ephemeral URL, changes every restart,
# forcing a re-run of Phase 2 each time. Prefer the reserved domain.
```

## Phase 2 — replicate the squad into the personal VAPI org

```bash
VAPI_PRIVATE_KEY=<personal-org key> ORG_UUID=<org uuid> \
  python3 ~/workspace/basata-ai/ellkay-audit/replicate-vapi-squad.py
# NGROK_URL auto-read from /tmp/ngrok_url.txt. Idempotent. Prints the number to call.
```

With the **reserved** ngrok domain the URL never changes, so you run this **once** — re-run it only when the squad config itself changes (new tools/prompts), never just because you restarted the stack.

⚠️ **Worktree trap:** replicate resolves org-configs by walking up from ITS OWN location → it reads the MAIN checkout, never a worktree. If the config under test lives in a worktree, verify what the script will read before running (or point ORG_CONFIGS_DIR at the worktree).

Verify: place a real call, exercise happy path + one refusal path, record the VAPI call IDs in the ticket.

## Phase 3 — auto-graded Hamming run (optional: `tests.yml` guardrails against local code)

Run `agents-tests-runner/run.sh` so **Hamming drives + grades** an agent's `tests.yml` against the local squad — instead of clicking the Hamming UI or dialing by hand. Full runbook + concrete CS values: RAS doc **"SOP: Local Hamming Test Run"**. Invariants:

- **Dedicated Hamming group only** — never a shared `basata-<env>` group. The runner resolves agents _by name within a group_, so an import into a shared group hijacks that env's real agent. Personal VAPI key = hard org boundary (can't touch dev0/staging).
- **Agent name is exact:** `<INITIALS> - <agent-dir>` (Grace = `CS - smart-voicemail`; dir is `smart-voicemail`, **not** `appt-mgmt`). Imported agents are Auto-Sync (`isEditable:false`) → you can't rename in Hamming; rename the **VAPI squad** (`PATCH /squad` with the `members` array sent back, or 400) and Auto-Sync pulls it. The group **list** endpoint lags the single-agent GET a cache cycle — verify the list before running.
- **Every replicate mints a NEW squad** → the Hamming agent's `externalAgentId` goes stale + the name reverts → re-import + re-rename. High-touch for rapid iteration; for that just **dial the number**.
- Renaming the squad to `CS - smart-voicemail` **breaks THIS script's teardown** (it matches the `"local E2E"` substring) — rename back before re-replicating, or patch the teardown matcher.
- `agents-tests-runner/configs/.env`: `HAMMING_API_KEY`, `HAMMING_LOCAL_GROUP_ID`, `VAPI_PRIVATE_KEY` (personal), `AZURE_BLOB_CONNECTION_STRING` = a **well-formed** dummy (`DefaultEndpointsProtocol=https;AccountName=placeholder;AccountKey=cGxhY2Vob2xkZXI=;EndpointSuffix=core.windows.net` — the blob client is built unconditionally at startup, so a bare placeholder crashes; fake-but-valid is fine, inbound never downloads), `BASATA_WEBHOOK_SECRET` blank. `configs/local/app.yml` → `hamming.base_url: https://app.hamming.ai/api/rest` (public; deployed envs use an internal Tailscale host).
- Personas: canonical `tests.yml` uses staging **"April Test"** (absent in the local Ellkay sandbox) → make a **throwaway org-configs branch** swapping to the seeded sandbox patient, and **push it** (`-oc` shallow-clones the _remote_ ref). Trim `tests.yml` to bound billable calls (each case = one VAPI+Hamming call; watch the VAPI balance).

```bash
cd ~/workspace/basata-ai/agents-tests-runner        # (or a worktree)
uv venv .venv --python 3.13 && uv pip install -r requirements.txt
./run.sh --env local -oc <throwaway-branch> --org-id <uuid> --agent smart-voicemail --https --sync
```

The runner creates the test cases + guardrails in Hamming via API, places inbound calls, and prints per-guardrail PASS/FAIL. Inbound needs no DB/blob/webhook secret; those are outbound-only.

## Teardown

```bash
python3 ~/workspace/basata-ai/ellkay-audit/replicate-vapi-squad.py teardown
pkill -f signing-proxy.py; pkill -f "ngrok http"
cd "$BUNDLE" && docker compose down
```

Notes: personal VAPI orgs cap at 10 phone numbers (script reuses the existing one). EMR targeting comes from the selected org's config `@type` — no env flag (CS → EllkayClient). For api.vapi.ai API calls use `~/.claude/scripts/vapi-curl` (Cloudflare needs the curl User-Agent).
