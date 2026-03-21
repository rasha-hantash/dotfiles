from __future__ import annotations

from pathlib import Path

import tomli
from pydantic import BaseModel, Field


class ArxivSourceConfig(BaseModel):
    enabled: bool = True
    categories: list[str] = Field(
        default_factory=lambda: ["cs.CL", "cs.AI", "cs.LG", "stat.ML", "cs.IR"]
    )
    max_results: int = 200
    days_back: int = 1


class HuggingFaceSourceConfig(BaseModel):
    enabled: bool = False


class FreshRssSourceConfig(BaseModel):
    enabled: bool = False
    url: str = ""
    username: str = ""
    password: str = ""
    blog_categories: list[str] = Field(default_factory=list)


class SourcesConfig(BaseModel):
    arxiv: ArxivSourceConfig = Field(default_factory=ArxivSourceConfig)
    huggingface: HuggingFaceSourceConfig = Field(default_factory=HuggingFaceSourceConfig)
    freshrss: FreshRssSourceConfig = Field(default_factory=FreshRssSourceConfig)


class GeneralConfig(BaseModel):
    knowledge_base_repo: str = "~/workspace/personal/explorations/brain-os"
    data_dir: str = "~/.local/share/dork/data"
    log_level: str = "info"


class DorkConfig(BaseModel):
    general: GeneralConfig = Field(default_factory=GeneralConfig)
    sources: SourcesConfig = Field(default_factory=SourcesConfig)

    @property
    def knowledge_base_path(self) -> Path:
        return Path(self.general.knowledge_base_repo).expanduser()

    @property
    def data_path(self) -> Path:
        return Path(self.general.data_dir).expanduser()

    @classmethod
    def load(cls, config_path: Path) -> DorkConfig:
        with open(config_path, "rb") as f:
            raw = tomli.load(f)
        return cls.model_validate(raw)
