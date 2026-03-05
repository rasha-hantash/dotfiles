#!/usr/bin/env python3
"""UserPromptSubmit hook -- inject relevant brain-os context.

Reads the user prompt, extracts keywords, searches brain-os markdown files
for relevant content, and outputs top excerpts as plain text stdout.
"""

import json
import os
import re
import sys

BRAIN_OS_ROOT = os.path.expanduser(
    "~/workspace/personal/explorations/brain-os"
)

# Directories to search (relative to BRAIN_OS_ROOT)
SEARCH_DIRS = ["", "claude", "python", "rust", "git", "unix", "interviews"]

# Directories to exclude
EXCLUDE_DIRS = {"claude-learnings", "papers", ".claude", ".git", "node_modules"}

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

MAX_EXCERPT_CHARS = 800
MAX_RESULTS = 5


def extract_keywords(prompt: str) -> list[str]:
    """Extract meaningful keywords from a prompt."""
    words = re.findall(r"[a-zA-Z0-9_-]+", prompt.lower())
    keywords = []
    for w in words:
        if len(w) >= 3 and w not in STOP_WORDS:
            keywords.append(w)
    return keywords


def get_searchable_files() -> list[str]:
    """Get all markdown files in searchable directories."""
    files = []
    for d in SEARCH_DIRS:
        dir_path = os.path.join(BRAIN_OS_ROOT, d) if d else BRAIN_OS_ROOT
        if not os.path.isdir(dir_path):
            continue
        for entry in os.listdir(dir_path):
            if not entry.endswith(".md"):
                continue
            if entry == "README.md" and d == "":
                continue
            full_path = os.path.join(dir_path, entry)
            if os.path.isfile(full_path):
                # Check not in excluded directory
                rel = os.path.relpath(full_path, BRAIN_OS_ROOT)
                top_dir = rel.split(os.sep)[0] if os.sep in rel else ""
                if top_dir not in EXCLUDE_DIRS:
                    files.append(full_path)
    return files


def extract_relevant_section(content: str, keywords: list[str]) -> str | None:
    """Extract the most relevant section from a file based on keyword density."""
    # Split into sections by ## headings
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

    # Truncate if too long
    if len(best_section) > MAX_EXCERPT_CHARS:
        best_section = best_section[:MAX_EXCERPT_CHARS] + "\n..."

    return best_section.strip()


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    prompt = data.get("prompt", "")
    if not prompt or len(prompt) < 5:
        sys.exit(0)

    keywords = extract_keywords(prompt)
    if not keywords:
        sys.exit(0)

    files = get_searchable_files()
    results: list[tuple[int, str, str]] = []  # (score, filename, excerpt)

    for filepath in files:
        try:
            with open(filepath) as f:
                content = f.read()
        except OSError:
            continue

        # Pass 1: filename matching (high signal)
        basename = os.path.basename(filepath).lower().replace(".md", "")
        filename_score = sum(2 for kw in keywords if kw in basename)

        # Pass 2: content keyword counting
        content_lower = content.lower()
        content_score = sum(content_lower.count(kw) for kw in keywords)

        total_score = filename_score + content_score
        if total_score < 2:
            continue

        excerpt = extract_relevant_section(content, keywords)
        if excerpt:
            rel_path = os.path.relpath(filepath, BRAIN_OS_ROOT)
            results.append((total_score, rel_path, excerpt))

    if not results:
        sys.exit(0)

    # Sort by score descending, take top N
    results.sort(key=lambda x: x[0], reverse=True)
    results = results[:MAX_RESULTS]

    output_parts = ["## Relevant brain-os context (auto-injected)\n"]
    for _score, rel_path, excerpt in results:
        output_parts.append(f"### From `{rel_path}`\n")
        output_parts.append(excerpt)
        output_parts.append("")

    print("\n".join(output_parts))


if __name__ == "__main__":
    main()
