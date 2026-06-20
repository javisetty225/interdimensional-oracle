# 🌀 Interdimensional Oracle

> A RAG-powered AI agent that answers questions about the Rick & Morty
> universe — exclusively from retrieved data, never from LLM memory.

## The Problem

The Interdimensional Council of Ricks has a data problem.
826 characters, 51 episodes, 126 locations across infinite dimensions.
Even the smartest Rick loses track. This oracle solves it.

## Planned Architecture

```
User Query
    ↓
Guardrails       ← block off-topic queries before they hit the LLM
    ↓
Retriever        ← semantic search over local ChromaDB vector store
    ↓
RAG Pipeline     ← inject context into prompt, call LLM
    ↓
Streaming UI     ← stream response back to the user word by word
```

## Tech Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Backend | FastAPI + Python | Async, native SSE streaming support |
| Retrieval | ChromaDB + sentence-transformers | Semantic search handles paraphrased queries correctly. Runs fully locally with no API cost |
| LLM | Claude Sonnet (Anthropic) | Strong instruction following, strict context grounding |
| Frontend | React + Vite | Fast, lightweight, no unnecessary complexity |

## Status

🚧 Under active development — built step by step.
Follow the commit history to see how each component was implemented.

## Setup

> Full setup guide will be added once the system is complete.
