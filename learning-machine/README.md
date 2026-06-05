# Learning Machine

Daily 6am cron pipeline that fetches candidate articles/papers from RSS, arXiv, HuggingFace, alphaxiv, and Slack, then triages them via two Claude passes (judgment + mechanical drift check) into a PR against the user's `brain-os` repo.

## Files

- `SKILL.md` — Pass 1 prompt (judgment). Reads user profile, classifies candidates, writes diffs.
- `validate-index.md` — Pass 2 prompt (mechanical). Catches orphan files and dead entries in `index.md`.
- `run-daily.sh` — cron wrapper. Orchestrates: secrets → fetch → SKILL → validator → `gt create` + `gt submit`.
- `secrets.env.template` — `op://` references for `op run --env-file=...`. Committed; contains no real secrets.

## Installation on the VPS

```sh
# 1. Clone or sync dotfiles to the VPS (the standard claude-vps-setup flow handles this).

# 2. Symlink this package to a stable path the cron wrapper expects.
mkdir -p ~/.config/learning-machine
ln -sf ~/workspace/dotfiles/learning-machine/SKILL.md ~/.config/learning-machine/SKILL.md
ln -sf ~/workspace/dotfiles/learning-machine/validate-index.md ~/.config/learning-machine/validate-index.md
ln -sf ~/workspace/dotfiles/learning-machine/run-daily.sh ~/.config/learning-machine/run-daily.sh
ln -sf ~/workspace/dotfiles/learning-machine/secrets.env.template ~/.config/learning-machine/secrets.env.template

# 3. Install the 1Password service account token (one-time).
#    Create the token at: https://my.1password.com/developer-tools/infrastructure-secrets
#    Scope it to the `learning-machine` vault only.
echo -n "<paste-token-here>" > ~/.config/learning-machine/op-token
chmod 600 ~/.config/learning-machine/op-token

# 4. Verify `op` CLI is installed and the token works.
OP_SERVICE_ACCOUNT_TOKEN=$(cat ~/.config/learning-machine/op-token) \
    op item list --vault learning-machine

# 5. Verify dork is installed and fetch-only mode works.
python -m dork fetch --since 24h --json | python3 -m json.tool | head -20

# 6. Install the cron entry.
( crontab -l 2>/dev/null; \
  echo "0 6 * * * /home/agent/.config/learning-machine/run-daily.sh >> /var/log/learning-machine.log 2>&1" \
) | crontab -

# 7. (Optional) Force a test run to verify the full pipeline works.
~/.config/learning-machine/run-daily.sh
```

## 1Password vault contents (one-time setup)

In the 1Password GUI, create a vault named `learning-machine` with three items:

| Item name  | Fields                                                       |
| ---------- | ------------------------------------------------------------ |
| `slack`    | `token` (xoxb-... bot token from the Slack app)              |
| `freshrss` | `user`, `password`, `url` (admin creds + http://localhost:8080 or tunnel URL) |
| `config`   | `slack_channel_id` (C0B3G7H9T2T for #learning-machine-inbox), `brain_os_repo` (path on VPS) |

Then create a service account token scoped to ONLY this vault. That token is the only secret that ever touches the VPS disk.

## How a typical day flows

1. **6:00:00** — cron fires `run-daily.sh`.
2. **6:00:01** — wrapper loads `OP_SERVICE_ACCOUNT_TOKEN` from `~/.config/learning-machine/op-token`.
3. **6:00:02-30** — `op run` resolves secrets at runtime and invokes `python -m dork fetch` and `python -m slack_inbox dump`. Output: `candidates.json` + `slack-inbox.json` in `~/.local/share/learning-machine/YYYY-MM-DD/`.
4. **6:00:30-6:05:00** — `claude -p "$(cat SKILL.md)"` (Pass 1): reads profile + JSONs + index, writes diffs to convention docs, appends to skipped log, updates index inline. Prints PR body to stdout.
5. **6:05:00-6:06:00** — `claude -p "$(cat validate-index.md)"` (Pass 2): scans for orphan files and dead entries in `index.md`. Adds/removes as needed. Prints any changes to stdout.
6. **6:06:00-6:06:30** — `gt create` + `gt submit --no-interactive --publish`. PR opens on GitHub.
7. **6:06:30** — old daily audit dirs (>30 days) pruned. Wrapper exits.

User wakes up, checks the Graphite PR link, accepts/rejects items, merges. The next day starts the loop again.

## Debugging

- **Why did this item get skipped?** Look at `~/.local/share/learning-machine/YYYY-MM-DD/skill-output.log` for SKILL's reasoning, or grep `brain-os/learning-machine/skipped/YYYY-MM.md` for the public reason.
- **Why is candidates.json empty?** Run `python -m dork fetch --since 24h --json` directly. dork may have failed silently — check stderr.
- **Why didn't a PR open?** Check `git status --porcelain` in `$BRAIN_OS_REPO`. If empty, no changes were made; if non-empty, gt likely errored — see `run-summary.md` for the exact failure.
- **Pipeline timing out?** Increase `CLAUDE_TIMEOUT` in `run-daily.sh` (default 600s). Pass 1 over 50+ items can take 4-6 minutes.

## Non-goals

- No real-time triage. This is daily-batch only.
- No automatic profile tuning. Profile edits are manual; the skipped log is the feedback signal.
- No sandboxing. Trust model: VPS is single-tenant, agent runs as the user.
