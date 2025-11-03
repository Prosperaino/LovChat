from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import httpx

from .ingest import build_chunks, extract_archives
from .index import build_vector_store
from .search_backends import ElasticsearchBackend
from .settings import settings

logger = logging.getLogger(__name__)

LOVDATA_BASE_URL = "https://api.lovdata.no/v1/publicData/get/"
DEFAULT_ARCHIVES = (
    "gjeldende-lover.tar.bz2",
    "gjeldende-sentrale-forskrifter.tar.bz2",
)


def download_archive(filename: str, dest_dir: Path, timeout: float = 30.0) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    destination = dest_dir / filename
    if destination.exists():
        logger.info("Archive %s already present", filename)
        return destination

    url = f"{LOVDATA_BASE_URL}{filename}"
    logger.info("Downloading %s", url)
    with httpx.stream("GET", url, timeout=timeout) as response:
        response.raise_for_status()
        with destination.open("wb") as handle:
            for chunk in response.iter_bytes():
                handle.write(chunk)

    logger.info("Saved archive to %s", destination)
    return destination


def ensure_archives(filenames: Iterable[str] | None = None, force: bool = False) -> list[Path]:
    if filenames is None:
        filenames = settings.archives or DEFAULT_ARCHIVES
    raw_dir = settings.raw_data_dir
    paths: list[Path] = []
    for name in filenames:
        destination = raw_dir / name
        if force and destination.exists():
            destination.unlink()
        paths.append(download_archive(name, raw_dir))
    return paths


def ensure_vector_store(force: bool = False) -> Path | None:
    if settings.search_backend == "elasticsearch":
        ensure_archives(force=force)
        workspace_dir = settings.workspace_dir
        extracted_root = workspace_dir / "extracted"
        extracted_dirs = extract_archives(settings.raw_data_dir, extracted_root, force=force)
        chunks = build_chunks(extracted_dirs)
        logger.info("Built %d document chunks for Elasticsearch", len(chunks))

        backend = ElasticsearchBackend(
            host=settings.es_host or "",
            index=settings.es_index,
            username=settings.es_username,
            password=settings.es_password,
            verify_certs=settings.es_verify_certs,
        )
        backend.index_documents(chunks, force=force)
        return None

    workspace_dir = settings.workspace_dir
    store_path = workspace_dir / "vector_store.pkl"
    if store_path.exists() and not force:
        logger.info("Vector store already exists at %s", store_path)
        return store_path

    ensure_archives(force=force)
    extracted_root = workspace_dir / "extracted"
    extracted_dirs = extract_archives(settings.raw_data_dir, extracted_root, force=force)
    chunks = build_chunks(extracted_dirs)
    logger.info("Built %d document chunks", len(chunks))
    path = build_vector_store(chunks, workspace_dir)
    logger.info("Vector store written to %s", path)
    return path
