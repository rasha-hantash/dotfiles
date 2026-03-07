#!/usr/bin/env python3
"""Fetch YouTube video transcript as JSON.

Usage:
    uv run --with youtube-transcript-api python3 fetch_transcript.py "YOUTUBE_URL" [--lang CODE] [--list-languages]
"""

import argparse
import json
import re
import sys

from youtube_transcript_api import YouTubeTranscriptApi


def extract_video_id(url: str) -> str | None:
    """Extract video ID from various YouTube URL formats."""
    patterns = [
        # Standard watch URL: youtube.com/watch?v=ID
        r"(?:youtube\.com|music\.youtube\.com)/watch\?.*v=([a-zA-Z0-9_-]{11})",
        # Short URL: youtu.be/ID
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        # Embed URL: youtube.com/embed/ID
        r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
        # Shorts URL: youtube.com/shorts/ID
        r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
        # Live URL: youtube.com/live/ID
        r"youtube\.com/live/([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    # Maybe it's just a raw video ID
    if re.fullmatch(r"[a-zA-Z0-9_-]{11}", url):
        return url
    return None


def list_languages(video_id: str) -> None:
    """List available transcript languages for a video."""
    ytt_api = YouTubeTranscriptApi()
    transcript_list = ytt_api.list(video_id)
    languages = []
    for transcript in transcript_list:
        languages.append({
            "language": transcript.language,
            "language_code": transcript.language_code,
            "is_generated": transcript.is_generated,
            "is_translatable": transcript.is_translatable,
        })
    print(json.dumps({"video_id": video_id, "languages": languages}, indent=2))


def fetch_transcript(video_id: str, lang: str | None = None) -> None:
    """Fetch transcript and output as JSON."""
    ytt_api = YouTubeTranscriptApi()
    languages = [lang] if lang else ["en"]

    transcript_list = ytt_api.list(video_id)

    fetched = None
    source = None

    # 1. Try manually created transcript in requested language
    try:
        t = transcript_list.find_manually_created_transcript(languages)
        fetched = t.fetch()
        source = "manual"
    except Exception:
        pass

    # 2. Try any transcript in requested language (including auto-generated)
    if fetched is None:
        try:
            t = transcript_list.find_transcript(languages)
            fetched = t.fetch()
            source = "generated" if t.is_generated else "manual"
        except Exception:
            pass

    # 3. Try translating any available transcript to requested language
    if fetched is None:
        try:
            for t in transcript_list:
                if t.is_translatable:
                    translated = t.translate(languages[0])
                    fetched = translated.fetch()
                    source = "translated"
                    break
        except Exception:
            pass

    if fetched is None:
        available = []
        for t in transcript_list:
            available.append(f"{t.language} ({t.language_code})")
        print(json.dumps({
            "error": f"No transcript found for language: {languages[0]}",
            "available_languages": available,
            "video_id": video_id,
        }, indent=2))
        sys.exit(1)

    result = {
        "video_id": video_id,
        "language": fetched.language,
        "language_code": fetched.language_code,
        "is_generated": fetched.is_generated,
        "source": source,
        "snippets": fetched.to_raw_data(),
    }
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Fetch YouTube transcript as JSON")
    parser.add_argument("url", help="YouTube URL or video ID")
    parser.add_argument("--lang", default=None, help="Language code (default: en)")
    parser.add_argument("--list-languages", action="store_true", help="List available languages")
    args = parser.parse_args()

    video_id = extract_video_id(args.url)
    if not video_id:
        print(json.dumps({"error": f"Could not extract video ID from: {args.url}"}, indent=2))
        sys.exit(1)

    try:
        if args.list_languages:
            list_languages(video_id)
        else:
            fetch_transcript(video_id, args.lang)
    except Exception as e:
        print(json.dumps({"error": str(e), "video_id": video_id}, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
