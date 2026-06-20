"""FastAPI application setup, middleware, and router registration."""
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import core.retriever as retriever_module
from api.endpoints import router

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Load the ChromaDB index and embedding model at server startup.
    This ensures the first query is fast — no cold start delay.
    """
    logger.info("Starting Interdimensional Oracle server...")
    try:
        retriever_module._load_index()
        logger.info("Index loaded successfully.")
    except Exception as e:
        logger.warning("Index not ready: %s — run indexer.py first.", e)
    yield
    logger.info("Server shutting down.")


app = FastAPI(
    title="Interdimensional Oracle API",
    description="RAG-powered Rick & Morty knowledge agent",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)