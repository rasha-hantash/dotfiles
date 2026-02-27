---
name: perf-review
description: Review recent code changes for performance issues, anti-patterns, and scalability concerns. Use after writing or modifying significant code.
---

Review code changes for performance issues. Use this after writing or modifying logic-heavy code — skip for docs, config, or trivial edits.

## Workflow

1. **Detect the project stack** by checking for manifest files:
   - `pyproject.toml`, `setup.py`, `requirements.txt` → Python
   - `package.json` → JavaScript/TypeScript (check for React, Next.js, Vue, etc.)
   - `go.mod` → Go
   - `Cargo.toml` → Rust
   - `*.csproj`, `*.sln` → .NET
   - `pom.xml`, `build.gradle` → Java/Kotlin
2. Run `git diff HEAD~1` to identify changed files (or `git diff main` if on a feature branch)
3. Read each changed file in full to understand context
4. Apply **only the relevant** checklists below based on detected stack
5. Report findings grouped by severity: **Critical**, **Warning**, **Suggestion**
6. If no issues found, say so explicitly

## Performance Checklists

### Python

- **N+1 queries**: Querying inside a loop instead of batching (e.g., `execute_values()`, bulk ORM operations, or a single JOIN)
- **Unbatched inserts**: Inserting rows one-by-one instead of using bulk insert APIs
- **Unbounded queries**: `SELECT` without `LIMIT` on tables that can grow
- **Waterfall API calls**: Sequential `await` calls to independent services that could be parallelized (e.g., `asyncio.gather()`, `ThreadPoolExecutor`)
- **Memory leaks**: Unbounded caches, missing `finally` cleanup on file handles / DB connections, reference cycles
- **Holding DB connections across I/O**: Keeping a cursor open while doing network calls or file I/O
- **Blocking calls in async context**: Synchronous I/O in async handlers without `run_in_executor`
- **Missing connection cleanup**: DB connections or file handles not closed in exception paths

### JavaScript / TypeScript

- **Unnecessary re-renders**: Inline object/array/function literals in JSX props, missing `React.memo` on expensive components
- **Missing memoization**: Expensive computations in render without `useMemo`, unstable callbacks without `useCallback`
- **Derived state in useState**: State that can be computed from other state/props
- **Missing code splitting**: Large components or routes imported eagerly that should use lazy loading
- **Missing virtualization**: Rendering large lists (>100 items) without windowing
- **Uncontrolled fetching**: Missing abort controllers, no deduplication of concurrent requests
- **Bundle size**: Importing entire libraries when tree-shakeable alternatives exist

### Go

- **Goroutine leaks**: Goroutines that block forever on channels with no consumer, missing context cancellation
- **String concatenation in loops**: Using `+=` instead of `strings.Builder`
- **Mutex held across I/O**: Holding a `sync.Mutex` lock during network calls, file I/O, or channel operations
- **Deferred closes in loops**: `defer file.Close()` inside a loop (defers stack until function exit)
- **Missing `context.Context`**: Public functions that do I/O without accepting a context parameter
- **Unbuffered channels in hot paths**: Synchronous channels causing goroutine scheduling overhead
- **Slice preallocation**: Appending in loops without preallocating via `make([]T, 0, n)`

### Rust

- **Unnecessary cloning**: `.clone()` where a borrow would suffice
- **Allocations in hot loops**: `String::new()`, `Vec::new()`, or `format!()` inside tight loops
- **Missing `collect` type hints**: Iterators that could be collected more efficiently with capacity hints
- **Unbounded channels**: `mpsc::channel()` without backpressure

### Universal (all stacks)

- **O(n^2) on large collections**: Nested loops, repeated `in`/`contains` on lists instead of sets/maps
- **Duplicated / derivable state**: Same data stored in multiple places
- **Unbounded caches**: Caches that grow without eviction policy (LRU, TTL, etc.)
- **Resource handle leaks**: Files, connections, or clients not closed in all code paths
- **Missing pagination**: API endpoints returning all records without pagination
- **Synchronous operations that should be async**: Blocking the main thread/event loop

## Output Format

```
## Performance Review

**Detected stack**: [languages and frameworks found]

### Critical
- **[file:line]** Description of the issue and why it matters
  - Suggested fix: ...

### Warning
- **[file:line]** Description of the issue
  - Suggested fix: ...

### Suggestion
- **[file:line]** Description of the potential improvement
  - Suggested fix: ...

### No Issues
(only if nothing was found)
```

Be specific: reference exact file paths and line numbers. Explain _why_ each issue matters.
