"""
Fetches all data from the Rick & Morty API and stores it locally.
Handles pagination, rate limiting, and retries automatically.
"""
import asyncio
import json
import logging
from pathlib import Path

import httpx
from tqdm import tqdm

logger = logging.getLogger(__name__)

BASE_URL = "https://rickandmortyapi.com/api"
DATA_DIR = Path(__file__).parent / "raw"

ENDPOINTS = ["character", "episode", "location"]
REQUEST_DELAY_SECONDS = 0.3
RATE_LIMIT_WAIT_SECONDS = 5
REQUEST_TIMEOUT_SECONDS = 30.0
MAX_RETRIES = 3


async def fetch_all_pages(
    client: httpx.AsyncClient,
    endpoint: str,
) -> list[dict]:
    """
    Fetch all paginated results for a given endpoint.
    Handles 429 rate limiting with incremental backoff.

    Args:
        client:   shared httpx async client
        endpoint: API endpoint name e.g. "character"

    Returns:
        Complete list of all records across all pages
    """
    url = f"{BASE_URL}/{endpoint}"
    results = []

    while url:
        for attempt in range(MAX_RETRIES):
            try:
                resp = await client.get(url)
            except httpx.RequestError as e:
                logger.error("Network error fetching %s: %s", url, e)
                raise

            if resp.status_code == 429:
                wait = RATE_LIMIT_WAIT_SECONDS * (attempt + 1)
                logger.warning(
                    "Rate limited on %s — attempt %d/%d, waiting %ds",
                    endpoint, attempt + 1, MAX_RETRIES, wait,
                )
                await asyncio.sleep(wait)
                continue

            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.error("HTTP error on %s: %s", url, e)
                raise

            break
        else:
            raise RuntimeError(
                f"Failed to fetch {endpoint} after {MAX_RETRIES} retries"
            )

        data = resp.json()
        results.extend(data["results"])
        url = data["info"].get("next")

        await asyncio.sleep(REQUEST_DELAY_SECONDS)

    return results


async def fetch_all_data() -> None:
    """
    Fetch all characters, episodes, and locations from the API.
    Saves each dataset as a JSON file in the raw data directory.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        logger.info("Fetching Rick & Morty Universe data...")

        for endpoint in tqdm(ENDPOINTS, desc="Fetching"):
            records = await fetch_all_pages(client, endpoint)

            out_path = DATA_DIR / f"{endpoint}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)

            logger.info(
                "Saved %d %s records to %s",
                len(records), endpoint, out_path,
            )

    logger.info("All data fetched successfully.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    asyncio.run(fetch_all_data())