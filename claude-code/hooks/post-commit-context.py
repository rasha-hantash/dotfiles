#!/usr/bin/env python3
"""PostToolUse hook: captures task context as a sidecar JSON file on git commit.

Reads the PostToolUse event from stdin, checks if the Bash command was a git commit,
and if so, snapshots all active task data into ~/.claude/commit-context/{project-id}/{sha}.json.

Also auto-installs a git post-rewrite hook so sidecar files survive rebase/amend.
"""

import fcntl
import hashlib
import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

COMMIT_CONTEXT_DIR = Path.home() / ".claude" / "commit-context"
TASKS_DIR = Path.home() / ".claude" / "tasks"
POST_REWRITE_MARKER = "# managed-by: post-commit-context"
POST_REWRITE_SCRIPT = Path.home() / ".claude" / "hooks" / "post-rewrite-context.py"


def main():
    try:
        event = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    # Only act on Bash tool calls that contain "git commit"
    tool_input = event.get("tool_input", {})
    command = tool_input.get("command", "")
    if "git commit" not in command:
        sys.exit(0)

    # Get the commit SHA
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except subprocess.CalledProcessError:
        sys.exit(0)

    # Get the project root (resolves through worktrees to the main worktree)
    try:
        toplevel = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except subprocess.CalledProcessError:
        sys.exit(0)

    project_id = hashlib.sha256(toplevel.encode()).hexdigest()[:12]

    # Collect task data from all active teams
    task_references = []
    task_dumps = []
    if TASKS_DIR.is_dir():
        for team_dir in TASKS_DIR.iterdir():
            if not team_dir.is_dir():
                continue
            team_name = team_dir.name
            for task_file in team_dir.glob("*.json"):
                try:
                    data = json.loads(task_file.read_text())
                    task_id = task_file.stem
                    task_references.append({"task_id": task_id, "team_name": team_name})
                    task_dumps.append({
                        "task_id": task_id,
                        "team_name": team_name,
                        "data": {
                            "subject": data.get("subject", ""),
                            "description": data.get("description", ""),
                            "status": data.get("status", ""),
                            "owner": data.get("owner", ""),
                        },
                    })
                except (json.JSONDecodeError, OSError):
                    continue

    session_id = os.environ.get("CLAUDE_SESSION_ID", "")

    sidecar = {
        "commit_sha": sha,
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
        "project_root": toplevel,
        "project_id": project_id,
        "session_id": session_id,
        "task_references": task_references,
        "task_dumps": task_dumps,
    }

    # Write the sidecar file with file locking
    out_dir = COMMIT_CONTEXT_DIR / project_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{sha}.json"

    try:
        fd = open(out_file, "w")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        json.dump(sidecar, fd, indent=2)
        fd.write("\n")
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()
    except (BlockingIOError, OSError):
        sys.exit(0)

    # Auto-install git post-rewrite hook
    try:
        git_dir = subprocess.check_output(
            ["git", "rev-parse", "--git-dir"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        install_post_rewrite_hook(Path(git_dir))
    except (subprocess.CalledProcessError, OSError):
        pass

    sys.exit(0)


def install_post_rewrite_hook(git_dir: Path):
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_file = hooks_dir / "post-rewrite"

    hook_invocation = f'python3 "{POST_REWRITE_SCRIPT}" "$@"\n'

    if not hook_file.exists():
        hook_file.write_text(
            f"#!/bin/sh\n{POST_REWRITE_MARKER}\n{hook_invocation}"
        )
        hook_file.chmod(hook_file.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    else:
        content = hook_file.read_text()
        if POST_REWRITE_MARKER not in content:
            with open(hook_file, "a") as f:
                f.write(f"\n{POST_REWRITE_MARKER}\n{hook_invocation}")


if __name__ == "__main__":
    main()
