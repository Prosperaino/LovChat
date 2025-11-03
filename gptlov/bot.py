from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity

from .index import VectorStore
from .search_backends import ElasticsearchBackend
from .settings import settings


@dataclass
class RetrievalResult:
    score: float
    content: str
    metadata: Dict[str, Any]


class GPTLovBot:
    """Simple retrieval-augmented chatbot for Lovdata content."""

    _LAW_NAME_PATTERN = re.compile(r"\b([\wÀ-ÖØ-öø-ÿ-]*(?:loven|forskriften))\b", re.IGNORECASE)
    _PARAGRAPH_PATTERN = re.compile(r"§\s*\d+[a-zA-Z]?(?:-\d+[a-zA-Z]?)?")
    _CHAPTER_PATTERN = re.compile(r"kapittel\s+([\dIVX]+[a-zA-Z]?)", re.IGNORECASE)

    def __init__(self, store_path: str | os.PathLike[str] | None, model: str | None = None):
        self.mode = settings.search_backend
        if self.mode == "elasticsearch":
            self.store: VectorStore | None = None
            self._es_backend = ElasticsearchBackend(
                host=settings.es_host or "",
                index=settings.es_index,
                username=settings.es_username,
                password=settings.es_password,
                verify_certs=settings.es_verify_certs,
            )
        else:
            if store_path is None:
                raise RuntimeError("Vector store path is required when using the sklearn backend.")
            self.store = VectorStore.load(Path(store_path))
            self._es_backend = None
        self.model = model or settings.openai_model
        self._client: OpenAI | None = None

    def _ensure_client(self) -> OpenAI:
        if self._client:
            return self._client

        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set. Cannot generate model responses.")

        if base_url:
            self._client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            self._client = OpenAI(api_key=api_key)
        return self._client

    def retrieve(self, question: str, top_k: int | None = None) -> List[RetrievalResult]:
        top_k = top_k or settings.top_k
        law_terms, paragraph_terms, chapter_terms = self._extract_query_hints(question)

        if self.mode == "elasticsearch":
            return self._retrieve_elasticsearch(
                question,
                top_k,
                law_terms=law_terms,
                paragraph_terms=paragraph_terms,
                chapter_terms=chapter_terms,
            )

        if not self.store:
            raise RuntimeError("Vector store not initialised.")

        query_vector = self.store.vectorizer.transform([question])
        scores = cosine_similarity(self.store.matrix, query_vector).ravel()

        candidate_count = min(len(scores), max(top_k * 8, top_k + 80, 80))
        candidate_indices = np.argsort(scores)[::-1][:candidate_count]

        if law_terms:
            additional_indices = self._find_metadata_matches(law_terms, scores)
            if additional_indices:
                combined = np.concatenate(
                    [candidate_indices, np.array(additional_indices, dtype=int)]
                )
                unique_indices = np.unique(combined)
                candidate_indices = np.array(
                    sorted(unique_indices, key=lambda idx: scores[idx], reverse=True),
                    dtype=int,
                )
        candidates: List[RetrievalResult] = []
        for idx in candidate_indices:
            metadata = self.store.metadata[idx]
            candidates.append(
                RetrievalResult(
                    score=float(scores[idx]),
                    content=metadata["content"],
                    metadata={k: v for k, v in metadata.items() if k != "content"},
                )
            )
        reranked = self._rerank_candidates(
            law_terms=law_terms,
            paragraph_terms=paragraph_terms,
            chapter_terms=chapter_terms,
            candidates=candidates,
        )
        return reranked[:top_k]

    def _retrieve_elasticsearch(
        self,
        question: str,
        top_k: int,
        *,
        law_terms: set[str],
        paragraph_terms: set[str],
        chapter_terms: set[str],
    ) -> List[RetrievalResult]:
        if not self._es_backend:
            raise RuntimeError("Elasticsearch backend is not configured.")
        raw_results = self._es_backend.retrieve(question, top_k)
        candidates = [
            RetrievalResult(
                score=float(entry.get("score", 0.0)),
                content=str(entry.get("content", "")),
                metadata=dict(entry.get("metadata", {})),
            )
            for entry in raw_results
        ]
        reranked = self._rerank_candidates(
            law_terms=law_terms,
            paragraph_terms=paragraph_terms,
            chapter_terms=chapter_terms,
            candidates=candidates,
        )
        return reranked[:top_k]

    def _extract_query_hints(
        self, question: str
    ) -> tuple[set[str], set[str], set[str]]:
        law_terms = {
            match.group(1).strip().lower()
            for match in self._LAW_NAME_PATTERN.finditer(question)
        }
        paragraph_terms = {
            re.sub(r"\s+", "", match.lower())
            for match in self._PARAGRAPH_PATTERN.findall(question)
        }
        chapter_terms = {
            match.group(1).strip().lower()
            for match in self._CHAPTER_PATTERN.finditer(question)
        }
        return law_terms, paragraph_terms, chapter_terms

    def _find_metadata_matches(self, law_terms: set[str], scores: np.ndarray) -> list[int]:
        if not self.store:
            return []
        if not law_terms:
            return []

        match_priorities: dict[int, tuple[int, float]] = {}
        for idx, metadata in enumerate(self.store.metadata):
            title = (metadata.get("title") or "").lower()
            path = (metadata.get("source_path") or "").lower()
            refid = (metadata.get("refid") or "").lower()
            normalized_title = title.replace(" ", "")
            for term in law_terms:
                normalized_term = term.replace(" ", "")
                if (
                    term in title
                    or term in path
                    or term in refid
                    or (normalized_term and normalized_term in normalized_title)
                ):
                    priority = self._classify_match_priority(metadata, term)
                    current = match_priorities.get(idx)
                    if current is None or priority < current[0]:
                        match_priorities[idx] = (priority, float(scores[idx]))
                    break

        ranked = sorted(
            match_priorities.items(),
            key=lambda item: (item[1][0], -item[1][1]),
        )
        return [idx for idx, _ in ranked[:30]]

    def _classify_match_priority(self, metadata: Dict[str, Any], term: str) -> int:
        """Assign priority to a metadata match (lower is better)."""

        title = (metadata.get("title") or "").lower()
        path = (metadata.get("source_path") or "").lower()

        is_primary_collection = "gjeldende-lover" in path
        if not is_primary_collection:
            return 2

        normalized_term = term.replace(" ", "")
        normalized_title = title.replace(" ", "")

        if (
            title.startswith("lov om")
            and "endring" not in title[:50]
            and "endrings" not in title[:50]
            and (term in title or normalized_term in normalized_title)
        ):
            return 0

        return 1

    def _rerank_candidates(
        self,
        *,
        law_terms: set[str],
        paragraph_terms: set[str],
        chapter_terms: set[str],
        candidates: List[RetrievalResult],
    ) -> List[RetrievalResult]:
        """Apply simple heuristics to favour chunks that directly match the query metadata."""

        adjusted: list[tuple[float, RetrievalResult]] = []
        for result in candidates:
            title = (result.metadata.get("title") or "").lower()
            path = (result.metadata.get("source_path") or "").lower()
            refid = (result.metadata.get("refid") or "").lower()
            content = result.content.lower()
            normalized_content = re.sub(r"\s+", "", content)

            boost = 0.0

            if law_terms:
                normalized_title = title.replace(" ", "")
                best_priority: int | None = None
                match_found = False
                for term in law_terms:
                    term_normalized = term.replace(" ", "")
                    matches = (
                        term in title
                        or term in path
                        or term in refid
                        or (term_normalized and term_normalized in normalized_title)
                    )
                    if matches:
                        match_found = True
                        priority = self._classify_match_priority(result.metadata, term)
                        if best_priority is None or priority < best_priority:
                            best_priority = priority
                        if best_priority == 0:
                            break
                if match_found:
                    if best_priority == 0:
                        boost += 0.45
                    elif best_priority == 1:
                        boost += 0.28
                    else:
                        boost += 0.18
                elif "gjeldende-lover" in path:
                    boost += 0.05
            elif "gjeldende-lover" in path:
                boost += 0.05

            if paragraph_terms:
                for term in paragraph_terms:
                    if term and term in normalized_content:
                        boost += 0.12
                        break

            if chapter_terms:
                for term in chapter_terms:
                    if term and f"kapittel {term}" in content:
                        boost += 0.08
                        break

            adjusted_score = result.score + boost
            adjusted.append((adjusted_score, result))

        adjusted.sort(key=lambda item: item[0], reverse=True)
        return [
            RetrievalResult(
                score=score,
                content=item.content,
                metadata=item.metadata,
            )
            for score, item in adjusted
        ]

    def generate_answer(self, question: str, context_blocks: List[RetrievalResult]) -> str:
        try:
            client = self._ensure_client()
        except RuntimeError as exc:
            context = "\n\n".join(block.content for block in context_blocks)
            return (
                "No OpenAI API key configured. Here are the most relevant excerpts:\n\n"
                f"{context}"
            )

        context_text = "\n\n".join(
            f"Kilde: {block.metadata.get('title') or block.metadata.get('refid') or block.metadata.get('source_path')}\n{block.content}"
            for block in context_blocks
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "Du er GPTLov, en hjelpsom assistent som svarer på spørsmål om norske lover og "
                    "sentrale forskrifter. Oppgi kun informasjon hentet fra konteksten. Hvis svaret "
                    "ikke finnes i utdragene, si at du ikke er sikker."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Kontekst:\n" + context_text + "\n\n" + f"Spørsmål: {question}\n" + "Svar på norsk."
                ),
            },
        ]

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
        )

        return response.choices[0].message.content.strip()

    def ask(self, question: str, top_k: int | None = None) -> dict[str, Any]:
        context_blocks = self.retrieve(question, top_k=top_k)
        answer = self.generate_answer(question, context_blocks)
        return {
            "answer": answer,
            "contexts": [
                {
                    "score": block.score,
                    **block.metadata,
                    "content": block.content,
                }
                for block in context_blocks
            ],
        }
