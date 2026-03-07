---
name: yt-analyze
description: Analyze a YouTube video transcript and extract timestamped highlights relevant to a specific topic or interest. Accepts a YouTube URL or raw transcript text.
---

Extract timestamped, clickable highlights from a YouTube video based on the user's stated context or interest.

## Input

The user provides:
1. **A YouTube URL** or **raw transcript text** (with timestamps)
2. **Context/interest** — what they care about (e.g., "Rust error handling patterns", "hiring advice for startups")

## Workflow

### Step 1: Get the transcript

**If YouTube URL provided:**

Run the helper script to fetch the transcript:

```bash
uv run --with youtube-transcript-api python3 ~/.claude/skills/yt-analyze/fetch_transcript.py "YOUTUBE_URL"
```

If the script returns an error about language availability, try `--list-languages` to see what's available, then re-run with `--lang CODE`.

**If raw transcript text provided:**

Parse timestamps from the text directly. Common formats: `[HH:MM:SS]`, `(MM:SS)`, `0:00`, `1:23:45`.

### Step 2: Analyze against user's context

Read through the full transcript and identify segments that are relevant to the user's stated interest. Look for:
- Direct discussions of the topic
- Tangential insights that connect to the topic
- Actionable advice or concrete examples
- Surprising or non-obvious points

### Step 3: Output highlights

For each relevant segment, output:

```
### [Brief topic label]

**[HH:MM:SS](https://youtube.com/watch?v=VIDEO_ID&t=Ns)** (where N = start_seconds - 5, floored to 0)

> "Key quote from the transcript"

[2-3 sentence summary of what's discussed and why it's relevant to the user's context]
```

Rules for timestamps:
- Offset the `&t=` parameter by **5 seconds early** (minimum 0) so the user gets context when they click
- Format the display as `HH:MM:SS` (or `MM:SS` if under 1 hour)
- Group nearby snippets (within 30s) into a single highlight rather than listing each individually

### Step 4: Synthesis

After all highlights, add:

```
## Summary

**Key themes:** [bullet list of 3-5 main themes relevant to user's context]

**Most actionable insight:** [single most useful takeaway]

**Gaps:** [what the video didn't cover that the user might want to explore elsewhere]

**Total relevant segments:** X out of ~Y minutes
```

## Edge cases

- If the video has no transcript available, tell the user and suggest they paste a manual transcript
- If the transcript is auto-generated, note that quotes may have transcription errors
- If nothing in the video matches the user's context, say so honestly rather than stretching relevance
- For very long videos (>1hr), focus on the top 10-15 most relevant segments
