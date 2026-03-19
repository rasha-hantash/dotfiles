> **Archived 2026-03-17** — High-impact items done, remainder low-value

# Dev Setup Optimization Plan

Prioritized optimizations for the Claude Code + tmux + dotfiles workflow, identified from a full audit of CLAUDE.md, hooks, brain-os, and project configs.

## High Impact

### 1. Slim down global CLAUDE.md

The global CLAUDE.md is loaded into every session and consumes significant context. Most of its content is event-specific (learnings capture, PR review monitor, plan checkpoints) and only relevant when those events fire.

**Action:** Move event-specific instructions into the agents/skills that execute them:

- Session learnings capture workflow → `~/.claude/agents/learnings-capturer.md`
- PR review monitor protocol → `~/.claude/agents/pr-monitor.md`
- Plan file two-checkpoint flow → a dedicated skill or agent instruction

The global CLAUDE.md should contain only the minimal rules every session needs: framing protocol, dotfiles location, gt-over-git, pre-coding context gate, post-coding checks.

**Metric:** Measure CLAUDE.md line count before/after. Target: <100 lines (currently ~200+).

### 2. Batch promote brain-os learnings

9 learnings (13+ insights) all have `Status: pending`. The capture pipeline works but the promotion pipeline doesn't exist yet. Insights are trapped in session-specific files instead of in destination docs.

**Action:**

- Promote each pending learning into its suggested destination doc
- Add inline provenance at destination (`_Source: claude-learnings/...`\_)
- Update audit trail: set status to `promoted`, fill `Promoted to` and `Promoted on`
- Create missing destination docs: `graphite-conventions.md`, `dotfiles-conventions.md`

### 3. Agent definitions for extracted CLAUDE.md content

Item #1 moves instructions out of CLAUDE.md, but those instructions need well-defined agent files so they're actually invoked correctly. Without this, the extracted content becomes invisible.

**Action:**

- Define `~/.claude/agents/learnings-capturer.md` with the full learnings capture workflow
- Define `~/.claude/agents/pr-monitor.md` with the PR review monitor protocol
- Ensure agent files include trigger conditions and the complete procedural steps
- Verify agents are discoverable by Claude Code's agent system

### 4. Refine CLAUDE.md prompt framing overhead

The framing protocol adds a full round-trip (present frame → wait → proceed) to every non-trivial request. For rapid iteration sessions this is noticeable friction.

**Action:**

- Make framing auto-skip more aggressive: skip for follow-ups within established context, debugging iterations, and any request where the task and constraints are unambiguous
- Keep framing mandatory only for: new features, architectural decisions, and ambiguous requests
- Reduce the framing template size (combine Persona/Constraints and Context/Task where possible)

### 5. Clean up stale plan files in cove

6 plan files in cove root. Audit found:

| File                          | Status                                                   | Action                           |
| ----------------------------- | -------------------------------------------------------- | -------------------------------- |
| `context-fix-plan.md`         | **All 5 items checked off** (2026-03-03)                 | Delete — completed               |
| `integration-cove-plan.md`    | **All 12 items checked off** (2026-03-03)                | Delete — completed               |
| `command-r-pr-review-plan.md` | 0 checked, 0 unchecked (design doc, no progress section) | Keep or archive — future feature |
| `context-retriever-plan.md`   | 0 checked, 0 unchecked (design doc)                      | Keep or archive — future feature |
| `plan-context-viewer.md`      | 0 checked, 0 unchecked (design doc)                      | Keep or archive — future feature |
| `rebrand-clove-plan.md`       | 0 checked, 0 unchecked (design doc)                      | Keep or archive — future feature |

**Action:**

1. Delete `context-fix-plan.md` and `integration-cove-plan.md` (both 100% complete)
2. Decide on the 4 design docs: delete if abandoned, or commit as `docs/` if they have future value

## Medium Impact

### 6. MCP-ify technical-rag system

The pre-coding context gate requires a manual round-trip: Claude stops, asks user, user queries RAG, pastes result back. This breaks flow on every non-trivial Rust task.

**Goal:** Expose technical-rag as an MCP server so Claude Code can query conventions directly.

#### Architecture (current state)

- **Backend:** Python 3.14+ / FastAPI, PostgreSQL 16 + pgvector
- **Retrieval:** Hybrid search (cosine + BM25 + RRF), optional Cohere/cross-encoder reranking
- **Generation:** Claude API with citation-enforcing system prompt
- **Embeddings:** OpenAI `text-embedding-3-large` (3072-dim)
- **Storage:** PostgreSQL (chunks table with vector column), PDFs on disk
- **Interface:** REST API at `localhost:8000` + React frontend

#### MCP integration approach

The MCP server wraps the existing REST API — it does NOT embed the Python RAG code. This keeps the MCP layer thin and the RAG system independently deployable.

```
Claude Code ──MCP──→ technical-rag-mcp (thin wrapper) ──HTTP──→ FastAPI backend ──→ PostgreSQL
```

**MCP tools to expose:**

| Tool              | Maps to                               | Purpose                                                    |
| ----------------- | ------------------------------------- | ---------------------------------------------------------- |
| `query`           | `POST /api/v1/rag/query`              | Ask a question, get cited answer + sources                 |
| `search`          | Retriever only (no generation)        | Get raw chunks without Claude generation (cheaper, faster) |
| `list_documents`  | `GET /api/v1/documents`               | See what books are indexed                                 |
| `browse_sections` | `GET /api/v1/documents/{id}/sections` | Browse a book's chapter/section tree                       |

**Not exposed via MCP** (keep in web UI only):

- PDF ingestion (large file uploads, long-running)
- PDF viewer with bbox highlighting (visual)
- Document metadata editing (admin)

#### Known unknowns

1. **MCP server language choice:** Python (reuse existing deps, `mcp` SDK) vs TypeScript (better MCP ecosystem, official examples). Python is simpler since the backend is Python. **Decision needed.**
2. **Backend lifecycle:** Does the FastAPI backend need to be running independently, or should the MCP server start it? If independent, the MCP server is just an HTTP client. If embedded, it needs to manage uvicorn. **Leaning toward: independent — Docker Compose already runs it.**
3. **Auth/API keys:** The backend needs `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DATABASE_URL`. The MCP server only needs the backend URL if it's a thin wrapper. But if `query` triggers Claude generation, the API cost is double (Claude calling MCP which calls Claude). **Consider: expose `search` (retrieval-only) as the primary tool, let Claude Code do its own synthesis from the raw chunks.**
4. **Response size:** A `query` response includes full chunk text + citations. With `top_k=5`, this could be 10-15KB of context injected into the conversation. **Need to test if this blows up context budget on repeated queries.**
5. **Latency:** Full RAG pipeline (embed query → vector search → rerank → Claude generation) takes 3-8 seconds. For MCP, `search` (retrieval only, ~500ms) may be more practical than `query` (full generation, ~5s).
6. **Docker dependency:** The backend requires PostgreSQL + pgvector running. If Docker isn't up, MCP tool calls fail silently. **Need clear error messages.**

#### Tracer bullet plan

**Goal of tracer bullet:** Prove the thinnest possible end-to-end path works — from Claude Code invoking an MCP tool, through the MCP server, to the FastAPI backend, returning real results into the conversation. No polish, no error handling, just the critical path.

**Phase 0: Verify prerequisites (30 min)**

- [ ] Confirm Docker Compose brings up PostgreSQL + backend successfully
- [ ] Confirm `curl POST /api/v1/rag/query` returns results with existing indexed books
- [ ] Confirm `curl POST /api/v1/rag/query` with `generation=false` or equivalent retrieval-only endpoint exists (if not, note that we need to add one)
- [ ] Check if the `mcp` Python SDK exists and works: `pip install mcp` + hello-world MCP server

**Phase 1: Tracer bullet — single `search` tool (2-3 hours)**

The thinnest slice: one MCP tool that calls one REST endpoint and returns results.

- [ ] Create `mcp-server/` directory in technical-rag repo
- [ ] Implement MCP server with one tool: `search(question: str, top_k: int = 5) → list[chunks]`
  - Makes HTTP POST to `localhost:8000/api/v1/rag/query` (or retrieval-only endpoint)
  - Returns formatted chunks (content + section_hierarchy + book_title + page_number)
  - No generation — Claude Code synthesizes from raw chunks itself
- [ ] Add MCP server config to `~/.claude/settings.json` under `mcpServers`
- [ ] **Test:** Start Docker Compose + MCP server. Open Claude Code session. Ask a technical question. Verify the MCP tool appears, is callable, and returns real book content.

**Success criteria for tracer bullet:** Claude Code can ask "How should I handle errors in Rust?" and get back actual chunks from indexed Rust books, without the user copy-pasting anything.

**Phase 2: Harden + add tools (after tracer bullet works)**

- [ ] Add `list_documents` tool (see what's indexed)
- [ ] Add `browse_sections` tool (explore a book's structure)
- [ ] Add error handling: backend not running, DB not available, no results found
- [ ] Add startup check in MCP server (verify backend is reachable)
- [ ] Tune response format for context budget (truncate long chunks, limit metadata)
- [ ] Add optional `tags` filter to search (e.g., `tags=["rust"]` to scope to Rust books)

**Phase 3: Integrate into workflow**

- [ ] Update CLAUDE.md context gate to reference MCP tool instead of manual RAG round-trip
- [ ] Add `query` tool with full Claude generation for cases where Claude Code wants a synthesized answer with citations
- [ ] Document in brain-os: `technical-rag-mcp-conventions.md`

### 7. Profile hook latency + consolidate hooks

13 hooks across 8 events. PostToolUse fires 4 hooks on every tool call — that's the hot path. The bash validator (184 lines) runs on every Bash call.

**Action:**

- Add timestamp logging to hooks and measure per-hook latency over a session
- Identify any hooks adding perceptible delay (>100ms)
- Merge PostToolUse hooks into a single dispatcher script that conditionally runs sub-checks (one process spawn instead of four)
- Consolidate or simplify hot-path hooks (especially the bash validator, which overlaps with Claude Code's own permission system)

### 6. Add brain-os index

No README or table of contents. CLAUDE.md says "scan the directory" but there's no fast discovery mechanism.

**Action:** Add `README.md` to brain-os root with a one-line summary per convention doc and the learnings directory structure.

### 8. Prune ~/.claude/ storage (1.2GB) — UPGRADED from Medium

- `debug/` — 330MB
- `telemetry/` — 258MB
- `projects/` — 466MB (84 projects, many likely stale)

**Action:** Delete debug logs older than 30 days. Remove project directories for repos no longer active. Consider a periodic cleanup script.

### 9. Add shell aliases for terminal pane

No shell aliases exist for common operations. The terminal pane (bottom-right in cove layout) is used for manual commands but has no shortcuts.

**Action:** Add aliases to zshrc (via dotfiles):

- `cb` → `cargo build`
- `ct` → `cargo test`
- `cc` → `cargo clippy -- -D warnings`
- `cf` → `cargo fmt`
- `gs` → `gt sync`
- `gst` → `gt state`

## Lower Impact

### 10. Remove unused gopls plugin

`gopls-lsp` is installed but Go isn't a primary language. Consuming plugin resources without benefit.

**Action:** Uninstall via Claude Code plugin management unless Go work is planned.

### 11. Scope auto-format hook per project

The auto-format PostToolUse hook checks file extension on every Write/Edit across all languages. Single-language projects (like cove = Rust) do unnecessary detection.

**Action:** Consider project-level hook overrides that skip extension detection for known single-language repos. Low priority — current overhead is minimal.

## Progress

**This session (2026-03-04):** Items 1, 3, 4, 7, 8

- [x] 1. Slim down global CLAUDE.md (2026-03-04) — 158 → 109 lines; extracted Session Learnings + PR Monitor to agent files
- [ ] 2. Batch promote brain-os learnings (10 pending → promoted)
- [x] 3. Agent definitions for extracted CLAUDE.md content (2026-03-04) — created ~/.claude/agents/learnings-capturer.md and pr-monitor.md
- [x] 4. Refine CLAUDE.md prompt framing overhead (2026-03-04) — removed confirmation requirement, added more skip conditions
- [x] 5. Clean up stale plan files in cove (2026-03-04) — deleted context-fix-plan.md + integration-cove-plan.md (both 100% complete); kept 4 design docs + 1 active plan (api-migration)
- [ ] 6. MCP-ify technical-rag system
  - [x] 6.0 Verify prerequisites (2026-03-04) — PostgreSQL healthy, applied missing tags migration, backend starts OK, MCP SDK available via uv
  - [x] 6.1 Tracer bullet (2026-03-04) — 3 MCP tools (search, list_documents, browse_sections) + backend fix (autocommit + /search endpoint)
  - [x] 6.2 Harden + error handling (2026-03-04) — content truncation (1500 char max), timeout handling, generic exception fallback, configurable backend URL via env var
  - [x] 6.3 Integrate into workflow (2026-03-04) — updated CLAUDE.md Convention Docs section to reference technical-rag MCP tools + wired into settings.json
- [x] 7. Profile hook latency + consolidate hooks (2026-03-04) — all hooks <55ms, merged detect-git-init.py + post-commit-context.py → git-guard.py (4 PostToolUse hooks → 3)
- [x] 8. Prune ~/.claude/ storage (2026-03-04) — 1.2GB → 766MB; deleted 3,817 telemetry files (303MB) + 32 stale project configs
- [ ] 9. Add brain-os index README
- [ ] 10. Add shell aliases for terminal pane
- [ ] 11. Remove unused gopls plugin
- [ ] 12. Scope auto-format hook per project
