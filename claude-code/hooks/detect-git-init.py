#!/usr/bin/env python3
"""PostToolUse(Bash) hook: detect `git init` and suggest Mesa setup."""

import json
import sys


def main():
    try:
        event = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        print(json.dumps({}))
        return

    tool_input = event.get("tool_input", {})
    command = tool_input.get("command", "")

    # Fast exit for non-git-init commands
    if not command.strip().startswith("git init"):
        print(json.dumps({}))
        return

    tool_output = event.get("tool_output", {})
    stdout = tool_output.get("stdout", "")
    stderr = tool_output.get("stderr", "")

    # Check that git init succeeded
    if "fatal" in stderr.lower() or "error" in stderr.lower():
        print(json.dumps({}))
        return

    if "Initialized" not in stdout and "Reinitialized" not in stdout:
        print(json.dumps({}))
        return

    print(json.dumps({
        "systemMessage": (
            "A new git repository was just initialized. "
            "Ask the user if they'd like to set up Mesa code review for this project. "
            "If they say yes, use the mesa-setup agent to analyze the project and "
            "generate a mesa.config.ts file."
        )
    }))


if __name__ == "__main__":
    main()
