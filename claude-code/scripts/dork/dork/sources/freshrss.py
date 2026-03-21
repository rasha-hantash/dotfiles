"""FreshRSS source adapter — fetches unread items via the GReader API."""

from __future__ import annotations

import logging
import re
from datetime import date
from html.parser import HTMLParser
from io import StringIO

import httpx

from dork.config import FreshRssSourceConfig
from dork.models import CandidatePaper, ContentType

log = logging.getLogger(__name__)

GREADER_LOGIN_PATH = "/api/greader.php/accounts/ClientLogin"
GREADER_STREAM_PATH = "/api/greader.php/reader/api/0/stream/contents/reading-list"
GREADER_EDIT_TAG_PATH = "/api/greader.php/reader/api/0/edit-tag"
GREADER_TOKEN_PATH = "/api/greader.php/reader/api/0/token"

ARXIV_URL_RE = re.compile(r"arxiv\.org/abs/(\d{4}\.\d{4,5})")


class FreshRssSource:
    def __init__(self, config: FreshRssSourceConfig) -> None:
        self.config = config
        self._auth_token: str | None = None
        self._edit_token: str | None = None

    @property
    def name(self) -> str:
        return "freshrss"

    def fetch(self, since: date | None = None) -> list[CandidatePaper]:
        if not self.config.url:
            log.warning("freshrss url not configured")
            return []

        try:
            self._authenticate()
            items = self._fetch_unread()
        except Exception as e:
            log.error("freshrss fetch failed", extra={"error": str(e)})
            return []

        candidates: list[CandidatePaper] = []
        processed_ids: list[str] = []

        for item in items:
            pub_date = _parse_timestamp(item.get("published", 0))
            if since and pub_date < since:
                continue

            title = item.get("title", "")
            link = _extract_link(item)
            if not title or not link:
                continue

            content_type = self._classify_content_type(item)

            content_html = item.get("summary", {}).get("content", "")
            abstract = _html_to_text(content_html)

            arxiv_match = ARXIV_URL_RE.search(link)
            source_id = arxiv_match.group(1) if arxiv_match else link

            candidate = CandidatePaper(
                source="freshrss",
                source_id=source_id,
                title=title,
                authors=_extract_authors(item),
                abstract=abstract,
                url=link,
                published=pub_date,
                content_type=content_type,
            )
            candidates.append(candidate)

            item_id = item.get("id", "")
            if item_id:
                processed_ids.append(item_id)

        if processed_ids:
            self._mark_as_read(processed_ids)

        log.info("fetched freshrss items", extra={"count": len(candidates)})
        return candidates

    def _authenticate(self) -> None:
        url = f"{self.config.url}{GREADER_LOGIN_PATH}"
        response = httpx.post(
            url,
            data={
                "Email": self.config.username,
                "Passwd": self.config.password,
            },
            timeout=15,
        )
        response.raise_for_status()

        for line in response.text.splitlines():
            if line.startswith("Auth="):
                self._auth_token = line[5:]
                return

        raise ValueError("No Auth token in ClientLogin response")

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"GoogleLogin auth={self._auth_token}"}

    def _fetch_unread(self) -> list[dict]:
        url = f"{self.config.url}{GREADER_STREAM_PATH}"
        response = httpx.get(
            url,
            params={
                "output": "json",
                "n": 200,
                "xt": "user/-/state/com.google/read",
            },
            headers=self._auth_headers(),
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("items", [])

    def _classify_content_type(self, item: dict) -> ContentType:
        categories = item.get("categories", [])
        cat_labels = [c.split("/")[-1].lower() for c in categories if isinstance(c, str)]

        for label in cat_labels:
            if label in self.config.blog_categories:
                return ContentType.BLOG

        link = _extract_link(item)
        if link and ARXIV_URL_RE.search(link):
            return ContentType.PAPER

        return ContentType.BLOG

    def _get_edit_token(self) -> str:
        if self._edit_token:
            return self._edit_token
        url = f"{self.config.url}{GREADER_TOKEN_PATH}"
        response = httpx.get(url, headers=self._auth_headers(), timeout=15)
        response.raise_for_status()
        self._edit_token = response.text.strip()
        return self._edit_token

    def _mark_as_read(self, item_ids: list[str]) -> None:
        try:
            token = self._get_edit_token()
            url = f"{self.config.url}{GREADER_EDIT_TAG_PATH}"
            response = httpx.post(
                url,
                data={
                    "a": "user/-/state/com.google/read",
                    "T": token,
                    "i": item_ids,
                },
                headers=self._auth_headers(),
                timeout=15,
            )
            response.raise_for_status()
            log.info("marked items as read", extra={"count": len(item_ids)})
        except Exception as e:
            log.warning("failed to mark items as read", extra={"error": str(e)})


def _extract_link(item: dict) -> str:
    for link_list in (item.get("canonical", []), item.get("alternate", [])):
        if link_list and isinstance(link_list, list):
            href = link_list[0].get("href", "")
            if href:
                return href
    return item.get("origin", {}).get("htmlUrl", "")


def _extract_authors(item: dict) -> list[str]:
    author = item.get("author", "")
    if author:
        return [author]
    origin = item.get("origin", {})
    title = origin.get("title", "")
    if title:
        return [title]
    return []


def _parse_timestamp(ts: int) -> date:
    if ts <= 0:
        return date.today()
    from datetime import datetime
    return datetime.fromtimestamp(ts).date()


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._result = StringIO()
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip = False
        if tag in ("p", "br", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._result.write("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._result.write(data)

    def get_text(self) -> str:
        return self._result.getvalue().strip()


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    return extractor.get_text()
