---
name: ci
description: Quick CI checks — run linters, tests, and grep-based perf pattern detection on changed files. Use after writing or modifying code.
---

Run a quick CI pipeline on changed files. Use this after writing or modifying code that affects logic — skip for docs, config, or trivial edits.

## Workflow

1. Run `git diff --name-only HEAD` to find changed source files
2. If no code changes, report "No changes to check" and stop
3. Based on file extensions, run the appropriate checks below
4. Report all failures clearly so they can be fixed

## Checks by Language

### Python (\*.py files changed)

**Lint:**

```bash
ruff check . 2>&1  # or: uv run ruff check . 2>&1
```

**Tests:**

```bash
pytest --tb=short -q 2>&1  # or: uv run pytest --tb=short -q 2>&1
```

(Exit code 5 = no tests collected, which is fine — not a failure)

### JavaScript / TypeScript (_.ts, _.tsx, _.js, _.jsx files changed)

**Build check:**

```bash
npm run build --if-present 2>&1
```

### Go (\*.go files changed)

**Vet:**

```bash
go vet ./... 2>&1
```

**Tests:**

```bash
go test ./... -short -count=1 2>&1
```

## Grep-based Performance Patterns

After running linters/tests, scan each changed file for common performance anti-patterns:

### Python

- **N+1 queries**: `execute()` / `fetchone()` / `fetchall()` called inside a `for` loop
- **Blocking sleep in async**: `time.sleep()` inside an `async def` function (should use `asyncio.sleep`)

### JavaScript / TypeScript

- **Inline objects in JSX**: `={{` in JSX props (excluding `style`/`className`) — causes unnecessary re-renders
- **useEffect without cleanup**: `useEffect` containing `setInterval`/`addEventListener`/`subscribe` but no cleanup `return`

### Go

- **String concat in loops**: `+=` inside a `for` loop (should use `strings.Builder`)
- **defer in loops**: `defer` inside a `for` loop (defers stack until function exit, not loop iteration)

## Output Format

```
## CI Results

### Lint/Build
- [tool]: PASS or FAIL with details

### Tests
- [framework]: X passed, Y failed

### Performance Patterns
- [file]: Description of pattern detected

### Summary
Overall: PASS / FAIL
```

If everything passes, just report "All checks passed" concisely.
