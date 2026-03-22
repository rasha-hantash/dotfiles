from __future__ import annotations

import re
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field

ARXIV_URL_PATTERN = re.compile(r"arxiv\.org/abs/(\d{4}\.\d{4,5})")
ARXIV_ID_PATTERN = re.compile(r"^(\d{4}\.\d{4,5})")
ARXIV_VERSION_PATTERN = re.compile(r"v(\d+)")


def extract_arxiv_id(url: str, source: str, source_id: str) -> str | None:
    if source == "arxiv":
        match = ARXIV_ID_PATTERN.match(source_id)
        if match:
            return match.group(1)
    match = ARXIV_URL_PATTERN.search(url)
    if match:
        return match.group(1)
    return None


def extract_arxiv_version(source_id: str) -> int:
    match = ARXIV_VERSION_PATTERN.search(source_id)
    if match:
        return int(match.group(1))
    return 1


class ContentType(str, Enum):
    PAPER = "paper"
    BLOG = "blog"


class CandidatePaper(BaseModel):
    source: str
    source_id: str
    title: str
    authors: list[str]
    abstract: str
    url: str
    published: date
    categories: list[str] = Field(default_factory=list)
    content_type: ContentType = ContentType.PAPER

    @property
    def arxiv_id(self) -> str | None:
        return extract_arxiv_id(self.url, self.source, self.source_id)

    @property
    def arxiv_version(self) -> int:
        if self.source == "arxiv":
            return extract_arxiv_version(self.source_id)
        return 1

    @property
    def dedup_key(self) -> str:
        aid = self.arxiv_id
        if aid:
            return f"arxiv:{aid}"
        return f"{self.source}:{self.source_id}"


class PipelineRun(BaseModel):
    run_id: str
    started_at: datetime
    finished_at: datetime | None = None
    sources_fetched: int = 0
    candidates_after_dedup: int = 0
