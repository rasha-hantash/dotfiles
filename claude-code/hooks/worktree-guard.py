#!/usr/bin/env python3
"""PreToolUse (EnterWorktree) hook — skip worktree creation in non-git directories.

When the current directory is not inside a git repository, denies EnterWorktree
with a friendly message instead of letting the tool fail with a confusing error.
"""

import json
import subprocess
import sys


def is_inside_git_repo() -> bool:
    """Check if the current working directory is inside a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except (subprocess.TimeoutExpired, OSError):
        return False


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    # If not in a git repo, deny gracefully
    if not is_inside_git_repo():
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "Not in a git repository — worktree creation skipped. "
                    "You can edit files directly in this directory."
                ),
            }
        }
        json.dump(result, sys.stdout)

    # In a git repo — allow (no output)
    sys.exit(0)


if __name__ == "__main__":
    main()
