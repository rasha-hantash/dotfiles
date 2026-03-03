#!/usr/bin/env python3
"""PreCompact hook -- preserve critical context before compaction.

Captures git state, active tasks, team members, and previous session
learnings, then injects them as systemMessage so Claude retains
awareness after compaction. Includes session ID for learnings chaining.
"""

import glob
import json
import os
import subprocess
import sys
import time


CHAIN_FILE = os.path.expanduser("~/.claude/session-learnings-chain.md")
CHAIN_MAX_AGE_SECONDS = 24 * 60 * 60  # 24 hours


def run_git(args, cwd=None):
    """Run a git command and return stdout, or empty string on failure."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def get_git_context(cwd):
    """Gather current git state."""
    lines = []
    branch = run_git(["branch", "--show-current"], cwd=cwd)
    if branch:
        lines.append(f"Current branch: {branch}")

    status = run_git(["status", "--porcelain"], cwd=cwd)
    if status:
        changed = len([l for l in status.splitlines() if l.strip()])
        lines.append(f"Uncommitted changes: {changed} file(s)")
    else:
        lines.append("Working tree: clean")

    log = run_git(
        ["log", "--oneline", "-5", "--no-decorate"],
        cwd=cwd,
    )
    if log:
        lines.append(f"Recent commits:\n{log}")

    return lines


def get_task_context():
    """Gather active tasks from all task lists."""
    lines = []
    tasks_root = os.path.expanduser("~/.claude/tasks")
    if not os.path.isdir(tasks_root):
        return lines

    for task_file in glob.glob(os.path.join(tasks_root, "**", "*.json"), recursive=True):
        try:
            with open(task_file) as f:
                task = json.load(f)
            status = task.get("status", "")
            if status in ("pending", "in_progress"):
                subject = task.get("subject", "untitled")
                owner = task.get("owner", "unassigned")
                task_id = task.get("id", os.path.basename(task_file))
                lines.append(f"  [{status}] #{task_id}: {subject} (owner: {owner})")
        except (json.JSONDecodeError, OSError):
            continue

    return lines


def get_team_context():
    """Gather active team members."""
    lines = []
    teams_root = os.path.expanduser("~/.claude/teams")
    if not os.path.isdir(teams_root):
        return lines

    for team_dir in glob.glob(os.path.join(teams_root, "*")):
        config_path = os.path.join(team_dir, "config.json")
        if not os.path.isfile(config_path):
            continue
        try:
            with open(config_path) as f:
                config = json.load(f)
            team_name = os.path.basename(team_dir)
            members = config.get("members", [])
            if members:
                member_names = [m.get("name", "unknown") for m in members]
                lines.append(f"  Team '{team_name}': {', '.join(member_names)}")
        except (json.JSONDecodeError, OSError):
            continue

    return lines


def get_session_learnings():
    """Read previous session learnings from chain file.

    Returns the content string, or empty string if file does not exist
    or is older than 24 hours.
    """
    if not os.path.isfile(CHAIN_FILE):
        return ""

    try:
        mtime = os.path.getmtime(CHAIN_FILE)
        if time.time() - mtime > CHAIN_MAX_AGE_SECONDS:
            return ""

        with open(CHAIN_FILE) as f:
            content = f.read().strip()
        return content
    except OSError:
        return ""


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        data = {}

    cwd = data.get("cwd", os.getcwd())
    session_id = data.get("session_id", "")
    session_short = session_id[:8] if session_id else "unknown"

    sections = []

    git_lines = get_git_context(cwd)
    if git_lines:
        sections.append("## Git State\n" + "\n".join(git_lines))

    task_lines = get_task_context()
    if task_lines:
        sections.append("## Active Tasks\n" + "\n".join(task_lines))

    team_lines = get_team_context()
    if team_lines:
        sections.append("## Active Teams\n" + "\n".join(team_lines))

    previous_learnings = get_session_learnings()
    if previous_learnings:
        sections.append(
            "## Previous Learnings This Session\n"
            "The following learnings were captured earlier in this session. "
            "Build on these -- do not duplicate them.\n\n"
            + previous_learnings
        )

    sections.append(
        "## ACTION REQUIRED: Capture Session Learnings\n"
        "Context is about to be compressed. This is a mandatory capture trigger.\n\n"
        f"**Session ID prefix:** `{session_short}`\n"
        f"**Branch namespace:** `learnings/{session_short}/`\n\n"
        "Before capturing, check for existing learnings PRs from this session:\n"
        f'  `gh pr list --search "learnings/{session_short}" --state open`\n\n'
        "If an existing PR covers the same topic area, amend it (gt checkout -> "
        "append -> gt modify -> gt submit). If it is a different topic, create a new PR.\n\n"
        "If this session produced any non-obvious insights, gotchas, debugging techniques, "
        "or patterns worth remembering:\n"
        "1. Launch a background agent (isolation: worktree) targeting the brain-os repo\n"
        f"2. Create a learnings file: claude-learnings/YYYY-MM-DD-{session_short}-<slug>.md\n"
        f"3. Branch via gt create under learnings/{session_short}/ namespace\n"
        "4. Submit via gt submit --no-interactive --publish\n"
        "5. Update the chain file (~/.claude/session-learnings-chain.md) with a summary "
        "of all learnings captured so far this session\n\n"
        "If nothing worth capturing, skip -- but actively decide, do not just forget."
    )

    context = "# Pre-Compaction Snapshot\n\n" + "\n\n".join(sections)
    result = {
        "systemMessage": context,
    }
    json.dump(result, sys.stdout)

    sys.exit(0)


if __name__ == "__main__":
    main()
