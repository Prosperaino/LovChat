from __future__ import annotations
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List

from bs4 import BeautifulSoup
from tqdm import tqdm


@dataclass
class DocumentChunk:
    """Represents a chunk of text from a legal document."""

    text: str
    source_path: Path
    title: str | None = None
    refid: str | None = None


def extract_archives(raw_dir: Path, extract_dir: Path, force: bool = False) -> list[Path]:
    """Extract every tar archive in ``raw_dir`` into ``extract_dir``.

    Parameters
    ----------
    raw_dir: Path
        Directory containing the downloaded Lovdata archives (tar/tar.bz2 files).
    extract_dir: Path
        Directory where the archives should be expanded.
    force: bool
        If ``True`` re-extract archives even if a directory already exists.

    Returns
    -------
    list[Path]
        Paths to the extracted archive root folders.
    """

    extract_dir.mkdir(parents=True, exist_ok=True)
    extracted_roots: list[Path] = []

    for archive in sorted(raw_dir.glob("*.tar*")):
        name = archive.name
        target_name = name.split(".tar", 1)[0]
        target_root = extract_dir / target_name
        if target_root.exists() and not force:
            extracted_roots.append(target_root)
            continue

        if target_root.exists():
            import shutil

            shutil.rmtree(target_root)

        target_root.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive, mode="r:*") as tar:
            tar.extractall(path=target_root)
        extracted_roots.append(target_root)

    return extracted_roots


def iter_document_paths(extracted_dirs: Iterable[Path]) -> Iterator[Path]:
    """Yield all XML/HTML files contained under the extracted directories."""

    extensions = {".xml", ".html", ".htm"}
    for directory in extracted_dirs:
        for path in directory.rglob("*"):
            if path.suffix.lower() in extensions and path.is_file():
                yield path


def parse_document(path: Path) -> tuple[str, str | None, str | None]:
    """Parse a structured Lovdata document and return text plus metadata."""

    html = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")

    title = None
    refid = None

    title_node = soup.find("dd", class_="title") or soup.find("title")
    if title_node:
        title = title_node.get_text(strip=True)

    refid_node = soup.find("dd", class_="refid")
    if refid_node:
        refid = refid_node.get_text(strip=True)

    body = soup.find("main") or soup.body
    if not body:
        text = soup.get_text(separator="\n", strip=True)
    else:
        text = body.get_text(separator="\n", strip=True)

    return text, title, refid


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200) -> List[str]:
    """Split text into overlapping chunks based on token-ish word counts."""

    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words))
        if end >= len(words):
            break
        start = max(end - overlap, start + 1)
    return chunks


def build_chunks(extracted_dirs: Iterable[Path], chunk_size: int = 1200, overlap: int = 200) -> list[DocumentChunk]:
    """Create document chunks from extracted archives."""

    paths = list(iter_document_paths(extracted_dirs))
    chunks: list[DocumentChunk] = []

    for path in tqdm(paths, desc="Parsing documents"):
        text, title, refid = parse_document(path)
        for chunk in chunk_text(text, chunk_size=chunk_size, overlap=overlap):
            chunks.append(DocumentChunk(text=chunk, source_path=path, title=title, refid=refid))

    return chunks
