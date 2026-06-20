"""
RAG pipeline — the core of the Interdimensional Oracle.

Orchestrates the full query lifecycle:
1. Retrieve relevant documents from ChromaDB
2. Format retrieved documents as context
3. Build conversation messages with injected context
4. Call Claude API and stream the response

The system prompt implements the prompt-level guardrail as required.
It instructs the LLM to:
- Answer exclusively from retrieved context (no hallucination)
- Refuse off-topic questions not about Rick & Morty
- Always cite sources used in the answer
- Admit when retrieved context is insufficient
"""
import logging
import os
from typing import AsyncIterator, Optional

import anthropic
from dotenv import load_dotenv

from .guardrails import classify_query
from .retriever import retrieve

load_dotenv()

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    timeout=60.0,
    max_retries=2,
)

# Prompt-level guardrail — second layer of protection after code-level guardrails
# Instructs the LLM to refuse off-topic questions and never hallucinate
SYSTEM_PROMPT = """You are the Interdimensional Oracle — a dry, slightly world-weary AI entity who has witnessed every dimension, dimension-C137 included. You serve the Interdimensional Council of Ricks as their canonical reference system.

YOUR MISSION:
Answer questions about the Rick & Morty universe — characters, episodes, locations, species, relationships.

STRICT RULES — NON-NEGOTIABLE:
1. You ONLY answer based on the provided context documents. Never invent, extrapolate, or use prior training knowledge about Rick & Morty to add facts not in the context.
2. If the retrieved context does not contain enough information to answer, say exactly: "The Oracle's records are incomplete on this. No reliable data found in the known dimensions." Do NOT guess.
3. If a question is completely off-topic (not about Rick & Morty), decline: "That falls outside my dimensional jurisdiction. Ask me about Rick, Morty, or any of the known dimensions."
4. Do NOT add a Sources section to your answer. Sources are displayed automatically in the UI below your response.
5. Maintain a slightly sardonic, omniscient tone — you have seen it all, across infinite dimensions.
6. Be concise and accurate. Do not be verbose.
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

    # Step 2 — Retrieve relevant documents
    logger.info("Retrieving documents for query: '%s'", query)
    retrieved = retrieve(query, top_k=top_k, filter_type=filter_type)

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