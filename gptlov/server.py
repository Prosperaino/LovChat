from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
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


class SourceResponse(BaseModel):
    title: Optional[str]
    refid: Optional[str]
    source_path: str
    score: float
    content: str


class AskResponse(BaseModel):
    answer: str
    sources: List[SourceResponse]


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


@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest) -> AskResponse:
    bot = _get_bot()
    loop = asyncio.get_event_loop()
    result: Dict[str, Any] = await loop.run_in_executor(
        None, bot.ask, request.question, request.top_k
    )

    sources = [
        SourceResponse(
            title=entry.get("title"),
            refid=entry.get("refid"),
            source_path=entry.get("source_path", ""),
            score=float(entry.get("score", 0.0)),
            content=entry.get("content", ""),
        )
        for entry in result.get("contexts", [])
    ]

    return AskResponse(answer=result["answer"], sources=sources)


@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    if _index_html is None:
        raise HTTPException(status_code=503, detail="Frontend is not available")
    return HTMLResponse(content=_index_html)
