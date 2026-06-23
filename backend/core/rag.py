"""
RAG pipeline — orchestrates the full query lifecycle.

Flow:
  1. Code-level guardrail check (guardrails.py)
  2. ChromaDB retrieval (retriever.py)
  3. Context injection into Claude's prompt
  4. Streaming SSE response via Anthropic API

The system prompt is the prompt-level guardrail — the second
of two required guardrail mechanisms. It instructs Claude to:
  - Answer only from retrieved context (no hallucination)
  - Refuse non-Rick & Morty questions
  - Never add a sources section (displayed by the frontend)
"""
import logging
import os
from typing import AsyncIterator, Optional

import anthropic
from dotenv import load_dotenv

from .guardrails import classify_query
from .retriever import retrieve, build_structured_filter, retrieve_by_filter

load_dotenv()

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    timeout=60.0,
    max_retries=2,
)

# Prompt-level guardrail — second layer of protection after code-level guardrails
# Instructs the LLM to refuse off-topic questions and never hallucinate
SYSTEM_PROMPT = """You are the Interdimensional Oracle — a dry, slightly world-weary AI entity who has witnessed every dimension. You serve the Interdimensional Council of Ricks as their canonical reference system.

YOUR MISSION:
Answer questions about the Rick & Morty universe — characters, episodes, locations, species, relationships.

STRICT RULES — NON-NEGOTIABLE:
1. Answer ONLY based on the provided context documents. Never use prior knowledge or invent facts not in the context.
2. If the context does not contain enough information, say exactly: "The Oracle's records are incomplete on this. No reliable data found in the known dimensions."
3. If a question is not about Rick & Morty, say: "That falls outside my dimensional jurisdiction."
4. Do NOT add a Sources section — sources are displayed automatically in the UI.
5. Keep the sardonic Oracle tone but be concise. Every factual claim must come directly from the retrieved context.
6. Do not add background knowledge about Rick & Morty that is not present in the retrieved documents.
"""


def _format_context(retrieved: list[dict]) -> str:
    """
    Format retrieved documents as readable context for the LLM.

    Each document is labeled with its type and relevance score
    so the LLM knows what it is working with.
    """
    if not retrieved:
        return "No relevant documents found in the Oracle's records."

    parts = []
    for i, result in enumerate(retrieved, 1):
        doc = result["doc"]
        confidence_pct = int(result["confidence"] * 100)
        parts.append(
            f"[Source {i} | Type: {doc['type']} | "
            f"Relevance: {confidence_pct}%]\n{doc['text']}"
        )

    return "\n\n".join(parts)


def _build_messages(
    query: str,
    history: list[dict],
    context: str,
) -> list[dict]:
    """
    Build the messages array for the Claude API call.

    Injects retrieved context into the current user message.
    Filters out blocked exchanges from history to prevent
    contaminating the conversation context.

    Args:
        query:   current user query
        history: previous conversation turns
        context: formatted retrieved documents

    Returns:
        List of message dicts for the Claude API
    """
    messages = []

    # Rebuild history as clean pairs only
    # Skip blocked responses to prevent context contamination
    turns = history[-12:]
    i = 0
    while i < len(turns) - 1:
        user_turn = turns[i]
        assistant_turn = turns[i + 1]
        is_clean = (
            user_turn["role"] == "user"
            and assistant_turn["role"] == "assistant"
            and not assistant_turn["content"].startswith("🚫")
            and not assistant_turn["content"].startswith("⚠️")
        )
        if is_clean:
            messages.append(user_turn)
            messages.append(assistant_turn)
        i += 2

    # Inject context into the current user message
    user_content = (
        f"RETRIEVED CONTEXT:\n{context}\n\n"
        f"---\n\n"
        f"USER QUESTION: {query}\n\n"
        f"Answer based solely on the context above."
    )
    messages.append({"role": "user", "content": user_content})

    return messages


async def stream_rag_response(
    query: str,
    history: list[dict],
    top_k: int = 5,
    filter_type: Optional[str] = None,
) -> AsyncIterator[dict]:
    """
    Main RAG entry point. Yields streaming chunks as dicts.

    Chunk types:
    - instant:         pre-built response, no LLM needed (greeting/help)
    - guardrail_block: query blocked by code-level guardrail
    - sources:         retrieved document metadata, sent before text
    - text_delta:      streaming text chunk from Claude
    - done:            stream complete
    - error:           API error occurred

    Args:
        query:       user question
        history:     previous conversation turns
        top_k:       number of documents to retrieve
        filter_type: optional entity type filter
    """
    # Step 1 — Code-level guardrail check
    guard = classify_query(query)

    # Handle instant responses — greetings and help requests
    if guard.get("instant_response"):
        yield {
            "type": "instant",
            "text": guard["instant_response"],
            "reason": guard["reason"],
        }
        return

    # Handle blocked queries
    if not guard["allowed"]:
        yield {
            "type": "guardrail_block",
            "reason": guard["reason"],
            "detail": guard["detail"],
        }
        return

    # Step 2 — Structured attribute filter first, else semantic retrieval
    structured = build_structured_filter(query)
    if structured:
        logger.info("Structured attribute query: %s", structured["where"])
        retrieved, total_matches = retrieve_by_filter(structured["where"])
    else:
        logger.info("Retrieving documents for query: '%s'", query)
        retrieved = retrieve(query, top_k=top_k, filter_type=filter_type)
        total_matches = len(retrieved)

    # Step 3 — Yield source metadata before streaming starts
    # Frontend uses this to show source tags and confidence bar
    sources = [
        {
            "id": r["doc"]["id"],
            "name": r["doc"]["name"],
            "type": r["doc"]["type"],
            "confidence": r["confidence"],
        }
        for r in retrieved
    ]
    overall_confidence = (
        sum(r["confidence"] for r in retrieved) / len(retrieved)
        if retrieved else 0.0
    )
    yield {
        "type": "sources",
        "sources": sources,
        "overall_confidence": round(overall_confidence, 3),
        "retrieved_count": len(retrieved),
    }

    # Step 4 — Build prompt with injected context
    context = _format_context(retrieved)
    if total_matches > len(retrieved):
        context = (
                f"NOTE: {total_matches} entities match this query. "
                f"Showing the first {len(retrieved)}.\n\n" + context
        )
    messages = _build_messages(query, history, context)

    # Step 5 — Stream Claude response
    logger.info(
        "Calling Claude with %d retrieved documents",
        len(retrieved),
    )
    try:
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=messages,
        ) as stream:
            for text_chunk in stream.text_stream:
                yield {"type": "text_delta", "text": text_chunk}

        yield {"type": "done"}

    except anthropic.APIError as e:
        logger.error("Claude API error: %s", e)
        yield {"type": "error", "message": str(e)}


async def rag_response_full(
    query: str,
    history: list[dict],
    top_k: int = 5,
    filter_type: Optional[str] = None,
) -> dict:
    """
    Non-streaming version of the RAG pipeline.
    Used for testing without needing a streaming client.

    Returns a complete response dict with answer, sources,
    confidence, and block status.
    """
    full_text = ""
    result = {}

    async for chunk in stream_rag_response(
        query, history, top_k, filter_type
    ):
        if chunk["type"] == "instant":
            return {
                "answer": chunk["text"],
                "sources": [],
                "overall_confidence": 0.0,
                "blocked": False,
                "reason": chunk["reason"],
            }
        elif chunk["type"] == "sources":
            result.update(chunk)
        elif chunk["type"] == "text_delta":
            full_text += chunk["text"]
        elif chunk["type"] == "guardrail_block":
            return {
                "answer": chunk["detail"],
                "sources": [],
                "overall_confidence": 0.0,
                "blocked": True,
                "reason": chunk["reason"],
            }
        elif chunk["type"] == "error":
            return {
                "answer": f"Error: {chunk['message']}",
                "sources": [],
                "overall_confidence": 0.0,
                "blocked": False,
                "reason": "error",
            }

    result["answer"] = full_text
    result["blocked"] = False
    return result