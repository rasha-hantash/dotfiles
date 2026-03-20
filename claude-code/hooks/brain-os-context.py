#!/usr/bin/env python3
"""UserPromptSubmit hook -- inject relevant brain-os context.

Reads the user prompt, extracts keywords, searches brain-os markdown files
for relevant content using TF-IDF scoring with domain awareness, and outputs
top excerpts as plain text stdout.

Logs structured JSON to ~/.local/state/brain-os/injections.log for
visibility into what context is being injected per turn.
"""

import json
import math
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

BRAIN_OS_ROOT = os.environ.get(
    "BRAIN_OS_PATH",
    os.path.expanduser("~/workspace/personal/explorations/brain-os"),
)

# Directories to exclude from search
EXCLUDE_DIRS = {
    "claude-learnings", "papers", ".claude", ".git", "node_modules",
    "recall", "transcripts", "articles", "interviews",
}

# Filenames to always exclude
EXCLUDE_FILES = {"README.md", "CLAUDE.md", "MEMORY.md", "AGENTS.md"}

# Common stop words to skip
STOP_WORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "had",
    "her", "was", "one", "our", "out", "has", "have", "been", "from",
    "this", "that", "with", "they", "will", "each", "make", "like",
    "how", "what", "when", "where", "which", "who", "why", "does",
    "use", "using", "used", "want", "need", "help", "just", "about",
    "into", "some", "than", "them", "then", "very", "also", "should",
    "could", "would", "there", "their", "been", "more", "other",
}

# Manifest files -> domain mapping for CWD-based domain detection
MANIFEST_MAP = {
    "Cargo.toml": "rust",
    "pyproject.toml": "python",
    "setup.py": "python",
    "package.json": "frontend",
    "tsconfig.json": "frontend",
    "go.mod": "go",
    "Gemfile": "ruby",
}

# Domain -> doc path prefixes that get a 2x boost
DOMAIN_DOC_MAP = {
    "rust": ["rust/"],
    "python": ["python/", "logging-conventions.md"],
    "frontend": ["frontend-conventions.md", "tanstack-router-guide.md", "html-security.md"],
    "go": [],
    "ruby": [],
}

# File extension -> domain for git diff signal
EXT_DOMAIN_MAP = {
    ".rs": "rust",
    ".py": "python",
    ".ts": "frontend", ".tsx": "frontend", ".jsx": "frontend", ".js": "frontend",
    ".go": "go",
    ".rb": "ruby",
}

MAX_EXCERPT_CHARS = 800
MAX_RESULTS = 5
LOG_DIR = os.path.expanduser("~/.local/state/brain-os")
LOG_FILE = os.path.join(LOG_DIR, "injections.log")


def extract_keywords(prompt: str) -> list[str]:
    """Extract meaningful keywords from a prompt."""
    words = re.findall(r"[a-zA-Z0-9_-]+", prompt.lower())
    keywords = []
    seen = set()
    for w in words:
        if len(w) >= 3 and w not in STOP_WORDS and w not in seen:
            keywords.append(w)
            seen.add(w)
    return keywords


def get_searchable_files() -> list[str]:
    """Discover all markdown files dynamically, excluding known non-convention dirs."""
    files = []
    for root, dirs, entries in os.walk(BRAIN_OS_ROOT):
        # Prune excluded directories in-place
        rel_root = os.path.relpath(root, BRAIN_OS_ROOT)
        top_dir = rel_root.split(os.sep)[0] if rel_root != "." else ""
        if top_dir in EXCLUDE_DIRS:
            dirs.clear()
            continue
        # Don't recurse into hidden dirs
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        for entry in entries:
            if not entry.endswith(".md"):
                continue
            if entry in EXCLUDE_FILES:
                continue
            # Skip plan files at root level
            if rel_root == "." and entry.endswith("-plan.md"):
                continue
            full_path = os.path.join(root, entry)
            if os.path.isfile(full_path):
                files.append(full_path)
    return files


def detect_domains(cwd: str) -> set[str]:
    """Detect project domains from CWD manifest files and recent git changes."""
    domains: set[str] = set()

    # Check manifest files in CWD
    for manifest, domain in MANIFEST_MAP.items():
        if os.path.exists(os.path.join(cwd, manifest)):
            domains.add(domain)

    # Check recent git diff for file extension signal
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~3..HEAD"],
            capture_output=True, text=True, timeout=3, cwd=cwd,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                ext = os.path.splitext(line)[1]
                if ext in EXT_DOMAIN_MAP:
                    domains.add(EXT_DOMAIN_MAP[ext])
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return domains


def compute_idf(files_contents: dict[str, str], keywords: list[str]) -> dict[str, float]:
    """Compute IDF weights for keywords across the document corpus."""
    n_docs = len(files_contents)
    if n_docs == 0:
        return {}

    idf: dict[str, float] = {}
    for kw in keywords:
        doc_freq = sum(
            1 for content in files_contents.values()
            if kw in content.lower()
        )
        # IDF: log(N / (1 + df)) — +1 to avoid division by zero
        idf[kw] = math.log(n_docs / (1 + doc_freq)) + 1.0
    return idf


def score_file(
    filepath: str,
    content: str,
    keywords: list[str],
    idf: dict[str, float],
    domains: set[str],
) -> float:
    """Score a file using TF-IDF with domain boosting and length normalization."""
    content_lower = content.lower()
    content_len = len(content_lower)
    if content_len == 0:
        return 0.0

    # TF-IDF score: sum of (term_freq * idf_weight) for each keyword
    tf_idf_score = 0.0
    for kw in keywords:
        tf = content_lower.count(kw)
        tf_idf_score += tf * idf.get(kw, 1.0)

    # Length normalization: divide by sqrt(doc_length) to prevent long docs dominating
    normalized_score = tf_idf_score / math.sqrt(content_len)

    # Filename bonus (high signal — 3x per matching keyword)
    basename = os.path.basename(filepath).lower().replace(".md", "")
    for kw in keywords:
        if kw in basename:
            normalized_score += 3.0 * idf.get(kw, 1.0)

    # Domain boost: 2x for docs matching detected project domain
    rel_path = os.path.relpath(filepath, BRAIN_OS_ROOT)
    for domain in domains:
        prefixes = DOMAIN_DOC_MAP.get(domain, [])
        if any(rel_path.startswith(p) or rel_path == p for p in prefixes):
            normalized_score *= 2.0
            break

    return normalized_score


def extract_relevant_section(content: str, keywords: list[str]) -> str | None:
    """Extract the most relevant section from a file based on keyword density."""
    sections = re.split(r"(?=^## )", content, flags=re.MULTILINE)
    if not sections:
        return None

    best_section = None
    best_score = 0

    for section in sections:
        section_lower = section.lower()
        score = sum(section_lower.count(kw) for kw in keywords)
        if score > best_score:
            best_score = score
            best_section = section

    if best_score == 0 or best_section is None:
        return None

    # Strip footnote citations (noise in injected context)
    best_section = re.sub(r"\[\^\d+\]", "", best_section)
    best_section = re.sub(r"^\[\^\d+\]:.*$", "", best_section, flags=re.MULTILINE)
    best_section = re.sub(r"\n{3,}", "\n\n", best_section)

    if len(best_section) > MAX_EXCERPT_CHARS:
        best_section = best_section[:MAX_EXCERPT_CHARS] + "\n..."

    return best_section.strip()


def log_injection(
    keywords: list[str],
    all_scored: list[tuple[float, str]],
    selected: list[tuple[float, str, str]],
    session_id: str,
    domains: set[str],
) -> None:
    """Append a structured JSON log entry for this invocation."""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session": session_id,
            "domains": sorted(domains),
            "keywords": keywords[:20],
            "scored_files": [
                {"file": path, "score": round(score, 1)} for score, path in all_scored
            ],
            "injected": [
                {"file": path, "score": round(score, 1)} for score, path, _ in selected
            ],
        }
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except OSError:
        pass  # logging must never break the hook


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    prompt = data.get("prompt", "")
    if not prompt or len(prompt) < 5:
        sys.exit(0)

    session_id = data.get("session_id", "unknown")
    cwd = data.get("cwd", os.getcwd())

    keywords = extract_keywords(prompt)
    if not keywords:
        log_injection([], [], [], session_id, set())
        sys.exit(0)

    # Detect project domains from CWD
    domains = detect_domains(cwd)

    # Load all files and their content
    files = get_searchable_files()
    files_contents: dict[str, str] = {}
    for filepath in files:
        try:
            with open(filepath) as f:
                files_contents[filepath] = f.read()
        except OSError:
            continue

    # Compute IDF weights across the corpus
    idf = compute_idf(files_contents, keywords)

    # Score each file
    all_scored: list[tuple[float, str]] = []
    results: list[tuple[float, str, str]] = []

    for filepath, content in files_contents.items():
        score = score_file(filepath, content, keywords, idf, domains)
        if score < 1.0:
            continue

        rel_path = os.path.relpath(filepath, BRAIN_OS_ROOT)
        all_scored.append((score, rel_path))

        excerpt = extract_relevant_section(content, keywords)
        if excerpt:
            results.append((score, rel_path, excerpt))

    if not results:
        log_injection(keywords, all_scored, [], session_id, domains)
        sys.exit(0)

    # Sort by score descending, take top N
    results.sort(key=lambda x: x[0], reverse=True)
    all_scored.sort(key=lambda x: x[0], reverse=True)
    results = results[:MAX_RESULTS]

    log_injection(keywords, all_scored, results, session_id, domains)

    # Build summary line showing what was matched
    matched_summary = ", ".join(
        f"{os.path.basename(path)} ({score:.0f})" for score, path, _ in results
    )
    top_keywords = ", ".join(keywords[:8])
    summary = f"> brain-os matched: {matched_summary} | keywords: {top_keywords}"

    output_parts = [summary, "", "## Relevant brain-os context (auto-injected)\n"]
    for _score, rel_path, excerpt in results:
        output_parts.append(f"### From `{rel_path}`\n")
        output_parts.append(excerpt)
        output_parts.append("")

    print("\n".join(output_parts))


if __name__ == "__main__":
    main()
