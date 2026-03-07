#!/usr/bin/env python3
"""brain-os-capture.py — Extract learnings from Claude Code sessions into brain-os.

Single capture script used by:
- cove kill: python3 brain-os-capture.py --session-id <id> --cwd <path>
- SessionEnd hook: receives session_id + transcript_path via stdin JSON

Uses claude -p (pipe mode) to extract insights and write them to brain-os
convention docs with inline footnote citations pointing to source transcripts.
"""

import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ── Config ──

BRAIN_OS_PATH = Path.home() / "workspace/personal/explorations/brain-os"
CLAUDE_PROJECTS_DIR = Path.home() / ".claude/projects"
LOCK_FILE = Path.home() / ".claude/brain-os-capture.lock"
LOG_FILE = Path.home() / ".claude/brain-os-capture.log"
MIN_TRANSCRIPT_BYTES = 1024

KEEP_TYPES = {"user", "assistant"}
MIN_TEXT_LENGTH = 20


def log(msg: str):
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except OSError:
        pass


# ── JSONL Discovery ──


def discover_transcript(session_id: str, cwd: str = "") -> Path | None:
    """Find the Claude Code transcript JSONL for a session.

    Discovery strategies:
    1. If cwd provided: encode cwd -> look in ~/.claude/projects/<encoded>/
    2. Worktree fallback: strip /.claude/worktrees/<name> and retry
    3. Glob all project dirs for <session_id>.jsonl
    """
    if cwd:
        encoded = cwd.replace("/", "-")
        candidate = CLAUDE_PROJECTS_DIR / encoded / f"{session_id}.jsonl"
        if candidate.is_file():
            return candidate

        # Worktree fallback: strip /.claude/worktrees/<name> from CWD
        stripped = re.sub(r"/\.claude/worktrees/[^/]+$", "", cwd)
        if stripped != cwd:
            encoded = stripped.replace("/", "-")
            candidate = CLAUDE_PROJECTS_DIR / encoded / f"{session_id}.jsonl"
            if candidate.is_file():
                return candidate

    # Glob across all project dirs
    if CLAUDE_PROJECTS_DIR.is_dir():
        for project_dir in CLAUDE_PROJECTS_DIR.iterdir():
            if not project_dir.is_dir():
                continue
            candidate = project_dir / f"{session_id}.jsonl"
            if candidate.is_file():
                return candidate

    return None


# ── JSONL Filtering ──


def extract_text(content) -> str:
    """Extract concatenated text from a message content field."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    return ""


def filter_transcript(jsonl_path: Path, max_entries: int = 500) -> list[dict]:
    """Filter JSONL to meaningful user/assistant entries, preserving line numbers."""
    meaningful = []
    with open(jsonl_path) as f:
        for line_num, line in enumerate(f, 1):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get("type") not in KEEP_TYPES:
                continue

            content = entry.get("message", {}).get("content", "")
            text = extract_text(content)

            if len(text) < MIN_TEXT_LENGTH:
                continue

            meaningful.append({
                "line_num": line_num,
                "role": entry.get("type", "unknown"),
                "text": text[:2000],
            })

    if len(meaningful) > max_entries:
        # Keep compact summaries + tail
        summaries = [
            e for e in meaningful
            if "compact summary" in e["text"].lower()
        ]
        tail = meaningful[-200:]
        meaningful = summaries + tail

    return meaningful


def format_transcript(entries: list[dict]) -> str:
    """Format filtered entries for the extraction prompt."""
    lines = []
    for entry in entries:
        lines.append(f"[line {entry['line_num']}] {entry['role']}: {entry['text']}")
    return "\n\n".join(lines)


# ── Existing Knowledge Scan ──


def scan_brain_os_structure() -> str:
    """Scan brain-os for doc headings and section headings."""
    if not BRAIN_OS_PATH.is_dir():
        return "(brain-os directory not found)"

    exclude = {".git", ".claude", "node_modules", "claude-learnings", "papers", "articles"}
    result = []

    for root, dirs, files in os.walk(BRAIN_OS_PATH):
        dirs[:] = [d for d in dirs if d not in exclude]

        for fname in sorted(files):
            if not fname.endswith(".md") or fname == "README.md":
                continue

            filepath = Path(root) / fname
            rel = filepath.relative_to(BRAIN_OS_PATH)

            try:
                content = filepath.read_text()
            except OSError:
                continue

            headings = []
            for line in content.split("\n"):
                if line.startswith("# "):
                    headings.append(line)
                elif line.startswith("## "):
                    headings.append(f"  {line}")

            if headings:
                result.append(f"`{rel}`:")
                for h in headings:
                    result.append(f"  {h}")

    return "\n".join(result) if result else "(empty brain)"


# ── Extraction Prompt ──

EXTRACTION_PROMPT = """You are a knowledge extraction agent for a personal engineering knowledge base called "brain-os".

Analyze the following Claude Code session transcript and extract insights worth preserving as reusable engineering knowledge.

## What counts as a learning

Signal comes in many sizes. All of these are equally valuable:

- **One-sentence gotchas**: "Airtable caps at 250k records per base regardless of plan"
- **Tool/library quirks**: "ureq v3 is fully sync — no async runtime needed"
- **Debugging patterns**: "When tmux pane-died fires, check if the process exit was 0 vs non-zero"
- **Architecture decisions**: "Use JSONL append-only logs for event sourcing — line numbers are stable citations"
- **Workflow improvements**: "Run `gt track -p main --force` after creating a worktree branch to fix Graphite parenting"

The quality bar is "is this true and useful to future-me?" — not "is this long enough?"

## What doesn't count

- Session-specific context (task details, file paths specific to one project)
- Things that are well-known or trivially documented
- Opinions or preferences without technical substance
- Information that overlaps with existing knowledge base content (see below)

## Existing knowledge base

These docs already exist. Do NOT extract insights that overlap with existing content. Route new insights to the most appropriate existing doc, or suggest a new doc if none fits.

{existing_knowledge}

## Output format

Return a JSON array. Each learning is an object with:
- "text": the insight to add to the convention doc (markdown formatted, concise)
- "target_file": which brain-os doc to add it to (e.g., "rust/rust-conventions.md") or "new: topic/filename.md" for new docs
- "section": existing section heading to add under (e.g., "## Error Handling") or "new: ## Section Name" for new sections
- "citation_line": the JSONL line number (from the [line N] prefix) that produced this insight
- "verbatim_quote": exact verbatim quote from that transcript entry that supports this insight (used for citation character offsets — must be findable via str.find() in the original text)
- "confidence": 0.5-1.0

Drop anything below 0.5 confidence. If no meaningful learnings exist, return: []

```json
[
  {{
    "text": "ureq v3 is fully sync — no tokio runtime needed. Good choice for CLI tools that need simple HTTP without async complexity.",
    "target_file": "rust/rust-conventions.md",
    "section": "## HTTP Clients",
    "citation_line": 247,
    "verbatim_quote": "ureq v3 removed all async support and is now purely synchronous",
    "confidence": 0.9
  }}
]
```

## Transcript

{transcript}"""


# ── Claude -p ──


def run_claude_p(prompt: str, timeout: int = 120) -> str | None:
    """Run claude -p and return stdout."""
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

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


def parse_json_array(output: str) -> list[dict]:
    """Parse JSON array from claude -p output, handling markdown fences."""
    text = output
    if "```json" in text:
        text = text.split("```json", 1)[1]
        text = text.split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1]
        text = text.split("```", 1)[0]

    text = text.strip()

    try:
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            log(f"Expected JSON array, got {type(parsed)}")
            return []
        return parsed
    except json.JSONDecodeError as e:
        log(f"Failed to parse JSON: {e}\nRaw: {text[:500]}")
        return []


# ── Convention Doc Writer ──


def next_footnote_number(content: str) -> int:
    """Find the next available footnote number in a document."""
    existing = re.findall(r"\[\^(\d+)\]", content)
    if not existing:
        return 1
    return max(int(n) for n in existing) + 1


def compute_citation(
    session_id: str, line_num: int, verbatim_quote: str, jsonl_path: Path
) -> str:
    """Build a citation string with optional character offsets."""
    prefix = session_id[:8]

    char_range = ""
    try:
        with open(jsonl_path) as f:
            for i, line in enumerate(f, 1):
                if i == line_num:
                    entry = json.loads(line)
                    content = entry.get("message", {}).get("content", "")
                    full_text = extract_text(content)
                    pos = full_text.find(verbatim_quote)
                    if pos >= 0:
                        char_range = f":{pos}-{pos + len(verbatim_quote)}"
                    break
    except (OSError, json.JSONDecodeError):
        pass

    return f"session:{prefix}:{line_num}{char_range}"


def write_learning_to_doc(
    learning: dict, session_id: str, jsonl_path: Path
) -> str | None:
    """Write a learning to its target brain-os convention doc. Returns relative path or None."""
    target = learning.get("target_file", "")
    section = learning.get("section", "")
    text = learning.get("text", "")
    line_num = learning.get("citation_line", 0)
    quote = learning.get("verbatim_quote", "")

    if not target or not text:
        return None

    # Handle "new: topic/filename.md"
    is_new_file = target.startswith("new: ")
    if is_new_file:
        target = target[5:]

    filepath = BRAIN_OS_PATH / target

    # Handle "new: ## Section Name"
    is_new_section = section.startswith("new: ")
    if is_new_section:
        section = section[5:]

    filepath.parent.mkdir(parents=True, exist_ok=True)

    if filepath.is_file():
        content = filepath.read_text()
    elif is_new_file:
        doc_title = (
            target.replace("/", " — ").replace(".md", "").replace("-", " ").title()
        )
        content = f"# {doc_title}\n"
    else:
        log(f"Target file not found and not marked as new: {target}")
        return None

    # Compute footnote number and citation
    fn_num = next_footnote_number(content)
    citation = compute_citation(session_id, line_num, quote, jsonl_path)

    description = quote[:80] + ("..." if len(quote) > 80 else "")
    footnote_def = f'[^{fn_num}]: {citation} "{description}"'

    # Add footnote reference to the learning text
    learning_text = f"{text}[^{fn_num}]"

    # Insert into document
    if section and not is_new_section:
        # Find section and append before the next section
        section_pattern = re.escape(section)
        match = re.search(f"^{section_pattern}$", content, re.MULTILINE)
        if match:
            next_section = re.search(r"^## ", content[match.end() :], re.MULTILINE)
            if next_section:
                insert_pos = match.end() + next_section.start()
            else:
                insert_pos = len(content)
            content = (
                content[:insert_pos].rstrip()
                + f"\n\n{learning_text}\n\n"
                + content[insert_pos:]
            )
        else:
            # Section not found — add as new section at end
            content = content.rstrip() + f"\n\n{section}\n\n{learning_text}\n"
    elif is_new_section:
        content = content.rstrip() + f"\n\n{section}\n\n{learning_text}\n"
    else:
        content = content.rstrip() + f"\n\n{learning_text}\n"

    # Add footnote definition at the end
    content = content.rstrip() + f"\n\n{footnote_def}\n"

    filepath.write_text(content)
    return target


# ── Git Operations ──


def git_commit_and_submit(modified_files: list[str], session_short: str):
    """Stage, commit, and submit changes via Graphite."""
    try:
        for f in modified_files:
            subprocess.run(
                ["git", "add", str(BRAIN_OS_PATH / f)],
                cwd=str(BRAIN_OS_PATH),
                capture_output=True,
                timeout=10,
            )

        msg = f"knowledge: auto-capture from session {session_short}"
        result = subprocess.run(
            ["gt", "create", "-m", msg],
            cwd=str(BRAIN_OS_PATH),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            log(f"gt create failed: {result.stderr[:500]}")
            return

        result = subprocess.run(
            ["gt", "submit", "--no-interactive", "--publish"],
            cwd=str(BRAIN_OS_PATH),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            log(f"gt submit failed: {result.stderr[:500]}")
            return

        log(f"Submitted learnings PR for session {session_short}")
        for line in result.stdout.split("\n"):
            if "graphite.com" in line or "github.com" in line:
                print(f"  PR: {line.strip()}")

    except subprocess.TimeoutExpired as e:
        log(f"Git command timed out: {e}")
    except FileNotFoundError as e:
        log(f"Command not found: {e}")


# ── Main ──


def main():
    parser = argparse.ArgumentParser(
        description="Extract learnings from Claude Code sessions"
    )
    parser.add_argument("--session-id", help="Claude session UUID (from cove)")
    parser.add_argument("--cwd", help="Session working directory (from cove)")
    args = parser.parse_args()

    session_id = args.session_id or ""
    transcript_path = None

    if not session_id:
        # SessionEnd hook: read from stdin
        try:
            data = json.load(sys.stdin)
            session_id = data.get("session_id", "")
            tp = data.get("transcript_path", "")
            if tp and os.path.isfile(tp):
                transcript_path = Path(tp)
        except (json.JSONDecodeError, EOFError):
            log("No valid JSON on stdin and no --session-id")
            sys.exit(0)

    if not session_id:
        log("No session_id available")
        sys.exit(0)

    session_short = session_id[:8]

    # Check double-capture marker
    marker = Path(f"/tmp/cove-captured-{session_id}")
    if marker.exists():
        marker.unlink(missing_ok=True)
        log(f"Marker found — cove already captured session {session_short}")
        sys.exit(0)

    # Detach from tmux process group (survive tmux kill-session)
    try:
        os.setsid()
    except OSError:
        pass

    log(f"--- Capture for session {session_short} ---")

    # Discover transcript
    if not transcript_path:
        transcript_path = discover_transcript(session_id, args.cwd or "")

    if not transcript_path or not transcript_path.is_file():
        log(f"Transcript not found for session {session_short}")
        sys.exit(0)

    if transcript_path.stat().st_size < MIN_TRANSCRIPT_BYTES:
        log(f"Transcript too small ({transcript_path.stat().st_size} bytes)")
        sys.exit(0)

    # Acquire lock to prevent concurrent git conflicts
    try:
        lock_fd = open(LOCK_FILE, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, BlockingIOError):
        log("Another capture is running, skipping")
        sys.exit(0)

    try:
        entries = filter_transcript(transcript_path)
        if not entries:
            log("No meaningful entries in transcript")
            sys.exit(0)

        log(f"Filtered to {len(entries)} entries")

        transcript_text = format_transcript(entries)
        existing_knowledge = scan_brain_os_structure()

        prompt = EXTRACTION_PROMPT.format(
            existing_knowledge=existing_knowledge,
            transcript=transcript_text,
        )

        print(f"Analyzing session {session_short} for learnings...")
        output = run_claude_p(prompt)
        if not output:
            print("  No learnings extracted.")
            sys.exit(0)

        learnings = parse_json_array(output)
        if not learnings:
            print("  No learnings detected.")
            sys.exit(0)

        learnings = [l for l in learnings if l.get("confidence", 0) >= 0.5]
        if not learnings:
            print("  No learnings passed confidence threshold.")
            sys.exit(0)

        print(f"Found {len(learnings)} learning(s):")
        modified_files = []
        for learning in learnings:
            target = write_learning_to_doc(learning, session_id, transcript_path)
            if target:
                modified_files.append(target)
                preview = learning.get("text", "")[:60]
                print(f"  - {preview}... -> {target}")

        if modified_files:
            git_commit_and_submit(list(set(modified_files)), session_short)
        else:
            print("  No files modified.")

    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
            LOCK_FILE.unlink(missing_ok=True)
        except OSError:
            pass

    sys.exit(0)


if __name__ == "__main__":
    main()
