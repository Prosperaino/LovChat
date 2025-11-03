from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .bot import LovChatBot
from .data_pipeline import ensure_vector_store
from .settings import settings

logger = logging.getLogger(__name__)

app = FastAPI(title="LovChat", version="0.1.0")

_bot: Optional[LovChatBot] = None


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
    logger.info("Ensuring vector store is available...")
    store_path = await loop.run_in_executor(None, ensure_vector_store)
    _bot = LovChatBot(store_path=store_path)
    logger.info("LovChatBot initialised with store at %s", store_path)


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


def _get_bot() -> LovChatBot:
    if _bot is None:
        raise HTTPException(status_code=503, detail="Vector store not ready")
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


@app.get("/")
async def root() -> Dict[str, str]:
    return {
        "message": "Welcome to LovChat.",
        "docs": "/docs",
    }
