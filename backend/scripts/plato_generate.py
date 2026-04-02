"""
backend/scripts/plato_generate.py
Stage 9 — CLI entry point for the Plato generation pipeline.

Run from the backend/ directory:
    python scripts/plato_generate.py

With a specific topic filter:
    PLATO_TOPIC=arrays python scripts/plato_generate.py

With custom generation parameters:
    PLATO_VARIANTS_PER_PROBLEM=5 PLATO_MIN_UTILITY_INSERT=0.55 \\
        python scripts/plato_generate.py

Exit codes:
    0  — generation completed (check output for accepted count)
    1  — no source problems found or all candidates rejected
    2  — unexpected infrastructure error
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Ensure backend/ is on sys.path when invoked as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from plato.config import PlatoConfig
from plato.generate import PlatoGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("plato_generate_script")


async def main() -> int:
    cfg = PlatoConfig()
    topic_filter = os.getenv("PLATO_TOPIC")

    logger.info(
        "Starting Plato generation pipeline. "
        "model=%s variants_per_problem=%d min_utility_insert=%.2f topic_filter=%s",
        cfg.model,
        cfg.variants_per_problem,
        cfg.min_utility_insert,
        topic_filter or "all",
    )

    generator = PlatoGenerator(cfg)

    try:
        results = await generator.run(topic_filter=topic_filter)
    except Exception as exc:
        logger.exception("Unexpected error during generation pipeline: %s", exc)
        return 2

    if not results:
        logger.warning("No source problems found — generation produced no results.")
        return 1

    total_inserted = sum(r.candidates_accepted for r in results)
    total_rejected = sum(r.candidates_rejected for r in results)

    # Summary JSON
    summary = {
        "source_problems_processed": len(results),
        "total_candidates_generated": sum(r.candidates_generated for r in results),
        "total_accepted": total_inserted,
        "total_rejected": total_rejected,
        "per_problem": [r.model_dump() for r in results],
    }
    print(json.dumps(summary, indent=2, default=str))

    if total_inserted == 0:
        logger.warning("Generation pipeline ran but inserted 0 problems.")
        return 1

    logger.info(
        "Generation complete: %d problems inserted (created_by='plato').",
        total_inserted,
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
