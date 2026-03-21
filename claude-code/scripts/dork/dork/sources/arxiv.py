"""arXiv source via RSS feeds — no external arxiv library needed."""
from __future__ import annotations

import logging
import re
from datetime import date
from time import mktime

import feedparser

from dork.config import ArxivSourceConfig
from dork.models import CandidatePaper

log = logging.getLogger(__name__)

ARXIV_RSS_BASE = "https://rss.arxiv.org/rss"
ARXIV_ID_RE = re.compile(r"abs/(\d{4}\.\d{4,5}(?:v\d+)?)")


class ArxivSource:
    def __init__(self, config: ArxivSourceConfig) -> None:
        self.config = config

    @property
    def name(self) -> str:
        return "arxiv"

    def fetch(self, since: date | None = None) -> list[CandidatePaper]:
        papers: list[CandidatePaper] = []
        seen_ids: set[str] = set()

        for category in self.config.categories:
            feed_url = f"{ARXIV_RSS_BASE}/{category}"
            log.info("fetching arxiv RSS", extra={"category": category, "url": feed_url})

            try:
                feed = feedparser.parse(feed_url)
                if feed.bozo and not feed.entries:
                    log.warning("arxiv RSS parse error", extra={"category": category, "error": str(feed.bozo_exception)})
                    continue

                for entry in feed.entries:
                    paper = self._parse_entry(entry, since, seen_ids)
                    if paper:
                        papers.append(paper)

                log.info("parsed arxiv RSS", extra={"category": category, "entries": len(feed.entries), "new": sum(1 for _ in feed.entries)})

            except Exception as e:
                log.warning("arxiv RSS fetch failed", extra={"category": category, "error": str(e)})

        log.info("fetched arxiv papers total", extra={"count": len(papers)})
        return papers

    def _parse_entry(self, entry: dict, since: date | None, seen_ids: set[str]) -> CandidatePaper | None:
        title = entry.get("title", "").strip()
        link = entry.get("link", "")
        summary = entry.get("summary", "").strip()

        if not title or not link:
            return None

        # Extract arXiv ID
        match = ARXIV_ID_RE.search(link)
        if not match:
            return None
        arxiv_id = match.group(1)

        # Skip duplicates across categories
        base_id = re.sub(r"v\d+$", "", arxiv_id)
        if base_id in seen_ids:
            return None
        seen_ids.add(base_id)

        # Parse date
        pub_date = _parse_date(entry)
        if since and pub_date < since:
            return None

        # Extract authors
        authors = _parse_authors(entry)

        # Extract categories from tags
        categories = [tag.get("term", "") for tag in entry.get("tags", []) if tag.get("term")]

        return CandidatePaper(
            source="arxiv",
            source_id=arxiv_id,
            title=title,
            authors=authors,
            abstract=summary,
            url=link,
            published=pub_date,
            categories=categories,
        )


def _parse_authors(entry: dict) -> list[str]:
    if "authors" in entry:
        return [a.get("name", "") for a in entry["authors"] if a.get("name")]
    if "author" in entry:
        return [entry["author"]]
    # feedparser sometimes puts author in author_detail
    if "author_detail" in entry:
        name = entry["author_detail"].get("name", "")
        if name:
            return [name]
    return []


def _parse_date(entry: dict) -> date:
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                return date.fromtimestamp(mktime(parsed))
            except (ValueError, OverflowError):
                pass
    return date.today()
