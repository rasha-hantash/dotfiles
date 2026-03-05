#!/usr/bin/env python3
"""PreToolUse (Edit|Write) hook — block file edits on main/master branches.

Reads hook JSON from stdin, checks the current git branch, and denies
edits if we're on a protected branch. Forces use of worktrees/feature branches.
"""

import json
import subprocess
import sys


PROTECTED_BRANCHES = {"main", "master"}


def get_current_branch(file_path: str) -> str | None:
    """Get the current branch for the repo containing file_path."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


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

    if branch in PROTECTED_BRANCHES:
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
