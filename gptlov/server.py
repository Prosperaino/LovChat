from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .bot import GPTLovBot
from .data_pipeline import ensure_vector_store
from .settings import settings

logger = logging.getLogger(__name__)

app = FastAPI(title="GPTLov", version="0.1.0")

_bot: Optional[GPTLovBot] = None
_base_dir = Path(__file__).resolve().parent
_static_dir = _base_dir / "static"
_template_path = _base_dir / "templates" / "index.html"

if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")
else:
    logger.warning("Static assets directory '%s' was not found.", _static_dir)

try:
    _index_html = _template_path.read_text(encoding="utf-8")
except FileNotFoundError:
    logger.warning("Frontend template '%s' was not found.", _template_path)
    _index_html = None


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


def _format_sse(event_type: str, payload: object) -> bytes:
    if isinstance(payload, (dict, list)):
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

    def enqueue(event_type: str, payload: object) -> None:
        message = _format_sse(event_type, payload)
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


@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    if _index_html is None:
        raise HTTPException(status_code=503, detail="Frontend is not available")
    return HTMLResponse(content=_index_html)
