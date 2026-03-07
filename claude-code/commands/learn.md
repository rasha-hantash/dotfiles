---
description: Capture learnings from the current session — extract insights, gotchas, and patterns into brain-os.
---

## Your Task

Launch the learnings-capturer agent to extract and save development insights from this session.

## Steps

1. **Launch the agent:** Use the Agent tool to spawn `~/.claude/agents/learnings-capturer.md` as a background agent with the following prompt:

   > Review the current session for non-obvious insights, gotchas, debugging techniques, and patterns worth preserving. Extract learnings and create a PR to brain-os. Session ID prefix: use `$CLAUDE_SESSION_ID` (first 8 chars) or "manual" if unavailable.

2. **Report back:** Once the agent is launched, confirm to the user that learnings capture is in progress. No need to wait for completion — the agent runs in the background.

## Important

- This is a manual trigger — use it when you notice something worth capturing mid-session.
- The agent handles deduplication, confidence scoring, file creation, and PR submission automatically.
- Do NOT duplicate the agent's work — just launch it and let it run.
