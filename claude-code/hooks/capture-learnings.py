#!/usr/bin/env python3
"""SessionEnd hook -- extract learnings from session transcript.

Uses claude -p (pipe mode) to spawn a temporary Claude Code session
that analyzes the transcript and creates learning files in brain-os.
All failures log and exit 0 (never crash session exit).
"""

import fcntl
import json
import os
import subprocess
import sys
import time
from datetime import datetime

BRAIN_OS_ROOT = os.path.expanduser(
    "~/workspace/personal/explorations/brain-os"
)
LEARNINGS_DIR = os.path.join(BRAIN_OS_ROOT, "claude-learnings")
LOCK_FILE = os.path.expanduser("~/.claude/capture-learnings.lock")
LOG_FILE = os.path.expanduser("~/.claude/capture-learnings.log")
MIN_TRANSCRIPT_BYTES = 1024  # Skip trivial sessions


def log(msg: str):
    """Append a timestamped message to the log file."""
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except OSError:
        pass


def read_transcript(path: str, max_estimated_tokens: int = 500_000) -> str:
    """Read transcript JSONL, truncating if too large.

    If estimated tokens exceed max, extract compaction summaries
    and last 50 messages.
    """
    try:
        with open(path) as f:
            lines = f.readlines()
    except OSError as e:
        log(f"Failed to read transcript: {e}")
        return ""

    # Estimate tokens: ~4 chars per token
    total_chars = sum(len(line) for line in lines)
    estimated_tokens = total_chars // 4

    if estimated_tokens <= max_estimated_tokens:
        return "".join(lines)

    log(f"Transcript too large ({estimated_tokens} est. tokens), extracting summaries + tail")

    # Extract compaction summaries and last 50 messages
    summaries = []
    tail_messages = lines[-50:]

    for line in lines:
        try:
            entry = json.loads(line)
            # Look for compaction summary messages
            if isinstance(entry, dict):
                msg = entry.get("message", {})
                content = msg.get("content", "")
                if isinstance(content, str) and "compact summary" in content.lower():
                    summaries.append(line)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and "compact summary" in str(block.get("text", "")).lower():
                            summaries.append(line)
                            break
        except (json.JSONDecodeError, AttributeError):
            continue

    result_lines = summaries + ["\n--- LAST 50 MESSAGES ---\n\n"] + tail_messages
    return "".join(result_lines)


def get_existing_session_learnings(session_short: str) -> list[str]:
    """Get titles/summaries of learnings already captured for this session.

    Returns a list of "title: what" strings for dedup in the assess step.
    """
    existing = []
    if not os.path.isdir(LEARNINGS_DIR):
        return existing
    for f in os.listdir(LEARNINGS_DIR):
        if session_short not in f or not f.endswith(".md"):
            continue
        filepath = os.path.join(LEARNINGS_DIR, f)
        try:
            with open(filepath) as fh:
                title = ""
                what = ""
                for line in fh:
                    line = line.strip()
                    if line.startswith("# ") and not title:
                        title = line[2:]
                    elif line.startswith("**What:**"):
                        what = line.replace("**What:**", "").strip()
                        break
                if title:
                    existing.append(f"- {title}: {what}" if what else f"- {title}")
        except OSError:
            continue
    return existing


def get_existing_knowledge_titles() -> str:
    """Scan brain-os for existing doc titles to help detect overlaps."""
    brain_os = os.path.dirname(LEARNINGS_DIR)  # brain-os root
    titles = []

    # Scan root and key subdirectories for markdown files
    scan_dirs = [brain_os]
    for subdir in ["claude", "python", "rust", "git", "unix", "interviews", "claude-learnings"]:
        path = os.path.join(brain_os, subdir)
        if os.path.isdir(path):
            scan_dirs.append(path)

    for d in scan_dirs:
        try:
            for f in os.listdir(d):
                if not f.endswith(".md"):
                    continue
                filepath = os.path.join(d, f)
                rel = os.path.relpath(filepath, brain_os)
                # Read first heading as title
                try:
                    with open(filepath, "r") as fh:
                        for line in fh:
                            line = line.strip()
                            if line.startswith("# "):
                                titles.append(f"- `{rel}`: {line[2:]}")
                                break
                        else:
                            titles.append(f"- `{rel}`")
                except Exception:
                    titles.append(f"- `{rel}`")
        except OSError:
            continue

    return "\n".join(titles) if titles else "(empty brain — no existing docs)"


# --- Step 1: Extract (generous, divergent — find all potential insights) ---

EXTRACT_PROMPT = """You are a learnings extraction agent. Analyze the following Claude Code session transcript and extract development insights worth preserving. Be generous — capture anything that might be useful. Scoring happens in a separate step.

## What counts as a learning
- Non-obvious gotchas and surprising behavior
- Debugging techniques that worked
- Architecture patterns worth codifying
- Tool/library quirks
- Workflow improvements

## What doesn't count
- Session-specific context (task details, file paths specific to one project)
- Things that are well-known / trivially documented
- Trivial facts or obvious behavior

## Output Format
Return a JSON array. Each learning is an object with:
- "title": concise title (used as filename slug)
- "what": the insight or gotcha
- "context": what was being done when discovered

If there are no meaningful learnings, return an empty array: []

Example:
```json
[
  {
    "title": "ureq v3 sync http client",
    "what": "ureq v3 is fully sync, no async runtime needed",
    "context": "Replacing claude -p subprocess with direct API call"
  }
]
```

## Transcript follows:

"""

# --- Step 2: Assess (analytical, convergent — score and compare) ---

ASSESS_PROMPT_TEMPLATE = """You are a learnings assessment agent. Score each candidate learning and determine where it belongs.

## Candidate learnings to assess
{candidates_json}

## Existing brain-os knowledge
These docs already exist. Use them to assess novelty and detect overlaps:
{existing_knowledge}

## Already captured this session
These learnings were already captured from an earlier run (e.g., at compaction time). Do NOT include any candidate that duplicates or substantially overlaps with these — only return genuinely new insights:
{already_captured}

## Confidence Rubric
Score each learning across three dimensions — novelty, reusability, placement clarity:
- 0.9-1.0: Clearly new (not in brain-os), universal pattern, obvious destination doc
- 0.7-0.8: Probably new, reusable across most projects, reasonable destination guess
- 0.5-0.6: Might overlap existing knowledge, somewhat generalizable, unsure where it belongs
- 0.3-0.4: Possibly already documented, narrow/project-specific, no clear destination

## Output Format
Return a JSON array with the same learnings, now enriched with assessment fields:
- "title": keep from input
- "what": keep from input
- "context": keep from input
- "confidence": number between 0.3 and 1.0
- "destination": which brain-os doc this belongs in (e.g., "rust/rust-conventions.md", "new doc: X")
- "similar_to": file path of existing brain-os doc this most overlaps with, or null if clearly new

Drop any learnings that score below 0.3 or that duplicate already-captured learnings.

Example:
```json
[
  {{
    "title": "ureq v3 sync http client",
    "what": "ureq v3 is fully sync, no async runtime needed",
    "context": "Replacing claude -p subprocess with direct API call",
    "confidence": 0.9,
    "destination": "rust/rust-conventions.md",
    "similar_to": null
  }}
]
```
"""


def _run_claude_p(prompt: str, timeout: int = 120) -> str | None:
    """Run claude -p and return stdout, or None on failure."""
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)  # Avoid nested session detection

    try:
        result = subprocess.run(
            ["claude", "-p", "--no-session-persistence"],
            input=prompt,
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        log(f"claude -p timed out after {timeout}s")
        return None
    except FileNotFoundError:
        log("claude command not found")
        return None

    if result.returncode != 0:
        log(f"claude -p failed (rc={result.returncode}): {result.stderr[:500]}")
        return None

    return result.stdout.strip()


def _parse_json_array(output: str) -> list[dict]:
    """Parse JSON array from claude -p output, handling markdown fences."""
    json_str = output
    if "```json" in json_str:
        json_str = json_str.split("```json", 1)[1]
        json_str = json_str.split("```", 1)[0]
    elif "```" in json_str:
        json_str = json_str.split("```", 1)[1]
        json_str = json_str.split("```", 1)[0]

    json_str = json_str.strip()

    try:
        parsed = json.loads(json_str)
        if not isinstance(parsed, list):
            log(f"Expected JSON array, got {type(parsed)}")
            return []
        return parsed
    except json.JSONDecodeError as e:
        log(f"Failed to parse JSON: {e}\nRaw: {json_str[:500]}")
        return []


def extract_learnings(transcript: str, session_short: str) -> list[dict]:
    """Step 1: Extract candidate learnings from transcript (generous, no scoring)."""
    prompt = EXTRACT_PROMPT + transcript

    log("Step 1: Extracting candidate learnings...")
    output = _run_claude_p(prompt)
    if not output:
        return []

    log(f"Step 1 output: {len(output)} chars")
    candidates = _parse_json_array(output)
    log(f"Step 1: Found {len(candidates)} candidates")
    return candidates


def assess_learnings(candidates: list[dict], already_captured: list[str]) -> list[dict]:
    """Step 2: Score candidates for confidence, destination, overlap, and dedup."""
    if not candidates:
        return []

    existing = get_existing_knowledge_titles()
    candidates_json = json.dumps(candidates, indent=2)
    captured_str = "\n".join(already_captured) if already_captured else "(none — first capture for this session)"
    prompt = ASSESS_PROMPT_TEMPLATE.format(
        candidates_json=candidates_json,
        existing_knowledge=existing,
        already_captured=captured_str,
    )

    log(f"Step 2: Assessing {len(candidates)} candidates (already captured: {len(already_captured)})...")
    output = _run_claude_p(prompt, timeout=60)
    if not output:
        log("Step 2 failed, falling back to unscored candidates")
        # Fallback: return candidates with default scores
        for c in candidates:
            c.setdefault("confidence", 0.5)
            c.setdefault("destination", "TBD")
            c.setdefault("similar_to", None)
        return candidates

    log(f"Step 2 output: {len(output)} chars")
    assessed = _parse_json_array(output)
    log(f"Step 2: {len(assessed)} learnings passed assessment")
    return assessed


def create_learning_files(
    learnings: list[dict], session_short: str, date_str: str
) -> list[str]:
    """Create learning markdown files. Returns list of created file paths."""
    os.makedirs(LEARNINGS_DIR, exist_ok=True)
    created = []

    for learning in learnings:
        title = learning.get("title", "untitled")
        slug = title.lower().replace(" ", "-").replace("_", "-")
        # Clean slug to valid filename chars
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        slug = slug.strip("-")[:60]

        filename = f"{date_str}-{session_short}-{slug}.md"
        filepath = os.path.join(LEARNINGS_DIR, filename)

        # Don't overwrite existing files
        if os.path.exists(filepath):
            log(f"File already exists, skipping: {filename}")
            continue

        confidence = learning.get("confidence", 0.5)
        what = learning.get("what", "")
        context = learning.get("context", "")
        destination = learning.get("destination", "TBD")
        similar_to = learning.get("similar_to")

        similar_line = f"\n**Similar to:** `{similar_to}`" if similar_to else ""

        content = f"""# {title}

**Date:** {date_str}
**Session:** {session_short}

## Learning: {title}

**Confidence:** {confidence}{similar_line}

**What:** {what}

**Context:** {context}

**Suggested destination:** `{destination}`

### Audit Trail

- **Status:** pending
- **Promoted to:** —
- **Promoted on:** —
"""
        try:
            with open(filepath, "w") as f:
                f.write(content)
            created.append(filepath)
            log(f"Created: {filename}")
        except OSError as e:
            log(f"Failed to write {filename}: {e}")

    return created


def git_commit_and_submit(created_files: list[str], session_short: str):
    """Stage, commit, and submit learning files via Graphite."""
    try:
        # Stage files
        for f in created_files:
            subprocess.run(
                ["git", "add", f],
                cwd=BRAIN_OS_ROOT,
                capture_output=True,
                timeout=10,
            )

        # Create branch and commit with gt
        msg = f"learnings: auto-capture from session {session_short}"
        result = subprocess.run(
            ["gt", "create", "-m", msg],
            cwd=BRAIN_OS_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            log(f"gt create failed: {result.stderr[:500]}")
            return

        # Submit
        result = subprocess.run(
            ["gt", "submit", "--no-interactive", "--publish"],
            cwd=BRAIN_OS_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            log(f"gt submit failed: {result.stderr[:500]}")
            return

        log(f"Successfully submitted learnings PR for session {session_short}")
        log(f"gt submit output: {result.stdout[:500]}")

    except subprocess.TimeoutExpired as e:
        log(f"Git/gt command timed out: {e}")
    except FileNotFoundError as e:
        log(f"Command not found: {e}")


def discover_transcript_path(session_id: str, cwd: str) -> str:
    """Find transcript JSONL from session_id and cwd.

    Transcripts live at ~/.claude/projects/<dash-joined-cwd>/<session-uuid>.jsonl.
    SessionEnd provides transcript_path directly, but PreCompact doesn't —
    this function discovers it.
    """
    projects_dir = os.path.expanduser("~/.claude/projects")
    if not os.path.isdir(projects_dir):
        return ""

    # Convert cwd to dash-joined project directory name
    # /Users/foo/workspace/bar -> -Users-foo-workspace-bar
    project_dir_name = cwd.replace("/", "-")
    if project_dir_name.startswith("-"):
        pass  # Already has leading dash from /Users/...
    else:
        project_dir_name = "-" + project_dir_name

    project_dir = os.path.join(projects_dir, project_dir_name)
    if not os.path.isdir(project_dir):
        log(f"Project dir not found: {project_dir}")
        return ""

    # Look for transcript with matching session_id
    candidate = os.path.join(project_dir, f"{session_id}.jsonl")
    if os.path.isfile(candidate):
        return candidate

    # Fallback: find most recently modified .jsonl in the project dir
    jsonl_files = []
    try:
        for f in os.listdir(project_dir):
            if f.endswith(".jsonl"):
                full = os.path.join(project_dir, f)
                jsonl_files.append((os.path.getmtime(full), full))
    except OSError:
        return ""

    if jsonl_files:
        jsonl_files.sort(reverse=True)
        latest = jsonl_files[0][1]
        log(f"Using most recent transcript: {latest}")
        return latest

    return ""


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        log("No valid JSON on stdin")
        sys.exit(0)

    # Detach from tmux session so we survive tmux kill-session.
    # The hook is async, so Claude Code doesn't wait for us.
    try:
        os.setsid()
    except OSError:
        pass  # Already session leader, fine

    transcript_path = data.get("transcript_path", "")
    session_id = data.get("session_id", "")
    cwd = data.get("cwd", os.getcwd())
    session_short = session_id[:8] if session_id else "unknown"
    trigger = "SessionEnd" if transcript_path else "PreCompact"

    log(f"--- {trigger} capture for session {session_short} ---")

    # Discover transcript path if not provided (PreCompact doesn't provide it)
    if not transcript_path or not os.path.isfile(transcript_path):
        if session_id:
            transcript_path = discover_transcript_path(session_id, cwd)
        if not transcript_path or not os.path.isfile(transcript_path):
            log(f"Transcript not found (tried: {transcript_path})")
            sys.exit(0)

    # Check transcript size
    try:
        size = os.path.getsize(transcript_path)
    except OSError:
        log("Could not stat transcript file")
        sys.exit(0)

    if size < MIN_TRANSCRIPT_BYTES:
        log(f"Transcript too small ({size} bytes), skipping")
        sys.exit(0)

    # Check what's already been captured for this session (for dedup in assess step)
    already_captured = get_existing_session_learnings(session_short)
    if already_captured:
        log(f"Found {len(already_captured)} already-captured learnings for this session")

    # Acquire lock to prevent concurrent git conflicts
    try:
        lock_fd = open(LOCK_FILE, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, BlockingIOError):
        log("Another capture process is running, skipping")
        sys.exit(0)

    try:
        transcript = read_transcript(transcript_path)
        if not transcript:
            log("Empty transcript after reading")
            sys.exit(0)

        candidates = extract_learnings(transcript, session_short)
        if not candidates:
            log("No learnings extracted")
            sys.exit(0)

        learnings = assess_learnings(candidates, already_captured)
        if not learnings:
            log("No learnings passed assessment")
            sys.exit(0)

        log(f"Extracted {len(candidates)} candidates, {len(learnings)} passed assessment")

        date_str = datetime.now().strftime("%Y-%m-%d")
        created = create_learning_files(learnings, session_short, date_str)

        if created:
            git_commit_and_submit(created, session_short)
        else:
            log("No files created (all duplicates?)")

    finally:
        # Release lock
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
            os.unlink(LOCK_FILE)
        except OSError:
            pass

    sys.exit(0)


if __name__ == "__main__":
    main()
