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
import re
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

STATUS_KEYWORDS = {
    r"\bdead\b": "Dead", r"\bdeceased\b": "Dead",
    r"\balive\b": "Alive", r"\bliving\b": "Alive",
}
GENDER_KEYWORDS = {
    r"\bfemale\b": "Female", r"\bmale\b": "Male", r"\bgenderless\b": "Genderless",
}
SPECIES_KEYWORDS = {
    r"\bhumans?\b": "Human", r"\baliens?\b": "Alien", r"\brobots?\b": "Robot",
    r"\bhumanoids?\b": "Humanoid", r"\banimals?\b": "Animal",
}
_LIST_INTENT = re.compile(
    r"\b(all|list|show|every|how many|which)\b|"
    r"\bcharacters\b|\blocations\b|\bepisodes\b"
)


def build_structured_filter(query: str) -> Optional[dict]:
    """
    Detect attribute-list queries ('all dead characters', 'female robots')
    and build a ChromaDB metadata filter. Returns None for normal questions
    so single-entity queries ('Is Rick dead?') still go through semantic search.
    """
    q = query.lower()
    if not _LIST_INTENT.search(q):
        return None

    conditions = [{"type": "character"}]
    matched = False
    for table in (STATUS_KEYWORDS, GENDER_KEYWORDS, SPECIES_KEYWORDS):
        for pattern, value in table.items():
            if re.search(pattern, q):
                field = "status" if table is STATUS_KEYWORDS else \
                        "gender" if table is GENDER_KEYWORDS else "species"
                conditions.append({field: value})
                matched = True
                break

    if not matched:
        return None

    where = conditions[0] if len(conditions) == 1 else {"$and": conditions}
    return {"where": where}


def retrieve_by_filter(where: dict, limit: int = 25) -> tuple[list[dict], int]:
    """
    Exact metadata match (no embedding). Returns (results, total_match_count).
    Confidence is 1.0 because these are exact field matches, not similarity.
    """
    _load_index()
    ids = _collection.get(where=where, include=[])["ids"]
    total = len(ids)
    if total == 0:
        return [], 0

    raw = _collection.get(ids=ids[:limit], include=["documents", "metadatas"])
    results = []
    for i, doc_id in enumerate(raw["ids"]):
        md = raw["metadatas"][i]
        results.append({
            "doc": {
                "id": doc_id, "type": md["type"], "name": md["name"],
                "text": raw["documents"][i], "raw": json.loads(md["raw"]),
            },
            "confidence": 1.0,
            "distance": 0.0,
        })
    return results, total