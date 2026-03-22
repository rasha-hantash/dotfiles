"""Fetch candidates from all sources, dedup, output JSON."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from dork.config import DorkConfig
from dork.models import CandidatePaper, PipelineRun
from dork.sources.arxiv import ArxivSource
from dork.sources.hf_papers import HuggingFaceSource
from dork.store import PaperStore

log = logging.getLogger(__name__)


def fetch_candidates(config: DorkConfig, max_candidates: int = 30) -> list[dict]:
    """Fetch from all sources, dedup, return serializable candidate list."""
    store = PaperStore(config.data_path)
    last_run = store.last_run_date()

    if last_run:
        log.info("last run: %s", last_run.isoformat())
    else:
        log.info("first run — no previous run date")

    candidates: list[CandidatePaper] = []

    # Fetch from each enabled source (graceful degradation)
    sources_config = [
        ("arxiv", config.sources.arxiv, lambda c: ArxivSource(c)),
        ("huggingface", config.sources.huggingface, lambda c: HuggingFaceSource(c)),
    ]

    for name, src_config, factory in sources_config:
        if not src_config.enabled:
            log.info("skipping %s (disabled)", name)
            continue
        try:
            source = factory(src_config)
            fetched = source.fetch(since=last_run)
            candidates.extend(fetched)
            log.info("source %s: fetched %d candidates", name, len(fetched))
        except Exception as e:
            log.warning("source %s: fetch FAILED — %s", name, e)

    # FreshRSS (lazy import — may not be configured)
    if config.sources.freshrss.enabled:
        try:
            from dork.sources.freshrss import FreshRssSource
            source = FreshRssSource(config.sources.freshrss)
            fetched = source.fetch(since=last_run)
            candidates.extend(fetched)
            log.info("source freshrss: fetched %d candidates", len(fetched))
        except Exception as e:
            log.warning("source freshrss: fetch FAILED — %s", e)
    else:
        log.info("skipping freshrss (disabled)")

    log.info("total fetched from all sources: %d", len(candidates))

    # Cross-source dedup
    seen: set[str] = set()
    unique: list[CandidatePaper] = []
    dupes_cross = 0
    for c in candidates:
        if c.dedup_key not in seen:
            seen.add(c.dedup_key)
            unique.append(c)
        else:
            dupes_cross += 1

    if dupes_cross:
        log.info("cross-source dedup removed %d duplicates", dupes_cross)

    # Dedup against store (previously seen papers)
    new: list[CandidatePaper] = []
    already_seen = 0
    for c in unique:
        prev = store.seen_version(c.dedup_key)
        if prev is None:
            new.append(c)
        elif c.arxiv_version > prev:
            new.append(c)
            log.info("version update: %s v%d -> v%d", c.source_id, prev, c.arxiv_version)
        else:
            already_seen += 1

    log.info("dedup result: %d new, %d already seen, %d cross-source dupes", len(new), already_seen, dupes_cross)

    if len(new) > max_candidates:
        log.info("capping output from %d to %d candidates", len(new), max_candidates)
        new = new[:max_candidates]

    # Record run
    run = PipelineRun(
        run_id=uuid.uuid4().hex[:12],
        started_at=datetime.now(),
        sources_fetched=len(candidates),
        candidates_after_dedup=len(new),
    )
    run.finished_at = datetime.now()
    store.append_run(run)

    # Serialize and record each candidate as seen
    result = []
    for c in new:
        d = _serialize(c)
        store.record_seen(d)
        result.append(d)

    log.info("output: %d candidates written", len(result))
    return result


def _serialize(c: CandidatePaper) -> dict:
    return {
        "source": c.source,
        "source_id": c.source_id,
        "title": c.title,
        "authors": c.authors,
        "abstract": c.abstract,
        "url": c.url,
        "published": c.published.isoformat() if c.published else None,
        "categories": c.categories,
        "content_type": c.content_type.value if c.content_type else "paper",
    }
