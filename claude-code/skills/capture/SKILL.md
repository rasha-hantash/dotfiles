---
name: capture
description: Capture session learnings into brain-os convention docs with provenance citations. Use when you notice a non-obvious insight worth preserving.
---

Capture learnings from the current session into brain-os convention docs. You have full conversational context — use it to produce high-quality entries with inline footnote citations.

**IMPORTANT:** Do NOT call `claude -p`. You are doing this inline.

## Steps

1. **Identify insights** worth capturing from the current conversation. Look for:
   - Non-obvious gotchas and surprising behavior
   - Tool/library quirks
   - Debugging patterns that worked
   - Architecture decisions worth codifying
   - Workflow improvements

2. **Find your session JSONL** for citation line numbers:
   - Encode the CWD: replace `/` with `-`
   - Find the most recently modified `.jsonl` in `~/.claude/projects/<encoded-cwd>/`
   - If in a worktree, strip `/.claude/worktrees/<name>` from CWD and retry
   - Read near the tail to find the relevant entry and its line number

3. **Write to the appropriate brain-os convention doc** at `~/workspace/personal/explorations/brain-os/`:
   - Route to the most specific existing doc (e.g., `rust/rust-conventions.md`, `unix/xdg-conventions.md`)
   - If no doc fits, create a new one in the appropriate topic directory
   - Add the insight under the most relevant `## section`, or create a new section

4. **Add footnote citations** using per-doc append-only numbering:
   - Find `max(existing footnote numbers)` in the target doc, use `max + 1`
   - Add `[^N]` at the end of the insight text
   - Add definition at the bottom: `[^N]: session:<prefix>:<line> "<description>"`
   - `<prefix>` = first 8 chars of session UUID (from JSONL filename)
   - `<line>` = JSONL line number of the source entry
   - Character offsets are best-effort; `/doctor` can validate later

5. **Create a PR** via Graphite:

   ```bash
   cd ~/workspace/personal/explorations/brain-os
   git add <modified files>
   gt create -m "knowledge: <brief description>"
   gt submit --no-interactive --publish
   ```

6. **Report** what was captured and where, with the PR link.

## Quality bar

"Is this true and useful to future-me?" — a one-sentence gotcha is just as valuable as a multi-paragraph pattern. Don't pad entries for length.
