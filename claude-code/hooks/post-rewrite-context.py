#!/usr/bin/env python3
"""Git post-rewrite hook helper: copies sidecar files when commits are rewritten.

Called by git's native post-rewrite hook after `git commit --amend` and `git rebase`.
Reads old-sha/new-sha pairs from stdin and copies sidecar context files accordingly.
"""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

COMMIT_CONTEXT_DIR = Path.home() / ".claude" / "commit-context"


def main():
    # Determine project-id
    try:
        toplevel = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except subprocess.CalledProcessError:
        sys.exit(0)

    project_id = hashlib.sha256(toplevel.encode()).hexdigest()[:12]
    context_dir = COMMIT_CONTEXT_DIR / project_id

    if not context_dir.is_dir():
        sys.exit(0)

    # Git provides old-sha new-sha pairs on stdin, one per line
    for line in sys.stdin:
        parts = line.strip().split()
        if len(parts) < 2:
            continue

        old_sha = parts[0]
        new_sha = parts[1]

        old_file = context_dir / f"{old_sha}.json"
        new_file = context_dir / f"{new_sha}.json"

        if not old_file.exists():
            continue

        try:
            old_data = json.loads(old_file.read_text())

            # Create new sidecar file with rewritten_from traceability
            new_data = dict(old_data)
            new_data["commit_sha"] = new_sha
            new_data["rewritten_from"] = old_sha
            new_file.write_text(json.dumps(new_data, indent=2) + "\n")

            # Mark the old file as superseded
            old_data["superseded_by"] = new_sha
            old_file.write_text(json.dumps(old_data, indent=2) + "\n")

        except (json.JSONDecodeError, OSError):
            continue

    sys.exit(0)


if __name__ == "__main__":
    main()
