import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from datasets import Dataset
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from ragas import evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    context_precision,
    context_recall,
    faithfulness,
)
from ragas.run_config import RunConfig

from backend.core.rag import rag_response_full
from backend.core.retriever import retrieve
from golden_dataset import GOLDEN_DATASET, EvalSample


# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------

load_dotenv()

ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
TOP_K = 5
MAX_WORKERS = 1

OUTPUT_FILE = (
    Path(__file__).resolve().parent
    / "evaluation_results.json"
)


# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# Evaluator
# ------------------------------------------------------------------------------

class RAGEvaluator:
    def __init__(self) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")

        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found.")

        self.llm = LangchainLLMWrapper(
            ChatAnthropic(
                model=ANTHROPIC_MODEL,
                api_key=api_key,
                temperature=0,
            )
        )

    async def process_question(
        self,
        sample: EvalSample,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        """Execute the RAG pipeline for a single sample."""
        try:
            rag_result = await rag_response_full(
                sample.question,
                history=[],
                system_prompt=system_prompt,
            )

            retrieved_docs = retrieve(sample.question, top_k=TOP_K)
            contexts = [doc["doc"]["text"] for doc in retrieved_docs]

            return {
                "question": sample.question,
                "answer": rag_result.get("answer", ""),
                "contexts": contexts,
                "ground_truth": sample.ground_truth,
            }

        except Exception:
            logger.exception("Failed processing question: %s", sample.question)
            return {
                "question": sample.question,
                "answer": "",
                "contexts": [],
                "ground_truth": sample.ground_truth,
            }

    async def build_dataset(
        self,
        system_prompt: str | None = None,
    ) -> Dataset:
        """Run the RAG pipeline over the golden set and build a dataset."""
        logger.info(
            "Building evaluation dataset (%d samples)...",
            len(GOLDEN_DATASET),
        )

        results = await asyncio.gather(
            *[
                self.process_question(sample, system_prompt=system_prompt)
                for sample in GOLDEN_DATASET
            ]
        )

        return Dataset.from_dict({
            "question": [r["question"] for r in results],
            "answer": [r["answer"] for r in results],
            "contexts": [r["contexts"] for r in results],
            "ground_truth": [r["ground_truth"] for r in results],
        })

    def evaluate_dataset(self, dataset: Dataset):
        logger.info("Starting RAGAS evaluation...")
        return evaluate(
            dataset=dataset,
            metrics=[faithfulness, context_precision, context_recall],
            llm=self.llm,
            run_config=RunConfig(max_workers=MAX_WORKERS),
        )

    async def run(self) -> None:
        from backend.core.rag import SYSTEM_PROMPT, MINIMAL_SYSTEM_PROMPT

        start = time.perf_counter()
        all_scores = {}

        for label, prompt in [
            ("persona", SYSTEM_PROMPT),
            ("minimal", MINIMAL_SYSTEM_PROMPT),
        ]:
            logger.info("Evaluating config: %s", label)
            dataset = await self.build_dataset(system_prompt=prompt)
            result = self.evaluate_dataset(dataset)
            all_scores[label] = {m: round(result[m], 4) for m in result.keys()}

        all_scores["elapsed_time_seconds"] = round(time.perf_counter() - start, 2)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(all_scores, f, indent=2)

        logger.info("Results saved to %s", OUTPUT_FILE)


async def main() -> None:
    evaluator = RAGEvaluator()
    await evaluator.run()


if __name__ == "__main__":
    asyncio.run(main())