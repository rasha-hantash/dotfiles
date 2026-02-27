---
name: test-runner
description: Run the project test suite and report a concise pass/fail summary. Use after writing or modifying code that has tests.
---

Run the project test suite and report results. Use this after writing or modifying code — skip for docs, config, or trivial edits.

## Workflow

1. **Detect test frameworks** by scanning the project root and subdirectories:
   - `pyproject.toml` or `pytest.ini` or `**/tests/` → **pytest** (prefer `uv run pytest` if `uv` is available)
   - `package.json` with `test` script → **npm test** / **vitest** / **jest**
   - `go.mod` → **go test ./...**
   - `Cargo.toml` → **cargo test**
   - `*.csproj` or `*.sln` → **dotnet test**
   - `Makefile` with `test` target → **make test**
   - `Taskfile.yml` with `test` task → **task test**
2. **Monorepo awareness**: Check for multiple test suites in subdirectories (e.g., `backend/`, `frontend/`, `services/`)
3. Run each detected test suite from the appropriate directory
4. Report a concise summary

## Running Tests

For each detected framework, run from the **project root** or appropriate subdirectory:

**Python** (prefer `uv` when available):

```bash
uv run pytest --tb=short -q 2>&1 || pytest --tb=short -q 2>&1
```

**JavaScript/TypeScript**:

```bash
npm test 2>&1
```

**Go**:

```bash
go test ./... -short -count=1 2>&1
```

**Rust**:

```bash
cargo test 2>&1
```

**.NET**:

```bash
dotnet test --verbosity minimal 2>&1
```

**Makefile/Taskfile**:

```bash
make test 2>&1  # or: task test 2>&1
```

## Output Format

```
## Test Results

**[Suite Name]**: X passed, Y failed, Z skipped
**[Suite Name]**: X passed, Y failed (or "no tests configured")

### Failures (if any)
- `test_name` in `file_path`: Brief description of failure
  - Likely cause: ...

### Summary
Overall: PASS / FAIL
```

Keep output concise. Only include failure details for tests that actually failed. Do not reproduce full stack traces — summarize the likely cause in one sentence.
