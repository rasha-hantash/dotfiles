#!/bin/bash
# run-daily.sh — invoked by cron at 0 6 * * * on the VPS.
#
# Five stages bookend two Claude invocations:
#   1. op resolves secrets at runtime (no plaintext on disk)
#   2. dork fetch + slack inbox dump  → candidates.json, slack-inbox.json
#   3. claude SKILL.md         (Pass 1 — judgment) writes pr-body.md
#   4. claude validate-index.md (Pass 2 — mechanical) appends to pr-body.md
#   5. gt create + gt submit   (only if any files changed)
#
# Run-summary, audit JSONs, and Claude transcripts all land in
# ~/.local/share/learning-machine/YYYY-MM-DD/. 30-day TTL.
#
# REQUIRES:
#   - 1Password service account token at $LM_HOME/op-token (chmod 600)
#   - `op`, `claude`, `gt`, `python -m dork` all on PATH
#   - Claude permissions pre-configured (settings.json or via /add-sandbox)
#     so non-interactive runs don't hit permission prompts

set -euo pipefail

# ---- Config (override via environment) ----
: "${LM_HOME:=$HOME/.config/learning-machine}"
: "${LM_DATA:=$HOME/.local/share/learning-machine}"
: "${BRAIN_OS_REPO:=$HOME/workspace/brain-os}"
: "${OP_TOKEN_FILE:=$LM_HOME/op-token}"
: "${SLACK_CHANNEL_ID:=C0B3G7H9T2T}"    # #learning-machine-inbox; not a secret
: "${CLAUDE_TIMEOUT:=600}"               # 10 min — Pass 1 over ~50 items + Pass 2

TODAY=$(date +%Y-%m-%d)
OUT_DIR="$LM_DATA/$TODAY"
SUMMARY="$OUT_DIR/run-summary.md"
PR_BODY_FILE="$OUT_DIR/pr-body.md"

mkdir -p "$OUT_DIR"
exec > >(tee -a "$SUMMARY") 2>&1

echo "# Learning Machine run — $(date -Iseconds)"
echo

# ---- Stage 1: load op service account token ----
if [ ! -s "$OP_TOKEN_FILE" ]; then
    echo "ERROR: missing or empty 1Password token at $OP_TOKEN_FILE" >&2
    exit 1
fi
export OP_SERVICE_ACCOUNT_TOKEN
OP_SERVICE_ACCOUNT_TOKEN=$(cat "$OP_TOKEN_FILE")

# Export SLACK_CHANNEL_ID so subprocesses (op run, claude) inherit it
export SLACK_CHANNEL_ID

# ---- Stage 2: fetch ----
echo "## Stage 2 — fetch"

# dork: pulls arXiv + HF + alphaxiv + FreshRSS. Secrets injected by op for FreshRSS.
op run --env-file="$LM_HOME/secrets.env.template" -- \
    python -m dork fetch --since 24h --json > "$OUT_DIR/candidates.json"

# slack inbox: optional. If the module isn't installed yet, skip gracefully.
if op run --env-file="$LM_HOME/secrets.env.template" -- \
       python -m slack_inbox dump --channel "$SLACK_CHANNEL_ID" --since 24h --json \
       > "$OUT_DIR/slack-inbox.json" 2>/dev/null; then
    echo "- slack-inbox.json: $(wc -c < "$OUT_DIR/slack-inbox.json") bytes"
else
    echo "[]" > "$OUT_DIR/slack-inbox.json"
    echo "- slack-inbox.json: skipped (slack_inbox module missing or fetch failed); empty array written"
fi

if [ ! -s "$OUT_DIR/candidates.json" ]; then
    echo "ERROR: candidates.json is empty or missing — dork fetch failed" >&2
    exit 1
fi
ITEM_COUNT=$(python3 -c "import json,sys; print(len(json.load(open(sys.argv[1])))+len(json.load(open(sys.argv[2]))))" "$OUT_DIR/candidates.json" "$OUT_DIR/slack-inbox.json")
echo "- candidates.json: $(wc -c < "$OUT_DIR/candidates.json") bytes"
echo "- combined item count: $ITEM_COUNT"
echo

# Refresh the `latest` symlink so prompt files can use a stable path
ln -sfn "$OUT_DIR" "$LM_DATA/latest"

# Initialize pr-body.md so SKILL just appends if needed
: > "$PR_BODY_FILE"

# ---- Stage 3: SKILL Pass 1 (judgment) ----
echo "## Stage 3 — SKILL Pass 1"
cd "$BRAIN_OS_REPO"
timeout "$CLAUDE_TIMEOUT" claude -p "$(cat "$LM_HOME/SKILL.md")" \
    2>&1 | tee "$OUT_DIR/skill-output.log"
echo "- skill-output.log: $(wc -l < "$OUT_DIR/skill-output.log") lines"

if [ ! -s "$PR_BODY_FILE" ]; then
    echo "ERROR: SKILL did not write pr-body.md. Check skill-output.log." >&2
    exit 1
fi

if [ "$(cat "$PR_BODY_FILE")" = "(no candidates today)" ]; then
    echo "- No items to land. Skipping validator and PR."
    find "$LM_DATA" -mindepth 1 -maxdepth 1 -type d -mtime +30 -exec rm -rf {} + 2>/dev/null || true
    exit 0
fi
echo

# ---- Stage 4: Validator Pass 2 (mechanical) ----
echo "## Stage 4 — Validator Pass 2"
timeout "$CLAUDE_TIMEOUT" claude -p "$(cat "$LM_HOME/validate-index.md")" \
    2>&1 | tee "$OUT_DIR/validator-output.log"
echo "- validator-output.log: $(wc -l < "$OUT_DIR/validator-output.log") lines"
echo

# ---- Stage 5: gt create + gt submit (only if there are changes) ----
echo "## Stage 5 — git delivery"
if [ -z "$(git status --porcelain)" ]; then
    echo "- No file changes after both passes. Skipping PR."
    find "$LM_DATA" -mindepth 1 -maxdepth 1 -type d -mtime +30 -exec rm -rf {} + 2>/dev/null || true
    exit 0
fi

# Use the first line of pr-body.md as the commit subject, rest as body
COMMIT_SUBJECT=$(head -1 "$PR_BODY_FILE")
COMMIT_BODY=$(tail -n +2 "$PR_BODY_FILE")

git add -A
gt create --commit -m "$COMMIT_SUBJECT" -m "$COMMIT_BODY"
gt submit --no-interactive --publish
echo "- PR submitted."

# ---- Cleanup ----
find "$LM_DATA" -mindepth 1 -maxdepth 1 -type d -mtime +30 -exec rm -rf {} + 2>/dev/null || true
