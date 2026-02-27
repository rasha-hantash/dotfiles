#!/usr/bin/env python3
"""PreCompact hook — preserve critical context before compaction.

Captures git state, active tasks, and team members, then injects
them as additionalContext so Claude retains awareness after compaction.
"""

import glob
import json
import os
import subprocess
import sys


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

    # Uncommitted changes count
    status = run_git(["status", "--porcelain"], cwd=cwd)
    if status:
        changed = len([l for l in status.splitlines() if l.strip()])
        lines.append(f"Uncommitted changes: {changed} file(s)")
    else:
        lines.append("Working tree: clean")

    # Last 5 commits
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


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        data = {}

    cwd = data.get("cwd", os.getcwd())
    sections = []

    # Git context
    git_lines = get_git_context(cwd)
    if git_lines:
        sections.append("## Git State\n" + "\n".join(git_lines))

    # Task context
    task_lines = get_task_context()
    if task_lines:
        sections.append("## Active Tasks\n" + "\n".join(task_lines))

    # Team context
    team_lines = get_team_context()
    if team_lines:
        sections.append("## Active Teams\n" + "\n".join(team_lines))

    if sections:
        context = "# Pre-Compaction Snapshot\n\n" + "\n\n".join(sections)
        result = {
            "systemMessage": context,
        }
        json.dump(result, sys.stdout)

    sys.exit(0)


if __name__ == "__main__":
    main()
