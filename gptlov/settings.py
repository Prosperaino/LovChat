from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _getenv(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value is not None:
            return value
    return default


@dataclass
class Settings:
    """Runtime configuration for GPTLov."""

    raw_data_dir: Path = Path(_getenv("GPTLOV_RAW_DATA_DIR", "LOVCHAT_RAW_DATA_DIR") or "data/raw")
    workspace_dir: Path = Path(
        _getenv("GPTLOV_WORKSPACE_DIR", "LOVCHAT_WORKSPACE_DIR") or "data/workspace"
    )
    openai_model: str = _getenv("GPTLOV_OPENAI_MODEL", "LOVCHAT_OPENAI_MODEL") or "gpt-4o-mini"
    top_k: int = int(_getenv("GPTLOV_TOP_K", "LOVCHAT_TOP_K") or "5")
    search_backend: str = (_getenv("GPTLOV_SEARCH_BACKEND") or "sklearn").lower()
    es_host: str | None = _getenv("GPTLOV_ES_HOST", "ELASTICSEARCH_URL")
    es_index: str = _getenv("GPTLOV_ES_INDEX") or "gptlov"
    es_username: str | None = _getenv("GPTLOV_ES_USERNAME")
    es_password: str | None = _getenv("GPTLOV_ES_PASSWORD")
    es_verify_certs: bool = (_getenv("GPTLOV_ES_VERIFY_CERTS") or "true").lower() not in {
        "0",
        "false",
        "no",
    }
    archives: tuple[str, ...] = field(default_factory=tuple)

    def ensure_directories(self) -> None:
        self.raw_data_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def __post_init__(self) -> None:
        env_archives = _getenv("GPTLOV_ARCHIVES", "LOVCHAT_ARCHIVES")
        if env_archives:
            parts = [part.strip() for part in env_archives.split(",") if part.strip()]
            self.archives = tuple(parts)
        elif not self.archives:
            self.archives = (
                "gjeldende-lover.tar.bz2",
                "gjeldende-sentrale-forskrifter.tar.bz2",
            )

        if self.search_backend not in {"sklearn", "elasticsearch"}:
            raise ValueError(
                f"Unsupported GPTLOV_SEARCH_BACKEND='{self.search_backend}'. "
                "Use 'sklearn' or 'elasticsearch'."
            )

        if self.search_backend == "elasticsearch" and not self.es_host:
            raise ValueError(
                "GPTLOV_ES_HOST/ELASTICSEARCH_URL must be set when using the Elasticsearch backend."
            )


settings = Settings()
settings.ensure_directories()
