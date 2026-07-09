---
name: local-voice-up
description: Bring up the Basata local voice-agent E2E stack (docker bundle + signing proxy + ngrok + VAPI squad replication) so a real phone call reaches the local backend. Use when testing voice-agent changes locally, when the user says "local E2E", "test this with a call", or mentions ngrok/signing-proxy/replicate-vapi-squad.
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

## Teardown

```bash
python3 ~/workspace/basata-ai/ellkay-audit/replicate-vapi-squad.py teardown
pkill -f signing-proxy.py; pkill -f "ngrok http"
cd "$BUNDLE" && docker compose down
```

Notes: personal VAPI orgs cap at 10 phone numbers (script reuses the existing one). EMR targeting comes from the selected org's config `@type` — no env flag (CS → EllkayClient). For api.vapi.ai API calls use `~/.claude/scripts/vapi-curl` (Cloudflare needs the curl User-Agent).
