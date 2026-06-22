"""
ChromaDB semantic retriever.

Encodes queries as 768-dim vectors using all-mpnet-base-v2
and performs cosine similarity search over 1003 documents.

Why all-mpnet-base-v2 over alternatives:
  - all-MiniLM-L6-v2: tested first, weaker on paraphrased queries
  - text-embedding-3-large: requires OpenAI API call per query
  - all-mpnet-base-v2: runs fully locally, strong semantic understanding

Confidence score = 1 - (cosine_distance / 2), range 0.0 to 1.0.
"""
import os
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"

import json
import logging
from pathlib import Path
from typing import Optional

import chromadb
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

CHROMA_DIR = Path(__file__).parent.parent / "data" / "chroma_db"
COLLECTION_NAME = "rick_and_morty"
EMBEDDING_MODEL = "all-mpnet-base-v2"

# Module-level cache — loaded once at server startup, reused for every query
_collection = None
_model = None


def _load_index() -> None:
    """
    Load ChromaDB collection and embedding model into memory.
    Called once at server startup — subsequent calls are no-ops.
    """
    global _collection, _model

    if _collection is not None:
        return

    logger.info("Loading embedding model: %s", EMBEDDING_MODEL)
    _model = SentenceTransformer(EMBEDDING_MODEL)

    logger.info("Connecting to ChromaDB at %s", CHROMA_DIR)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    _collection = client.get_collection(COLLECTION_NAME)

    logger.info(
        "Loaded collection with %d documents",
        _collection.count(),
    )


def _distance_to_confidence(distance: float) -> float:
    """
    Convert ChromaDB cosine distance to a confidence score.

    ChromaDB returns cosine distance where:
    - 0.0 = identical documents (perfect match)
    - 2.0 = completely opposite documents (no match)

    We convert to confidence where:
    - 1.0 = perfect match
    - 0.0 = no match
    """
    return round(max(0.0, 1.0 - (distance / 2)), 3)


def retrieve(
    query: str,
    top_k: int = 5,
    filter_type: Optional[str] = None,
) -> list[dict]:
    """
    Search the ChromaDB knowledge base for documents relevant to the query.

    Encodes the query as an embedding vector and finds the most
    semantically similar documents using cosine similarity.

    Args:
        query:       The user's question in natural language
        top_k:       Number of documents to return (default 5)
        filter_type: Optional filter — "character", "episode", or "location"

    Returns:
        List of dicts ordered by relevance, each containing:
          - doc:        document with id, type, name, text, raw fields
          - confidence: similarity score 0.0 to 1.0
          - distance:   raw ChromaDB cosine distance
    """
    _load_index()

    # Encode query into embedding vector
    logger.debug("Encoding query: %s", query)
    query_embedding = _model.encode(query).tolist()

    # Build optional metadata filter
    where = {"type": filter_type} if filter_type else None

    # Query ChromaDB for most similar documents
    results = _collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    # Format results into consistent structure
    formatted = []
    ids = results["ids"][0]
    distances = results["distances"][0]
    metadatas = results["metadatas"][0]
    documents = results["documents"][0]

    for i, doc_id in enumerate(ids):
        metadata = metadatas[i]
        distance = distances[i]
        confidence = _distance_to_confidence(distance)

        formatted.append({
            "doc": {
                "id": doc_id,
                "type": metadata["type"],
                "name": metadata["name"],
                "text": documents[i],
                "raw": json.loads(metadata["raw"]),
            },
            "confidence": confidence,
            "distance": round(float(distance), 4),
        })

    logger.debug(
        "Query '%s' → %d results (top confidence: %.3f)",
        query,
        len(formatted),
        formatted[0]["confidence"] if formatted else 0.0,
    )

    return formatted