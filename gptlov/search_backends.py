from __future__ import annotations

import hashlib
import logging
from typing import Dict, Iterable, Iterator, List

try:
    from elasticsearch import Elasticsearch, helpers  # type: ignore
except ImportError as exc:  # pragma: no cover - handled at runtime
    Elasticsearch = None  # type: ignore
    helpers = None  # type: ignore

from .ingest import DocumentChunk

logger = logging.getLogger(__name__)


class ElasticsearchBackend:
    """Lightweight wrapper around Elasticsearch for document indexing and search."""

    def __init__(
        self,
        host: str,
        index: str,
        *,
        username: str | None = None,
        password: str | None = None,
        verify_certs: bool = True,
    ) -> None:
        if Elasticsearch is None:
            raise RuntimeError(
                "The 'elasticsearch' package is required. Install it or switch "
                "GPTLOV_SEARCH_BACKEND back to 'sklearn'."
            )

        auth = None
        if username or password:
            auth = (username or "", password or "")

        self.client = Elasticsearch(hosts=[host], basic_auth=auth, verify_certs=verify_certs)
        self.index = index

    def ensure_index(self, force: bool = False) -> None:
        if force and self.client.indices.exists(index=self.index):
            logger.info("Deleting existing Elasticsearch index '%s'", self.index)
            self.client.indices.delete(index=self.index)

        if not self.client.indices.exists(index=self.index):
            logger.info("Creating Elasticsearch index '%s'", self.index)
            self.client.indices.create(
                index=self.index,
                settings={
                    "analysis": {
                        "analyzer": {
                            "norwegian_default": {
                                "type": "standard",
                                "stopwords": "_norwegian_",
                            }
                        }
                    }
                },
                mappings={
                    "properties": {
                        "title": {"type": "text", "analyzer": "norwegian_default"},
                        "refid": {"type": "keyword"},
                        "source_path": {"type": "keyword"},
                        "content": {"type": "text", "analyzer": "norwegian_default"},
                    }
                },
            )

    def index_documents(self, chunks: Iterable[DocumentChunk], force: bool = False) -> None:
        self.ensure_index(force=force)

        logger.info("Indexing document chunks into Elasticsearch '%s'", self.index)
        actions = self._yield_bulk_actions(chunks)
        helpers.bulk(self.client, actions, chunk_size=500, request_timeout=120)
        logger.info("Elasticsearch index '%s' is ready", self.index)

    def _yield_bulk_actions(self, chunks: Iterable[DocumentChunk]) -> Iterator[Dict[str, object]]:
        for idx, chunk in enumerate(chunks):
            doc_id = hashlib.sha1(f"{chunk.source_path}:{idx}".encode("utf-8")).hexdigest()
            yield {
                "_op_type": "index",
                "_index": self.index,
                "_id": doc_id,
                "title": chunk.title,
                "refid": chunk.refid,
                "source_path": str(chunk.source_path),
                "content": chunk.text,
            }

    def retrieve(self, question: str, top_k: int) -> List[Dict[str, object]]:
        size = max(top_k * 5, top_k + 20, 50)
        logger.debug("Querying Elasticsearch index '%s' with size=%d", self.index, size)
        response = self.client.search(
            index=self.index,
            query={
                "multi_match": {
                    "query": question,
                    "fields": [
                        "title^4",
                        "refid^3",
                        "content",
                    ],
                    "type": "best_fields",
                }
            },
            size=size,
            _source=["title", "refid", "source_path", "content"],
        )

        hits = response.get("hits", {}).get("hits", [])
        results: List[Dict[str, object]] = []
        for hit in hits:
            source = hit.get("_source", {})
            results.append(
                {
                    "score": float(hit.get("_score", 0.0)),
                    "content": source.get("content", ""),
                    "metadata": {
                        "title": source.get("title"),
                        "refid": source.get("refid"),
                        "source_path": source.get("source_path"),
                    },
                }
            )
        return results
