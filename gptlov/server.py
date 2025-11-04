from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .bot import GPTLovBot
from .data_pipeline import ensure_vector_store
from .settings import settings

logger = logging.getLogger(__name__)

app = FastAPI(title="GPTLov", version="0.1.0")

_bot: Optional[GPTLovBot] = None
_base_dir = Path(__file__).resolve().parent
_frontend_dir = _base_dir.parent / "labs_app" / "frontend" / "build"
_frontend_static_dir = _frontend_dir / "static"
_frontend_index_path = _frontend_dir / "index.html"
_legacy_static_dir = _base_dir / "static"
_template_path = _base_dir / "templates" / "index.html"

if _frontend_static_dir.exists():
    app.mount("/static", StaticFiles(directory=_frontend_static_dir), name="static")
elif _legacy_static_dir.exists():
    logger.warning(
        "Labs frontend static assets not found at %s; falling back to legacy static directory.",
        _frontend_static_dir,
    )
    app.mount("/static", StaticFiles(directory=_legacy_static_dir), name="static")
else:
    logger.warning(
        "Neither labs frontend static directory '%s' nor legacy static directory '%s' were found.",
        _frontend_static_dir,
        _legacy_static_dir,
    )

try:
    _frontend_index_html = _frontend_index_path.read_text(encoding="utf-8")
except FileNotFoundError:
    logger.warning(
        "Labs frontend index '%s' was not found. Falling back to legacy template if available.",
        _frontend_index_path,
    )
    _frontend_index_html = None

try:
    _legacy_index_html = _template_path.read_text(encoding="utf-8")
except FileNotFoundError:
    logger.warning("Frontend template '%s' was not found.", _template_path)
    _legacy_index_html = None


class AskRequest(BaseModel):
    question: str = Field(..., description="Question about Norwegian law or regulations")
    top_k: Optional[int] = Field(None, description="Number of chunks to retrieve")


@app.on_event("startup")
async def startup_event() -> None:
    global _bot
    loop = asyncio.get_event_loop()
    logger.info("Preparing search backend (%s)...", settings.search_backend)
    store_path = await loop.run_in_executor(None, ensure_vector_store)
    _bot = GPTLovBot(store_path=store_path)
    if store_path:
        logger.info("GPTLovBot initialised with vector store at %s", store_path)
    else:
        logger.info("GPTLovBot initialised using Elasticsearch index '%s'", settings.es_index)


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


def _get_bot() -> GPTLovBot:
    if _bot is None:
        raise HTTPException(status_code=503, detail="Search backend not ready")
    return _bot


def _safe_source_name(entry: Dict[str, Any]) -> str:
    def _candidate(value: object) -> str:
        return value.strip() if isinstance(value, str) else ""

    title = _candidate(entry.get("title"))
    if title:
        return title
    refid = _candidate(entry.get("refid"))
    if refid:
        return refid
    source_path = _candidate(entry.get("source_path"))
    if source_path:
        stem = Path(source_path).stem
        return stem or source_path
    return "Kilde"


def _format_sse(event_type: str, payload: object, *, raw: bool = False) -> bytes:
    if raw:
        data = str(payload)
    elif isinstance(payload, (dict, list)):
        data = json.dumps(payload, ensure_ascii=False)
    else:
        data = str(payload)
    message = f"event: {event_type}\ndata: {data}\n\n"
    return message.encode("utf-8")


@app.post("/ask")
async def ask(request: AskRequest) -> StreamingResponse:
    bot = _get_bot()
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[bytes | object] = asyncio.Queue()
    sentinel = object()

    def enqueue(event_type: str, payload: object, *, raw: bool = False) -> None:
        message = _format_sse(event_type, payload, raw=raw)
        loop.call_soon_threadsafe(queue.put_nowait, message)

    def stream_worker() -> None:
        try:
            for event in bot.ask_streaming(request.question, request.top_k):
                event_type = event.get("type") if isinstance(event, dict) else None
                if not event_type:
                    continue
                if event_type == "status":
                    message = event.get("message")
                    if message:
                        enqueue("status", str(message))
                elif event_type == "contexts":
                    contexts = event.get("contexts") or []
                    enqueue("contexts", contexts)
                elif event_type == "chunk":
                    text = event.get("text")
                    if text:
                        enqueue("chunk", {"text": text})
                elif event_type == "answer_html":
                    html = event.get("html")
                    if html:
                        enqueue("answer_html", {"html": html})
                elif event_type == "done":
                    enqueue("done", True)
                    break
        except Exception as exc:  # pragma: no cover - defensive path
            logger.exception("Streaming failed, aborting SSE response")
            enqueue("error", {"message": str(exc)})
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, sentinel)

    loop.run_in_executor(None, stream_worker)

    async def event_generator():
        while True:
            message = await queue.get()
            if message is sentinel:
                break
            if isinstance(message, bytes):
                yield message

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=headers,
    )


@app.post("/api/chat")
async def labs_chat(request: Request) -> StreamingResponse:
    try:
        request_json = await request.json()
    except Exception as exc:  # pragma: no cover - depends on malformed requests
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    question = request_json.get("question")
    if not isinstance(question, str) or not question.strip():
        raise HTTPException(status_code=400, detail="Missing question from request JSON")

    top_k = request_json.get("top_k")
    if not isinstance(top_k, int) or top_k <= 0:
        top_k = None

    session_id = request.query_params.get("session_id") or str(uuid4())
    bot = _get_bot()
    question_value = question.strip()

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[bytes | object] = asyncio.Queue()
    sentinel = object()

    def enqueue(event_type: str, payload: object, *, raw: bool = False) -> None:
        message = _format_sse(event_type, payload, raw=raw)
        loop.call_soon_threadsafe(queue.put_nowait, message)

    def stream_worker() -> None:
        logger.info("Handling labs chat question for session %s", session_id)
        enqueue("session_id", session_id)
        unique_sources: List[str] = []
        sent_source_list = False

        try:
            for event in bot.ask_streaming(question_value, top_k):
                event_type = event.get("type") if isinstance(event, dict) else None
                if not event_type:
                    continue

                if event_type == "status":
                    message = str(event.get("message") or "").strip()
                    if message:
                        enqueue("status", message)
                elif event_type == "contexts":
                    contexts = event.get("contexts")
                    if not isinstance(contexts, list):
                        continue

                    seen: set[str] = set()
                    for entry in contexts:
                        if not isinstance(entry, dict):
                            continue

                        name = _safe_source_name(entry)
                        payload = {
                            "name": name,
                            "page_content": entry.get("content") or "",
                            "url": entry.get("url") or entry.get("source_path") or "",
                            "source_path": entry.get("source_path"),
                            "category": entry.get("category"),
                            "updated_at": entry.get("updated_at"),
                        }
                        enqueue("source", payload)

                        if name and name not in seen:
                            seen.add(name)
                            if name not in unique_sources:
                                unique_sources.append(name)

                    if unique_sources and not sent_source_list:
                        enqueue("source_list", {"names": unique_sources})
                        sent_source_list = True

                    enqueue("contexts", contexts)
                elif event_type == "chunk":
                    chunk = str(event.get("text") or "")
                    if chunk:
                        enqueue("chunk", chunk)
                elif event_type == "answer_html":
                    html = str(event.get("html") or "")
                    if html:
                        enqueue("answer_html", html)
                elif event_type == "done":
                    enqueue("done", True)
                    break
        except Exception as exc:  # pragma: no cover - defensive path
            logger.exception("Labs chat streaming failed")
            enqueue("FatalError", "Beklager, jeg klarte ikke å finne svar denne gangen.", raw=True)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, sentinel)

    loop.run_in_executor(None, stream_worker)

    async def event_generator():
        while True:
            message = await queue.get()
            if message is sentinel:
                break
            if isinstance(message, bytes):
                yield message

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=headers,
    )


@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    html = _frontend_index_html or _legacy_index_html
    if html is None:
        raise HTTPException(status_code=503, detail="Frontend is not available")
    return HTMLResponse(content=html)


@app.get("/{path:path}", include_in_schema=False, response_model=None)
async def spa_assets(path: str) -> Response:
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    candidate = _frontend_dir / path
    if candidate.is_file():
        return FileResponse(candidate)

    html = _frontend_index_html or _legacy_index_html
    if html is None:
        raise HTTPException(status_code=503, detail="Frontend is not available")
    return HTMLResponse(content=html)
