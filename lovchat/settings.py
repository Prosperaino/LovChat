from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    """Runtime configuration for LovChat."""

    raw_data_dir: Path = Path(os.getenv("LOVCHAT_RAW_DATA_DIR", "data/raw"))
    workspace_dir: Path = Path(os.getenv("LOVCHAT_WORKSPACE_DIR", "data/workspace"))
    openai_model: str = os.getenv("LOVCHAT_OPENAI_MODEL", "gpt-4o-mini")
    top_k: int = int(os.getenv("LOVCHAT_TOP_K", "5"))
    archives: tuple[str, ...] = field(default_factory=tuple)

    def ensure_directories(self) -> None:
        self.raw_data_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def __post_init__(self) -> None:
        env_archives = os.getenv("LOVCHAT_ARCHIVES")
        if env_archives:
            parts = [part.strip() for part in env_archives.split(",") if part.strip()]
            self.archives = tuple(parts)
        elif not self.archives:
            self.archives = (
                "gjeldende-lover.tar.bz2",
                "gjeldende-sentrale-forskrifter.tar.bz2",
            )


settings = Settings()
settings.ensure_directories()
