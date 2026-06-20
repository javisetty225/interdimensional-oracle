"""
Builds a semantic vector knowledge base from raw Rick & Morty API data.

Architecture decision: ChromaDB + sentence-transformers (all-mpnet-base-v2).

Development history:
- BM25 + TF-IDF was evaluated first. Exact name queries worked well but
  paraphrased queries failed consistently due to keyword mismatch.
- ChromaDB with all-MiniLM-L6-v2 was evaluated next. Location queries
  improved but highly paraphrased queries remained weak.
- Upgraded to all-mpnet-base-v2 for better semantic understanding.
  This model produces higher quality embeddings at the cost of size.

Why ChromaDB over a vector database service:
- Runs fully locally — no external server, no API cost, no network dependency
- Stores index as local files — fast startup, easy to rebuild
- Sufficient for 1003 documents at this scale

Known limitation:
- Relationship queries ("friend of Rick", "enemy of Morty") fail because
  the API only contains factual data — relationships are not in the source.
- Descriptive queries ("dead characters") are weaker than metadata filtering.
  A hybrid search approach would improve this.
"""
import json
import logging
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "raw"
CHROMA_DIR = Path(__file__).parent / "chroma_db"

COLLECTION_NAME = "rick_and_morty"
EMBEDDING_MODEL = "all-mpnet-base-v2"
BATCH_SIZE = 64


def build_character_doc(c: dict) -> dict:
    """
    Convert a raw character record into a rich searchable text document.

    Written in natural language so the embedding model captures semantic
    meaning. Species and type are combined to improve soft matching.
    Frequency description helps queries like 'main characters'.
    """
    episodes = c.get("episode", [])
    episode_count = len(episodes)

    if episode_count >= 40:
        frequency = "major recurring character appearing in nearly all episodes"
    elif episode_count >= 10:
        frequency = "recurring character appearing in many episodes"
    elif episode_count >= 3:
        frequency = "supporting character appearing in several episodes"
    else:
        frequency = "minor character with limited appearances"

    species = c.get("species", "unknown")
    char_type = c.get("type") or ""
    species_desc = f"{species} of type {char_type}" if char_type else species

    name = c["name"]
    status = c["status"]
    gender = c["gender"]
    origin = c["origin"]["name"]
    location = c["location"]["name"]

    text = (
        f"{name} is a {status.lower()} {species_desc} character. "
        f"Gender: {gender}. "
        f"Originally from {origin}. "
        f"Currently located at {location}. "
        f"This is a {frequency}. "
        f"Appears in {episode_count} episode(s)."
    )

    return {
        "id": f"character_{c['id']}",
        "type": "character",
        "name": name,
        "text": text,
        "raw": c,
    }


def build_episode_doc(e: dict) -> dict:
    """
    Convert a raw episode record into a searchable text document.

    Season and episode numbers written in natural language to help
    queries like 'first episode of season 3' find S03E01.
    """
    chars = e.get("characters", [])
    season_ep = e.get("episode", "")

    season_desc = ""
    if season_ep and len(season_ep) == 6:
        season_num = str(int(season_ep[1:3]))
        ep_num = str(int(season_ep[4:6]))
        season_desc = (
            f"This is season {season_num} episode {ep_num}. "
            f"Season {season_num}, episode number {ep_num}. "
        )

    text = (
        f"Episode: {e['name']}. "
        f"Code: {season_ep}. "
        f"Air date: {e.get('air_date', 'unknown')}. "
        f"{season_desc}"
        f"Features {len(chars)} character(s)."
    )

    return {
        "id": f"episode_{e['id']}",
        "type": "episode",
        "name": e["name"],
        "text": text,
        "raw": e,
        "season_ep": season_ep,
    }


def build_location_doc(loc: dict) -> dict:
    """
    Convert a raw location record into a searchable text document.
    """
    residents = loc.get("residents", [])

    text = (
        f"Location: {loc['name']}. "
        f"Type: {loc.get('type') or 'unknown'}. "
        f"Dimension: {loc.get('dimension') or 'unknown'}. "
        f"Has {len(residents)} known resident(s)."
    )

    return {
        "id": f"location_{loc['id']}",
        "type": "location",
        "name": loc["name"],
        "text": text,
        "raw": loc,
    }


def load_raw_data() -> list[dict]:
    """
    Load and convert all raw JSON files into searchable documents.
    Returns a flat list of all documents across all entity types.
    """
    documents = []

    builders = [
        ("character.json", build_character_doc),
        ("episode.json", build_episode_doc),
        ("location.json", build_location_doc),
    ]

    for fname, builder in builders:
        path = DATA_DIR / fname
        if not path.exists():
            logger.warning("%s not found — run fetcher.py first", fname)
            continue

        with open(path, encoding="utf-8") as f:
            records = json.load(f)

        for record in records:
            documents.append(builder(record))

        entity_type = fname.replace(".json", "")
        logger.info("Loaded %d %s records", len(records), entity_type)

    return documents


def build_index() -> None:
    """
    Build ChromaDB vector index from raw data files.

    Process:
    1. Load and convert raw JSON into text documents
    2. Load sentence-transformers embedding model locally
    3. Generate embeddings for all documents in batches
    4. Store embeddings and metadata in ChromaDB
    """
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    documents = load_raw_data()
    if not documents:
        raise RuntimeError("No documents found. Run fetcher.py first.")

    # Load embedding model — runs fully locally, no API needed
    logger.info("Loading embedding model: %s", EMBEDDING_MODEL)
    model = SentenceTransformer(EMBEDDING_MODEL)

    # Connect to ChromaDB
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    # Delete existing collection if rebuilding
    try:
        client.delete_collection(COLLECTION_NAME)
        logger.info("Deleted existing collection for clean rebuild")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # Generate embeddings and store in batches
    logger.info(
        "Generating embeddings for %d documents in batches of %d...",
        len(documents),
        BATCH_SIZE,
    )

    for i in tqdm(range(0, len(documents), BATCH_SIZE), desc="Embedding"):
        batch = documents[i: i + BATCH_SIZE]
        texts = [d["text"] for d in batch]
        embeddings = model.encode(
            texts,
            show_progress_bar=False,
        ).tolist()

        collection.add(
            ids=[d["id"] for d in batch],
            documents=texts,
            embeddings=embeddings,
            metadatas=[
                {
                    "type": d["type"],
                    "name": d["name"],
                    "raw": json.dumps(d["raw"]),
                }
                for d in batch
            ],
        )

    logger.info(
        "Index built successfully — %d documents stored in ChromaDB at %s",
        len(documents),
        CHROMA_DIR,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    build_index()