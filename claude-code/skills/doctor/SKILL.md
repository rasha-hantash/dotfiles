---
name: doctor
description: Scan brain-os convention docs for provenance health — uncited sections, orphaned citations, and quality issues.
---

Run a provenance health check on brain-os convention docs.

## Checks

### 1. Uncited sections (info)

Scan all convention docs for `## sections` that contain no footnote references (`[^N]`).

```bash
# For each .md file in brain-os (excluding claude-learnings/, papers/, articles/, .git/)
# Split by ## headings
# Check if any [^N] reference exists in the section body
```

Report sections without citations. Not all content needs citations — manually authored docs are fine. Severity: info.

### 2. Orphaned citations (warning)

For each footnote definition (`[^N]: session:<prefix>:<line>...`), validate:

- **JSONL exists:** Scan `~/.claude/projects/` for a file matching `<prefix>*.jsonl`
- **Line in range:** The cited line number is within the file's line count
- **Character offsets valid** (if present): Offsets are within the entry's text length

```bash
# Extract all footnote definitions matching: [^N]: session:<prefix>:<line>
# For each, glob ~/.claude/projects/*/<prefix>*.jsonl
# If found, check line count and optionally validate char offsets
```

Report citations that can't be resolved. Severity: warning.

## Output format

```
brain-os doctor report
======================

WARNINGS (N):
  <file>:
    - Citation [^N]: session:<prefix>:<line> — JSONL not found
    - Citation [^N]: session:<prefix>:<line> — line N but file has M lines

INFO:
  N docs scanned, M citations found, K sections uncited

  Sections without citations:
    <file>: "<section heading>" (added manually?)
```

## How to run

1. Read all `.md` files in `~/workspace/personal/explorations/brain-os/` (excluding `claude-learnings/`, `papers/`, `articles/`, `.git/`, `node_modules/`)
2. Parse footnote definitions and section headings
3. Validate citations against local JSONL files
4. Print the report
