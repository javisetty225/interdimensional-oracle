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

## Known Limitations

### Retrieval — paraphrased relationship queries
Queries describing a character by their relationship to another
character (e.g. "Rick's best friend", "Morty's sister") fail because
the Rick & Morty API only contains factual entity data — name, species,
status, origin. Relationship information is not present in the source
data and would require episode transcript extraction or manual annotation.

### Retrieval — combined attribute queries
Queries combining multiple attributes (e.g. "alive female characters",
"dead aliens from unknown dimension") return partial results because
the semantic search finds the closest single concept rather than
filtering by multiple metadata fields simultaneously. A hybrid approach
combining semantic search with ChromaDB metadata filtering would
resolve this.

### Embedding model
Using all-mpnet-base-v2 for a balance of speed and accuracy. Larger
models like text-embedding-3-large would produce better embeddings
but require an API call and add cost per query.