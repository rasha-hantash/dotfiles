#!/usr/bin/env python3
"""PreToolUse (Bash) hook — command safety guardrails.

Reads hook JSON from stdin, inspects the command, and returns:
- permissionDecision: "deny"  for dangerous commands
- permissionDecision: "allow" for known-safe commands (formatters, test runners)
- no output (exit 0) to fall through to normal permissions
"""

import json
import os
import re
import sys

SENTINEL = os.path.expanduser("~/.claude/.pr-review-active")

# --- PR review context: allowed only when sentinel file exists ---
PR_REVIEW_PATTERNS = [
    r"^git\s+add\b",
    r"^git\s+commit\b",
    r"^git\s+push\b",
    r"^sleep\s+\d+",
]

# --- Dangerous patterns: deny immediately ---
DENY_PATTERNS = [
    # Privilege escalation
    (r"\bsudo\b", "sudo commands are blocked"),
    (r"\bdd\b.*\bof=", "dd write operations are blocked"),
    # Destructive git operations
    (r"git\s+push\s+.*--force.*\b(main|master)\b", "force push to main/master is blocked"),
    (r"git\s+push\s+.*\b(main|master)\b.*--force", "force push to main/master is blocked"),
    (r"git\s+reset\s+--hard", "git reset --hard is blocked"),
    (r"git\s+checkout\s+\.", "git checkout . is blocked"),
    (r"git\s+clean\s+-[a-zA-Z]*f", "git clean -f is blocked"),
    (r"git\s+branch\s+-D\b", "git branch -D is blocked"),
    # Broad destructive rm
    (r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+/\s", "rm -rf / is blocked"),
    (r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+/\*", "rm -rf /* is blocked"),
    (r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+~", "rm -rf ~ is blocked"),
    (r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+\.\.", "rm -rf .. is blocked"),
    # Dangerous permissions
    (r"chmod\s+777\b", "chmod 777 is blocked"),
    # Remote code execution
    (r"curl\s.*\|\s*(ba)?sh", "curl piped to shell is blocked"),
    (r"wget\s.*\|\s*(ba)?sh", "wget piped to shell is blocked"),
    # Fork bombs
    (r":\(\)\s*\{\s*:\|:\s*&\s*\}\s*;", "fork bombs are blocked"),
    # System directory writes
    (r">\s*/etc/", "writing to /etc/ is blocked"),
    (r"tee\s+/etc/", "writing to /etc/ is blocked"),
    # Process killing
    (r"\bkillall\b", "killall is blocked"),
]

# --- Safe patterns: auto-approve ---
ALLOW_PATTERNS = [
    # Formatters
    r"^(uv\s+run\s+)?ruff\s+(format|check)\b",
    r"^(uv\s+run\s+)?black\b",
    r"^(npx\s+)?prettier\b",
    r"^gofmt\b",
    r"^pg_format\b",
    # Test runners
    r"^(uv\s+run\s+)?pytest\b",
    r"^(uv\s+run\s+)?python3?\s+-m\s+pytest\b",
    r"^npm\s+(run\s+)?test\b",
    r"^go\s+test\b",
    # Graphite
    r"^gt\b",
    # Taskfile
    r"^task\b",
]


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    command = data.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    # Check deny patterns first
    for pattern, reason in DENY_PATTERNS:
        if re.search(pattern, command):
            result = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
            json.dump(result, sys.stdout)
            sys.exit(0)

    # Check PR review context patterns
    stripped = command.strip()
    for pattern in PR_REVIEW_PATTERNS:
        if re.search(pattern, stripped):
            if os.path.isfile(SENTINEL):
                result = {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "allow",
                        "permissionDecisionReason": "auto-approved: pr review context active",
                    }
                }
            else:
                result = {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "requires active pr review context (~/.claude/.pr-review-active)",
                    }
                }
            json.dump(result, sys.stdout)
            sys.exit(0)

    # Check allow patterns
    for pattern in ALLOW_PATTERNS:
        if re.search(pattern, stripped):
            result = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "auto-approved safe command",
                }
            }
            json.dump(result, sys.stdout)
            sys.exit(0)

    # Fall through to normal permission handling
    sys.exit(0)


if __name__ == "__main__":
    main()
