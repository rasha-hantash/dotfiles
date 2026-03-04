#!/usr/bin/env python3
"""PostToolUse(Bash) hook: git-related post-processing.

Combines two concerns:
1. git init detection → suggests Mesa code review setup
2. git commit detection → captures task context as sidecar JSON

Reads hook JSON from stdin. Returns systemMessage for git init,
writes sidecar files for git commit, exits 0 for everything else.
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


def handle_git_init(event):
    """Detect `git init` and suggest Mesa setup."""
    tool_output = event.get("tool_output", {})
    stdout = tool_output.get("stdout", "")
    stderr = tool_output.get("stderr", "")

    if "fatal" in stderr.lower() or "error" in stderr.lower():
        return

    if "Initialized" not in stdout and "Reinitialized" not in stdout:
        return

    print(json.dumps({
        "systemMessage": (
            "A new git repository was just initialized. "
            "Ask the user if they'd like to set up Mesa code review for this project. "
            "If they say yes, use the mesa-setup agent to analyze the project and "
            "generate a mesa.config.ts file."
        )
    }))


def handle_git_commit():
    """Capture task context as sidecar JSON on git commit."""
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except subprocess.CalledProcessError:
        return

    try:
        toplevel = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except subprocess.CalledProcessError:
        return

    project_id = hashlib.sha256(toplevel.encode()).hexdigest()[:12]

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

    sidecar = {
        "commit_sha": sha,
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
        "project_root": toplevel,
        "project_id": project_id,
        "session_id": os.environ.get("CLAUDE_SESSION_ID", ""),
        "task_references": task_references,
        "task_dumps": task_dumps,
    }

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
        return

    try:
        git_dir = subprocess.check_output(
            ["git", "rev-parse", "--git-dir"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        install_post_rewrite_hook(Path(git_dir))
    except (subprocess.CalledProcessError, OSError):
        pass


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


def main():
    try:
        event = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    command = event.get("tool_input", {}).get("command", "").strip()
    if not command:
        sys.exit(0)

    if command.startswith("git init"):
        handle_git_init(event)
    elif "git commit" in command:
        handle_git_commit()

    sys.exit(0)


if __name__ == "__main__":
    main()
