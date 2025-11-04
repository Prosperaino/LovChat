from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from flask import current_app, stream_with_context

from gptlov.bot import GPTLovBot
from gptlov.data_pipeline import ensure_vector_store

SESSION_EVENT = "session_id"
SOURCE_EVENT = "source"
DONE_EVENT = "done"
ANSWER_HTML_EVENT = "answer_html"
STATUS_EVENT = "status"
SOURCE_LIST_EVENT = "source_list"
CONTEXT_EVENT = "contexts"
CHUNK_EVENT = "chunk"


def _build_payload(event_type: str, payload: object | None = None) -> str:
    lines = [f"event: {event_type}"]
    data = json.dumps(payload, ensure_ascii=False)
    lines.append(f"data: {data}")
    return "\n".join(lines) + "\n\n"

_bot: GPTLovBot | None = None
_lock = threading.Lock()
_fallback_logger = logging.getLogger("gptlov.labs_app")


def _get_logger():
    try:
        return current_app.logger
    except RuntimeError:  # pragma: no cover - only triggered outside request context
        return _fallback_logger


def _initialise_bot() -> GPTLovBot:
    global _bot
    if _bot is not None:
        return _bot

    with _lock:
        if _bot is None:
            logger = _get_logger()
            logger.info("Initialising GPTLov bot for labs app")
            store_path = ensure_vector_store()
            _bot = GPTLovBot(store_path=store_path)
    return _bot


def _safe_source_name(entry: dict[str, object]) -> str:
    title = (entry.get("title") or "").strip() if isinstance(entry.get("title"), str) else ""
    refid = (entry.get("refid") or "").strip() if isinstance(entry.get("refid"), str) else ""
    source_path = (entry.get("source_path") or "").strip() if isinstance(entry.get("source_path"), str) else ""
    if title:
        return title
    if refid:
        return refid
    if source_path:
        return Path(source_path).stem
    return "Kilde"


@stream_with_context
def ask_question(question: str, session_id: str):
    try:
        bot = _initialise_bot()
    except Exception as exc:  # pragma: no cover - defensive path
        logger = _get_logger()
        logger.exception("Failed to prepare GPTLov bot")
        error_message = "Kunne ikke starte søkemotoren. Prøv igjen senere."
        yield "event: FatalError\n"
        yield f"data: {error_message}\n\n"
        return

    logger = _get_logger()
    logger.info("[labs_app] Handling question for session %s", session_id)
    yield _build_payload(SESSION_EVENT, session_id)

    sent_source_list = False
    unique_sources: list[str] = []

    try:
        for event in bot.ask_streaming(question):
            event_type = event.get("type") if isinstance(event, dict) else None

            if event_type == "status":
                message = str(event.get("message") or "").strip()
                if message:
                    yield _build_payload(STATUS_EVENT, message)
            elif event_type == "contexts":
                contexts = event.get("contexts")
                if isinstance(contexts, list):
                    seen: set[str] = set()
                    for entry in contexts:
                        if not isinstance(entry, dict):
                            continue
                        name = _safe_source_name(entry)
                        payload = {
                            "name": name,
                            "page_content": entry.get("content", ""),
                            "title": entry.get("title"),
                            "refid": entry.get("refid"),
                            "score": entry.get("score"),
                            "source_path": entry.get("source_path"),
                        }
                        yield _build_payload(SOURCE_EVENT, payload)
                        if name and name not in seen:
                            seen.add(name)
                            unique_sources.append(name)
                    if unique_sources and not sent_source_list:
                        yield _build_payload(SOURCE_LIST_EVENT, {"names": unique_sources})
                        sent_source_list = True
                    yield _build_payload(CONTEXT_EVENT, contexts)
            elif event_type == "chunk":
                chunk = str(event.get("text") or "")
                if chunk:
                    yield _build_payload(CHUNK_EVENT, chunk)
            elif event_type == "answer_html":
                html_text = str(event.get("html") or "")
                if html_text:
                    yield _build_payload(ANSWER_HTML_EVENT, html_text)
            elif event_type == "done":
                yield _build_payload(DONE_EVENT, True)
                break
    except Exception as exc:  # pragma: no cover - relies on runtime failures
        logger.exception("GPTLov bot failed to stream answer")
        error_message = "Beklager, jeg klarte ikke å finne svar denne gangen."
        yield "event: FatalError\n"
        yield f"data: {error_message}\n\n"
        return
