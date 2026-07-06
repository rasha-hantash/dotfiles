#!/usr/bin/env python3
"""PreToolUse (Edit|Write) hook — block file edits on main/master branches.

Reads hook JSON from stdin, checks the current git branch, and denies
edits if we're on a protected branch. Forces use of worktrees/feature branches.
"""

import json
import os
import subprocess
import sys


PROTECTED_BRANCHES = {"main", "master"}


def repo_dir_for(file_path: str) -> str | None:
    """Nearest existing directory containing file_path (the file may not exist yet)."""
    d = os.path.dirname(os.path.abspath(os.path.expanduser(file_path)))
    while d and d != "/" and not os.path.isdir(d):
        d = os.path.dirname(d)
    return d if d and os.path.isdir(d) else None


def get_current_branch(file_path: str) -> str | None:
    """Get the current branch for the repo containing file_path (NOT the process CWD)."""
    repo_dir = repo_dir_for(file_path)
    if repo_dir is None:
        return None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=repo_dir,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def is_gitignored(file_path: str) -> bool:
    """True if file_path matches a .gitignore pattern in its repo — such files
    live only on main by design and can't leak into a PR, so editing is safe."""
    repo_dir = repo_dir_for(file_path)
    if repo_dir is None:
        return False
    try:
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", "--", file_path],
            capture_output=True,
            timeout=5,
            cwd=repo_dir,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        sys.exit(0)

    # Allow edits outside of git repos (e.g. ~/.claude/ config files)
    branch = get_current_branch(file_path)
    if branch is None:
        sys.exit(0)

    if branch in PROTECTED_BRANCHES and not is_gitignored(file_path):
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"Cannot edit files on '{branch}' branch. "
                    "Use a worktree (EnterWorktree) or feature branch first."
                ),
            }
        }
        json.dump(result, sys.stdout)
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
