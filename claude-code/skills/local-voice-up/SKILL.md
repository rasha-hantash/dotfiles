---
name: local-voice-up
description: Bring up the Basata local voice-agent E2E stack (docker bundle + signing proxy + ngrok + VAPI squad replication) so a real phone call reaches the local backend. Use when testing voice-agent changes locally, when the user says "local E2E", "test this with a call", or mentions ngrok/signing-proxy/replicate-vapi-squad.
---

# Local Voice E2E Bring-Up (Basata)

Call path: `caller → VAPI squad (personal org) → ngrok → signing-proxy :9000 → basata-backend :3001 → emr-gateway :3004 → EMR sandbox`. Source of truth: `~/workspace/basata-ai/ellkay-audit/LOCAL-E2E.md` — read it if any step here disagrees.

## Phase 1 — stack + proxy + tunnel (per-machine variance lives here)

```bash
BUNDLE=~/workspace/basata-ai/basata-devops/out/$USER   # generate with dw.py if missing
cd "$BUNDLE" && docker compose up -d                    # backend :3001, emr-gateway :3004
# Port collisions (usually :5432 from another project's *-db container): stop the squatter, retry.

WEBHOOKS_SHARED_SECRET=$(grep WEBHOOKS_SHARED_SECRET "$BUNDLE/.env" | cut -d= -f2) \
  python3 ~/workspace/basata-ai/ellkay-audit/signing-proxy.py &   # HMAC-signs for /api/agents/tools/**

ngrok http 9000 --log=stdout &                          # free-tier URL changes every restart
curl -s localhost:4040/api/tunnels | python3 -c "import sys,json;print(json.load(sys.stdin)['tunnels'][0]['public_url'])" > /tmp/ngrok_url.txt
```

## Phase 2 — replicate the squad into the personal VAPI org

```bash
VAPI_PRIVATE_KEY=<personal-org key> ORG_UUID=<org uuid> \
  python3 ~/workspace/basata-ai/ellkay-audit/replicate-vapi-squad.py
# NGROK_URL auto-read from /tmp/ngrok_url.txt. Idempotent. Prints the number to call.
```

⚠️ **Worktree trap:** replicate resolves org-configs by walking up from ITS OWN location → it reads the MAIN checkout, never a worktree. If the config under test lives in a worktree, verify what the script will read before running (or point ORG_CONFIGS_DIR at the worktree).

Verify: place a real call, exercise happy path + one refusal path, record the VAPI call IDs in the ticket.

## Teardown

```bash
python3 ~/workspace/basata-ai/ellkay-audit/replicate-vapi-squad.py teardown
pkill -f signing-proxy.py; pkill -f "ngrok http"
cd "$BUNDLE" && docker compose down
```

Notes: personal VAPI orgs cap at 10 phone numbers (script reuses the existing one). EMR targeting comes from the selected org's config `@type` — no env flag (CS → EllkayClient). For api.vapi.ai API calls use `~/.claude/scripts/vapi-curl` (Cloudflare needs the curl User-Agent).
