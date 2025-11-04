from __future__ import annotations

import copy
import logging
import json
import os
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple

import numpy as np
import bleach
from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity
from markdown_it import MarkdownIt

from .index import VectorStore
from .search_backends import ElasticsearchBackend
from .settings import settings

logger = logging.getLogger(__name__)

_ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS).union(
    {
        "p",
        "pre",
        "code",
        "blockquote",
        "ul",
        "ol",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "br",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
    }
)
_ALLOWED_ATTRS: Dict[str, List[str]] = {
    key: sorted(set(value)) for key, value in bleach.sanitizer.ALLOWED_ATTRIBUTES.items()
}
_ALLOWED_ATTRS["a"] = sorted(set(_ALLOWED_ATTRS.get("a", [])) | {"href", "title", "rel"})
_ALLOWED_ATTRS["th"] = sorted(set(_ALLOWED_ATTRS.get("th", [])) | {"scope", "colspan", "rowspan", "align"})
_ALLOWED_ATTRS["td"] = sorted(set(_ALLOWED_ATTRS.get("td", [])) | {"colspan", "rowspan", "align"})


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
        self._markdown = (
            MarkdownIt("commonmark", {"linkify": True, "breaks": True, "typographer": True})
            .enable("table")
            .enable("strikethrough")
        )
        self._cache_max_entries = max(0, settings.cache_size)
        self._cache: OrderedDict[Tuple[str, int], Dict[str, Any]] = OrderedDict()
        self._cache_lock = threading.RLock()

    def _serialise_contexts(self, context_blocks: List[RetrievalResult]) -> List[Dict[str, Any]]:
        return [
            {
                "score": block.score,
                **block.metadata,
                "content": block.content,
            }
            for block in context_blocks
        ]

    def _iter_chunks(self, text: str, chunk_size: int = 320) -> Iterator[str]:
        pointer = 0
        length = len(text)
        while pointer < length:
            chunk = text[pointer : pointer + chunk_size]
            if chunk:
                yield chunk
            pointer += chunk_size

    def _build_prompt_payload(
        self, question: str, context_blocks: List[RetrievalResult]
    ) -> Tuple[str, List[Dict[str, str]]]:
        context_text: List[str] = []
        for idx, block in enumerate(context_blocks, start=1):
            source_label = (
                block.metadata.get("title")
                or block.metadata.get("refid")
                or block.metadata.get("source_path")
                or f"Kilde {idx}"
            )
            snippet = block.content.strip()
            if len(snippet) > 1800:
                trimmed = snippet[:1800]
                if " " in trimmed:
                    trimmed = trimmed.rsplit(" ", 1)[0]
                if not trimmed:
                    trimmed = snippet[:1800]
                snippet = trimmed.rstrip() + " …"
            context_text.append(f"[{idx}] {source_label}\n{snippet}")
        context_blob = "\n\n".join(context_text)

        instructions = (
            "Du er GPTLov, en juridisk veileder for norske lover og forskrifter. "
            "Gi alltid et tydelig og konkret svar basert på konteksten. "
            "Når informasjonen er begrenset, forklar hva kildene sier og presiser eventuelle mangler "
            "i stedet for å si at du er usikker. "
            "Svar alltid på norsk bokmål og pek på relevante paragrafer når det er mulig. "
            "Presenter svaret i velstrukturert Markdown med en kort fet oppsummering først, tydelige avsnitt, "
            "punktlister eller tabeller der det er nyttig, og egne seksjoner for oppfølging eller forbehold."
        )

        user_message = (
            "Spørsmål:\n"
            f"{question}\n\n"
            "Tilgjengelig kontekst (utdrag nummerert i hakeparenteser):\n"
            f"{context_blob}\n\n"
            "Oppgave: Gi et strukturert svar som forklarer hva loven sier. "
            "Returner alltid svaret i Markdown-format med seksjoner, tydelige avsnitt og relevante punktlister. "
            "Hvis du trekker inn informasjon fra flere utdrag, knytt uttalelsene til nummeret "
            "til kilden i hakeparentes, for eksempel [1]."
        )

        return instructions, [{"role": "user", "content": user_message}]

    def _answer_when_no_contexts(self) -> str:
        return (
            "Jeg fant ingen utdrag som matcher spørsmålet ditt i kildene våre.\n\n"
            "Forslag: prøv å formulere spørsmålet med lovens navn, paragrafnummer eller et "
            "mer konkret tema (for eksempel «§ 14-5 i arbeidsmiljøloven»)."
        )

    def _answer_without_model(self, context_blocks: List[RetrievalResult]) -> str:
        context = "\n\n".join(block.content for block in context_blocks)
        return (
            "No OpenAI API key configured. Here are the most relevant excerpts:\n\n"
            f"{context}"
        )

    def _apply_confidence_fallback(
        self, answer: str, context_blocks: List[RetrievalResult]
    ) -> str:
        if not answer:
            return "Modellen returnerte ikke noe svar denne gangen."

        if "jeg er ikke sikker" not in answer.lower():
            return answer

        fallback_sections: List[str] = []
        for idx, block in enumerate(context_blocks, start=1):
            source_label = (
                block.metadata.get("title")
                or block.metadata.get("refid")
                or block.metadata.get("source_path")
                or f"Kilde {idx}"
            )
            snippet = block.content.strip()
            sentences = re.split(r"(?<=[.!?])\s+", snippet)
            summary = " ".join(sentences[:2]).strip()
            if not summary:
                trimmed = snippet[:260]
                if " " in trimmed:
                    trimmed = trimmed.rsplit(" ", 1)[0]
                if not trimmed:
                    trimmed = snippet[:260]
                summary = trimmed.rstrip() + " …"
            fallback_sections.append(f"[{idx}] {source_label}: {summary}")

        if fallback_sections:
            return "Her er det jeg fant i kildene:\n" + "\n".join(
                f"- {section}" for section in fallback_sections
            )

        return answer

    def _normalise_question(self, question: str) -> str:
        return re.sub(r"\s+", " ", question).strip().lower()

    def _make_cache_key(self, question: str, top_k: int) -> Tuple[str, int]:
        return (self._normalise_question(question), top_k)

    def _get_cached_answer(self, key: Tuple[str, int]) -> Dict[str, Any] | None:
        if self._cache_max_entries <= 0:
            return None

        with self._cache_lock:
            cached = self._cache.get(key)
            if cached is None:
                return None
            self._cache.move_to_end(key)
            return copy.deepcopy(cached)

    def _store_in_cache(self, key: Tuple[str, int], value: Dict[str, Any]) -> None:
        if self._cache_max_entries <= 0:
            return

        with self._cache_lock:
            self._cache[key] = copy.deepcopy(value)
            self._cache.move_to_end(key)
            while len(self._cache) > self._cache_max_entries:
                self._cache.popitem(last=False)

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

    @staticmethod
    def _extract_value(obj: Any, key: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def _extract_response_text(self, response: Any) -> str:
        direct = self._extract_value(response, "output_text")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()

        chunks: list[str] = []
        output_items = self._extract_value(response, "output", []) or []
        for item in output_items:
            item_type = self._extract_value(item, "type")
            if item_type != "message":
                continue
            contents = self._extract_value(item, "content", []) or []
            for content in contents:
                content_type = self._extract_value(content, "type")
                if content_type == "output_text":
                    text = self._extract_value(content, "text", "")
                    if text:
                        chunks.append(str(text))
        return "".join(chunks).strip()

    def _render_markdown(self, text: str) -> str:
        html = self._markdown.render(text)
        sanitized = bleach.clean(
            html,
            tags=_ALLOWED_TAGS,
            attributes=_ALLOWED_ATTRS,
            strip=True,
        )
        return bleach.linkify(sanitized, parse_email=False)

    def generate_answer(self, question: str, context_blocks: List[RetrievalResult]) -> str:
        if not context_blocks:
            return self._answer_when_no_contexts()

        try:
            client = self._ensure_client()
        except RuntimeError:
            return self._answer_without_model(context_blocks)

        instructions, payload = self._build_prompt_payload(question, context_blocks)
        response = client.responses.create(
            model=self.model,
            instructions=instructions,
            input=payload,
        )

        answer = self._extract_response_text(response)
        return self._apply_confidence_fallback(answer, context_blocks)

    def ask(self, question: str, top_k: int | None = None) -> dict[str, Any]:
        effective_top_k = top_k or settings.top_k
        cache_key = self._make_cache_key(question, effective_top_k)
        cached = self._get_cached_answer(cache_key)
        if cached is not None:
            return cached

        context_blocks = self.retrieve(question, top_k=effective_top_k)
        answer = self.generate_answer(question, context_blocks)
        answer_html = self._render_markdown(answer)
        result = {
            "answer": answer,
            "answer_html": answer_html,
            "contexts": self._serialise_contexts(context_blocks),
        }
        self._store_in_cache(cache_key, result)
        return result

    def ask_streaming(
        self, question: str, top_k: int | None = None
    ) -> Iterator[Dict[str, Any]]:
        effective_top_k = top_k or settings.top_k
        cache_key = self._make_cache_key(question, effective_top_k)
        cached = self._get_cached_answer(cache_key)
        if cached is not None:
            yield {
                "type": "status",
                "stage": "cache_hit",
                "message": "Fant et tidligere svar som deles straks.",
            }
            contexts = cached.get("contexts", [])
            if contexts:
                yield {"type": "contexts", "contexts": contexts}
            answer = cached.get("answer", "")
            for chunk in self._iter_chunks(answer):
                yield {"type": "chunk", "text": chunk}
            answer_html = cached.get("answer_html")
            if answer_html:
                yield {"type": "answer_html", "html": answer_html}
            yield {"type": "done"}
            return

        yield {
            "type": "status",
            "stage": "retrieving",
            "message": "Henter relevante kilder fra Lovdata…",
        }
        context_blocks = self.retrieve(question, top_k=effective_top_k)
        serialised_contexts = self._serialise_contexts(context_blocks)
        yield {"type": "contexts", "contexts": serialised_contexts}

        if not context_blocks:
            answer = self._answer_when_no_contexts()
            answer_html = self._render_markdown(answer)
            result = {
                "answer": answer,
                "answer_html": answer_html,
                "contexts": serialised_contexts,
            }
            self._store_in_cache(cache_key, result)
            for chunk in self._iter_chunks(answer):
                yield {"type": "chunk", "text": chunk}
            if answer_html:
                yield {"type": "answer_html", "html": answer_html}
            yield {"type": "done"}
            return

        try:
            client = self._ensure_client()
        except RuntimeError:
            answer = self._answer_without_model(context_blocks)
            answer_html = self._render_markdown(answer)
            result = {
                "answer": answer,
                "answer_html": answer_html,
                "contexts": serialised_contexts,
            }
            self._store_in_cache(cache_key, result)
            for chunk in self._iter_chunks(answer):
                yield {"type": "chunk", "text": chunk}
            if answer_html:
                yield {"type": "answer_html", "html": answer_html}
            yield {"type": "done"}
            return

        yield {
            "type": "status",
            "stage": "generating",
            "message": "Genererer svar med GPTLov…",
        }

        instructions, payload = self._build_prompt_payload(question, context_blocks)
        streamed_chunks: List[str] = []
        final_response: Any | None = None

        try:
            with client.responses.stream(
                model=self.model,
                instructions=instructions,
                input=payload,
            ) as stream:
                for event in stream:
                    event_type = getattr(event, "type", None)
                    if event_type is None:
                        event_type = getattr(event, "event", None)
                    parsed_payload: Dict[str, Any] | None = None
                    if event_type is None and isinstance(event, dict):
                        event_type = event.get("type")
                        parsed_payload = event  # reuse existing dict below
                    if event_type is None and hasattr(event, "data"):
                        raw_data = getattr(event, "data")
                        if isinstance(raw_data, str) and raw_data.strip():
                            try:
                                parsed_payload = json.loads(raw_data)
                                if isinstance(parsed_payload, dict):
                                    event_type = parsed_payload.get("type")
                            except json.JSONDecodeError:
                                parsed_payload = None

                    if event_type == "response.output_text.delta":
                        delta = getattr(event, "delta", None)
                        if delta is None and parsed_payload is not None:
                            delta = parsed_payload.get("delta")
                        if delta is None and isinstance(event, dict):
                            delta = event.get("delta")
                        if delta:
                            text = delta if isinstance(delta, str) else str(delta)
                            streamed_chunks.append(text)
                            yield {"type": "chunk", "text": text}
                    elif event_type == "response.error":
                        error_payload = getattr(event, "error", None)
                        if error_payload is None and parsed_payload is not None:
                            error_payload = parsed_payload.get("error")
                        if error_payload is None and isinstance(event, dict):
                            error_payload = event.get("error")
                        error_message = "Ukjent feil fra modellen."
                        if isinstance(error_payload, dict):
                            error_message = error_payload.get("message", error_message)
                        raise RuntimeError(error_message)
                final_response = stream.get_final_response()
        except Exception as exc:
            logger.warning("Streaming falt tilbake til synkron generering: %s", exc)
            answer = self.generate_answer(question, context_blocks)
            answer_html = self._render_markdown(answer)
            result = {
                "answer": answer,
                "answer_html": answer_html,
                "contexts": serialised_contexts,
            }
            self._store_in_cache(cache_key, result)
            yield {
                "type": "status",
                "stage": "finalising",
                "message": "Svar klart – deler resultatet.",
            }
            for chunk in self._iter_chunks(answer):
                yield {"type": "chunk", "text": chunk}
            if answer_html:
                yield {"type": "answer_html", "html": answer_html}
            yield {"type": "done"}
            return

        answer_text = "".join(streamed_chunks).strip()
        if not answer_text and final_response is not None:
            answer_text = self._extract_response_text(final_response) or ""

        answer = self._apply_confidence_fallback(answer_text, context_blocks)
        answer_html = self._render_markdown(answer)
        result = {
            "answer": answer,
            "answer_html": answer_html,
            "contexts": serialised_contexts,
        }
        self._store_in_cache(cache_key, result)

        yield {
            "type": "status",
            "stage": "finalising",
            "message": "Svar klart – deler resultatet.",
        }
        # The streamed chunks already covered the plain text answer. Share rendered HTML at the end.
        if answer_html:
            yield {"type": "answer_html", "html": answer_html}
        yield {"type": "done"}
