#!/usr/bin/env python3
"""Tests for worktree-guard.py — PreToolUse hook for EnterWorktree|EnterWorktree.

Verifies that worktree creation is gracefully skipped in non-git directories
and allowed in git repos.
"""

import json
import os
import subprocess
import sys
import tempfile

# Path to the hook under test
HOOK = os.path.join(os.path.dirname(__file__), "worktree-guard.py")


def run_hook(tool_input: dict, tool_name: str = "EnterWorktree", cwd: str | None = None) -> dict | None:
    """Run the worktree-guard hook with the given input and return parsed output."""
    hook_input = {
        "tool_name": tool_name,
        "tool_input": tool_input,
    }
    result = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(hook_input),
        capture_output=True,
        text=True,
        timeout=10,
        cwd=cwd,
    )
    assert result.returncode == 0, f"Hook crashed: {result.stderr}"
    if result.stdout.strip():
        return json.loads(result.stdout)
    return None


def test_denies_worktree_in_non_git_directory():
    """EnterWorktree in a plain directory (no .git) should be denied gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output = run_hook({"name": "my-worktree"}, cwd=tmpdir)
        assert output is not None, "Expected deny output, got None (silent allow)"
        decision = output["hookSpecificOutput"]["permissionDecision"]
        assert decision == "deny", f"Expected deny, got {decision}"
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]
        assert "not" in reason.lower() and "git" in reason.lower(), (
            f"Reason should mention not being in a git repo: {reason}"
        )


def test_allows_worktree_in_git_repo():
    """EnterWorktree inside a git repo should be allowed (no output)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
        output = run_hook({"name": "my-worktree"}, cwd=tmpdir)
        assert output is None, f"Expected silent allow (None), got: {output}"


def test_allows_worktree_in_nested_git_directory():
    """EnterWorktree in a subdirectory of a git repo should be allowed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
        subdir = os.path.join(tmpdir, "src", "lib")
        os.makedirs(subdir)
        output = run_hook({"name": "my-worktree"}, cwd=subdir)
        assert output is None, f"Expected silent allow, got: {output}"


def test_handles_missing_tool_input_gracefully():
    """Malformed input should not crash — just allow."""
    with tempfile.TemporaryDirectory() as tmpdir:
        hook_input = {"tool_name": "EnterWorktree"}  # no tool_input
        result = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            timeout=10,
            cwd=tmpdir,
        )
        assert result.returncode == 0, f"Hook crashed on malformed input: {result.stderr}"


def test_handles_empty_stdin_gracefully():
    """Empty stdin should not crash."""
    result = subprocess.run(
        [sys.executable, HOOK],
        input="",
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f"Hook crashed on empty stdin: {result.stderr}"


if __name__ == "__main__":
    tests = [
        test_denies_worktree_in_non_git_directory,
        test_allows_worktree_in_git_repo,
        test_allows_worktree_in_nested_git_directory,
        test_handles_missing_tool_input_gracefully,
        test_handles_empty_stdin_gracefully,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS  {test.__name__}")
            passed += 1
        except (AssertionError, Exception) as e:
            print(f"  FAIL  {test.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
