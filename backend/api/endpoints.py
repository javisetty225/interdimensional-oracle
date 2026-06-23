"""Route handlers for all API endpoints."""
import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import core.retriever as retriever_module
from core.rag import stream_rag_response
from core.retriever import retrieve
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from .models import BrowseRequest, ChatRequest, FeedbackRequest

logger = logging.getLogger(__name__)

router = APIRouter()

FEEDBACK_LOG = Path(__file__).parent.parent / "data" / "feedback.jsonl"
SUMMARY_PREVIEW_CHARS = 200


def _append_feedback_entry(entry: dict) -> None:
    with open(FEEDBACK_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


@router.get("/health")
async def health():
    """
    Health check endpoint.
    Returns server status and index document count.
    """
    collection = retriever_module._collection
    index_loaded = collection is not None
    doc_count = collection.count() if index_loaded else 0

    return {
        "status": "ok",
        "index_loaded": index_loaded,
        "doc_count": doc_count,
    }


@router.get("/stats")
async def stats():
    """
    Return document counts by entity type.
    Used by the frontend to display collection statistics.
    """
    retriever_module._load_index()
    collection = retriever_module._collection

    counts = {}
    for entity_type in ["character", "episode", "location"]:
        result = collection.get(
            where={"type": entity_type},
            include=[],
        )
        counts[entity_type] = len(result["ids"])

    return {
        "counts": counts,
        "total": sum(counts.values()),
    }


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Main chat endpoint using Server-Sent Events for streaming.

    Each SSE event is a JSON object with a 'type' field:
    - instant:         pre-built response (greeting/help), no LLM
    - guardrail_block: query blocked by code-level guardrail
    - sources:         retrieved document metadata
    - text_delta:      streaming text chunk from Claude
    - done:            stream complete
    - error:           API error
    """
    history_dicts = [m.model_dump() for m in request.history]

    async def event_generator():
        try:
            async for chunk in stream_rag_response(
                query=request.query,
                history=history_dicts,
                top_k=request.top_k,
                filter_type=request.filter_type,
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
                await asyncio.sleep(0)
        except Exception as e:
            logger.error("Stream error: %s", e)
            error_chunk = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(error_chunk)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """
    Log user feedback for Human-in-the-Loop signal collection.

    Feedback is appended to a local JSONL file.
    Each line is a JSON object with timestamp, query, and helpful flag.
    This simulates a real HITL feedback loop for model improvement.
    """
    FEEDBACK_LOG.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "message_id": request.message_id,
        "query": request.query,
        "helpful": request.helpful,
        "comment": request.comment,
    }

    await asyncio.to_thread(_append_feedback_entry, entry)

    logger.info(
        "Feedback logged — query: '%s', helpful: %s",
        request.query,
        request.helpful,
    )

    return {"status": "recorded"}


@router.post("/browse")
async def browse(request: BrowseRequest):
    """
    Browse all entities with optional search and type filter.

    Returns paginated results. If a search query is provided,
    results are ranked by semantic similarity. Otherwise results
    are returned alphabetically.

    Used by the optional Browse Mode feature in the frontend.
    """
    retriever_module._load_index()
    collection = retriever_module._collection

    if request.search and request.search.strip():
        results = retrieve(
            request.search,
            top_k=50,
            filter_type=request.filter_type,
        )
        docs = [r["doc"] for r in results]
    else:
        where = (
            {"type": request.filter_type}
            if request.filter_type
            else None
        )
        raw = collection.get(
            where=where,
            include=["documents", "metadatas"],
        )
        docs = [
            {
                "id": raw["ids"][i],
                "type": raw["metadatas"][i]["type"],
                "name": raw["metadatas"][i]["name"],
                "text": raw["documents"][i],
                "raw": json.loads(raw["metadatas"][i]["raw"]),
            }
            for i in range(len(raw["ids"]))
        ]
        docs = sorted(docs, key=lambda d: d["name"].lower())

    total = len(docs)
    start = (request.page - 1) * request.page_size
    page_docs = docs[start: start + request.page_size]

    return {
        "total": total,
        "page": request.page,
        "page_size": request.page_size,
        "results": [
            {
                "id": d["id"],
                "name": d["name"],
                "type": d["type"],
                "summary": (
                    d["text"][:SUMMARY_PREVIEW_CHARS] + "..."
                    if len(d["text"]) > SUMMARY_PREVIEW_CHARS
                    else d["text"]
                ),
                "raw": d["raw"],
            }
            for d in page_docs
        ],
    }