from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from dork.models import PipelineRun, extract_arxiv_id, extract_arxiv_version


class PaperStore:
    def __init__(self, data_dir: Path) -> None:
        self.papers_path = data_dir / "papers.jsonl"
        self.runs_path = data_dir / "runs.jsonl"
        self.papers_path.parent.mkdir(parents=True, exist_ok=True)
        self._seen_versions: dict[str, int] | None = None

    def _load_seen_versions(self) -> dict[str, int]:
        versions: dict[str, int] = {}
        if not self.papers_path.exists():
            return versions
        with open(self.papers_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                source = record["source"]
                source_id = record["source_id"]
                url = record.get("url", "")
                arxiv_id = extract_arxiv_id(url, source, source_id)
                if arxiv_id:
                    key = f"arxiv:{arxiv_id}"
                    version = extract_arxiv_version(source_id)
                else:
                    key = f"{source}:{source_id}"
                    version = 1
                versions[key] = max(versions.get(key, 0), version)
        return versions

    @property
    def seen_versions(self) -> dict[str, int]:
        if self._seen_versions is None:
            self._seen_versions = self._load_seen_versions()
        return self._seen_versions

    def seen_version(self, dedup_key: str) -> int | None:
        return self.seen_versions.get(dedup_key)

    def record_seen(self, candidate_dict: dict) -> None:
        """Record a candidate as seen for future dedup."""
        with open(self.papers_path, "a") as f:
            f.write(json.dumps(candidate_dict) + "\n")
        source = candidate_dict["source"]
        source_id = candidate_dict["source_id"]
        url = candidate_dict.get("url", "")
        arxiv_id = extract_arxiv_id(url, source, source_id)
        if arxiv_id:
            key = f"arxiv:{arxiv_id}"
            version = extract_arxiv_version(source_id)
        else:
            key = f"{source}:{source_id}"
            version = 1
        self.seen_versions[key] = max(self.seen_versions.get(key, 0), version)

    def last_run_date(self) -> date | None:
        if not self.runs_path.exists():
            return None
        last_started: datetime | None = None
        with open(self.runs_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                started = datetime.fromisoformat(record["started_at"])
                if last_started is None or started > last_started:
                    last_started = started
        return last_started.date() if last_started else None

    def append_run(self, run: PipelineRun) -> None:
        with open(self.runs_path, "a") as f:
            f.write(run.model_dump_json() + "\n")
