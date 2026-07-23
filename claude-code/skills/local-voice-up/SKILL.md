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
# Host ports reading connection-refused right after `up` is usually a daemon-busy blip — verify with
# `docker port ${USER}-basata-backend` + in-container /actuator/health before assuming it's down.
```

**Backend OOM-loops (`docker ps -a` → `Exited (137)`, `inspect … OOMKilled=true`) → raise the engine RAM.**
The container sets no `-Xmx`, so the JVM balloons ~3–4 GiB during Flyway/Hibernate startup and, at the
default 8 GiB, the kernel OOM-kills it ~6 min into boot (log stalls after the `spring.jpa.open-in-view`
warning). This machine runs **OrbStack, NOT Docker Desktop** (`docker context show` → `orbstack`; editing
Docker Desktop's settings-store.json does nothing). Raise OrbStack's ceiling (a dynamic balloon — safe on
a 16 GiB host, only grows as needed) and restart the engine, then drop fax-gateway (dead weight for voice):

```bash
orb config set memory_mib 12288 && orb stop && orb start   # NB: `orb restart` is for Linux MACHINES, not the engine
docker info --format '{{.MemTotal}}'                        # confirm ~11.7 GiB (12 GiB minus VM overhead)
cd "$BUNDLE" && docker compose up -d --scale fax-gateway=0
```

**`:5432` squatter you can't stop** (another tenant's `*-db`, e.g. `athertonhealth-db-1` — do NOT kill it;
the auto-mode classifier will deny it anyway): the backend reaches Postgres over the internal network
(`postgres:5432`), so only the _host_ publish collides. Remap just your Postgres host port via a compose
override, and pass it on **every** `up` that touches Postgres — the backend `depends_on` it, so an
override-less `up basata-backend` recreates Postgres on 5432 and re-collides:

```bash
printf 'services:\n  postgres:\n    ports: !override\n      - "15432:5432"\n' > /tmp/pg-override.yml
docker compose -f docker-compose.yml -f /tmp/pg-override.yml up -d --scale fax-gateway=0
# for later single-service ups: docker compose -f docker-compose.yml -f /tmp/pg-override.yml up -d postgres basata-backend
```

```bash
# Sign with the CONTAINER's live secret, NOT the bundle .env — the .env value drifts from the running
# container (regenerated after boot) and causes "Invalid webhook signature". (brain-os voice/local-e2e.md)
# Re-run this whenever the backend container is recreated (compose up after down, override changes, etc.).
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
VAPI_PRIVATE_KEY=<personal-org key> ORG_UUID=<org uuid> AGENT_NAME=smart-voicemail \
  NGROK_URL=https://ngrok-local-rasha.ngrok.app \
  ORG_CONFIGS_DIR=<worktree>/organizations \
  python3 ~/workspace/basata-ai/ellkay-audit/replicate-vapi-squad.py
# Setting ORG_UUID + AGENT_NAME makes it fully non-interactive (no org-picker prompt); 571 already
# exists so no number prompt. Prints the number to call + the NEW squad id (every run mints a new squad).
```

With the **reserved** ngrok domain the URL never changes, so you run this **once** — re-run it only when the squad config itself changes (new tools/prompts), never just because you restarted the stack.

⚠️ **Worktree trap:** replicate resolves org-configs by walking up from ITS OWN location → it reads the MAIN checkout, never a worktree. **To test config under a worktree you MUST set `ORG_CONFIGS_DIR=<worktree>/organizations`** (note: it wants the `organizations` dir, not the repo root).

Note: `replicate-vapi-squad.py`'s `parse_vars_local` was fixed (2026-07-23) to read multiline-YAML tool
URLs — develop's formatter emits `local:\n    https://…` and the old same-line-only parser saw an empty
value and died with `no local url in vars.yml for cardiacSolutions…`. If that error resurfaces, the parser
regressed.

Verify: place a real call, exercise happy path + one refusal path, record the VAPI call IDs in the ticket.

## Phase 3 — auto-graded Hamming run (optional: `tests.yml` guardrails against local code)

Run `agents-tests-runner/run.sh` so **Hamming drives + grades** an agent's `tests.yml` against the local squad — instead of clicking the Hamming UI or dialing by hand. Full runbook + concrete CS values: RAS doc **"SOP: Local Hamming Test Run"**. Invariants:

- **`configs/local/app.yml` is NOT committed** — author it before the first run or you get `Unknown
environment 'local'`. Minimal working file (backend/emr point at localhost; hamming public URL + the
  dedicated local group; DB omitted — inbound doesn't need it):
  ```yaml
  basata:
    backend_url: "http://localhost:3001"
  hamming:
    base_url: "https://app.hamming.ai/api/rest" # public; deployed envs use an internal Tailscale host
    group_id: "<HAMMING_LOCAL_GROUP_ID from configs/.env>"
  emr_gateway:
    base_url: "http://localhost:3004"
  ```
- **The test must carry the phone number, twice over.** The runner dials `vapiPhoneNumberId` for
  `env=local` from the agent's `vapi/telephony.json.vars.yml`, **falling back to `_default` — a stale
  `44644177…` that 404s.** Add a `local:` key = the id of the number bound to your current squad
  (571 = `f6c56789-d721-47c5-88ba-a2372f1679ba`). AND each test's `simulation.hammingTestCase` needs
  `phoneNumbers: ["+15719328047"]`, or Hamming 400s `No phone numbers provided and the agent has no
linked inbound phone numbers`. Both edits go on the throwaway branch below.
- **Dedicated Hamming group only** — never a shared `basata-<env>` group. The runner resolves agents _by name within a group_, so an import into a shared group hijacks that env's real agent. Personal VAPI key = hard org boundary (can't touch dev0/staging).
- **Agent name is exact:** `<INITIALS> - <agent-dir>` (Grace = `CS - smart-voicemail`; dir is `smart-voicemail`, **not** `appt-mgmt`). Imported agents are Auto-Sync (`isEditable:false`) → you can't rename in Hamming; rename the **VAPI squad** (`PATCH /squad` with the `members` array sent back, or 400) and Auto-Sync pulls it. The group **list** endpoint lags the single-agent GET a cache cycle — verify the list before running.
- **Every replicate mints a NEW squad**, but the runner dials the phone number (571 → whatever squad is bound now), so a fresh replicate + re-run "just works" as long as the Hamming agent already exists in the group by name. For rapid iteration, dialing the number by hand is still cheapest.
- Renaming the squad to `CS - smart-voicemail` **breaks THIS script's teardown** (it matches the `"local E2E"` substring) — rename back before re-replicating, or patch the teardown matcher.
- `agents-tests-runner/configs/.env`: `HAMMING_API_KEY`, `HAMMING_LOCAL_GROUP_ID`, `VAPI_PRIVATE_KEY` (personal), `AZURE_BLOB_CONNECTION_STRING` = a **well-formed** dummy (`DefaultEndpointsProtocol=https;AccountName=placeholder;AccountKey=cGxhY2Vob2xkZXI=;EndpointSuffix=core.windows.net` — the blob client is built unconditionally at startup, so a bare placeholder crashes; fake-but-valid keeps startup alive), `BASATA_WEBHOOK_SECRET` blank.
- Personas: canonical `tests.yml` uses **"April Test"** — seed it into the local Ellkay sandbox first
  (`FIRST=April LAST=Test DOB=1982-12-24 SEX=F ellkay-audit/seed-patient.sh create` → id
  `79907B1D-…`; add `book earliest` for an appointment). Make a **throwaway org-configs branch** to trim
  `tests.yml` to bound billable calls (each case = one VAPI+Hamming call; watch the VAPI balance) and add
  the phone-number keys above, and **push it** (`-oc` shallow-clones the _remote_ ref).

```bash
cd ~/workspace/basata-ai/agents-tests-runner        # (or a worktree)
uv venv .venv --python 3.13 && uv pip install -r requirements.txt
./run.sh --env local -oc <throwaway-branch> --org-id <uuid> --agent smart-voicemail --https --sync
```

The runner creates the test cases + guardrails in Hamming via API, places inbound calls, and prints per-guardrail PASS/FAIL. **Hamming grades the VAPI transcript directly, so guardrail verification is independent of the backend** — a passing run does NOT prove a task landed in the app.

⚠️ **Inbound DOES download the recording now** (contradicts older notes). `VapiService.processCallRecording`
uploads the VAPI recording to **Azure Blob**; with the dummy `AZURE_BLOB_CONNECTION_STRING` it throws
`Signature did not match` → `phone_call.analysis_status = FAILED` → **call row created but NO task**. So the
call/transcript exist (and Hamming grades fine) but the local app shows no task without a REAL Azure blob
connection string. Verify tasks in DB, not by assuming: `psql -h 127.0.0.1 -p 15432 -U <DB_USER> -d local`
(the runner itself can't — it warns `Basata login failed` when `BASATA_APP_USERNAME/PASSWORD` are unset).

## Teardown

```bash
python3 ~/workspace/basata-ai/ellkay-audit/replicate-vapi-squad.py teardown   # deletes squad/assistants/tools; keeps the number (now unbound)
pkill -f signing-proxy.py; pkill -f "ngrok http"
cd "$BUNDLE" && docker compose down     # scoped to the bundle's compose project; other tenants' containers untouched
# OrbStack RAM stays raised (harmless, dynamic). Delete the throwaway org-configs branch (local + remote).
```

Notes: personal VAPI orgs cap at 10 phone numbers (script reuses the existing one). EMR targeting comes from the selected org's config `@type` — no env flag (CS → EllkayClient). For api.vapi.ai API calls use `~/.claude/scripts/vapi-curl` (Cloudflare needs the curl User-Agent); it defaults to the **production/team** VAPI org — the local squad + 571 live in your **personal** org, so query those with `VAPI_PRIVATE_KEY=<personal>` (from `agents-tests-runner/configs/.env`).
