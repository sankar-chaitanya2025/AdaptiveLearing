"""
backend/scripts/plato_train.py
Stage 9 — CLI entry point for the Plato training pipeline.

Run from the backend/ directory:
    python scripts/plato_train.py

Or with custom env overrides:
    PLATO_MIN_LOGS=50 PLATO_MIN_UTILITY_TRAIN=0.25 python scripts/plato_train.py

Exit codes:
    0  — training dataset exported successfully
    1  — insufficient data or all rows invalid
    2  — unexpected infrastructure error
"""

import json
import logging
import sys
from pathlib import Path

# Ensure backend/ is on sys.path when invoked as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import SessionLocal
from plato.config import PlatoConfig
from plato.train import PlatoTrainer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("plato_train_script")


def main() -> int:
    cfg = PlatoConfig()
    logger.info(
        "Starting Plato training pipeline. "
        "model=%s min_logs=%d min_utility_train=%.2f artifact_dir=%s",
        cfg.model, cfg.min_logs, cfg.min_utility_train, cfg.artifact_dir,
    )

    trainer = PlatoTrainer(cfg)
    db = SessionLocal()

    try:
        result = trainer.run(db)
    except Exception as exc:
        logger.exception("Unexpected error during training pipeline: %s", exc)
        return 2
    finally:
        db.close()

    # Pretty-print the result for operator review
    print(json.dumps(result.model_dump(mode="json", exclude={"timestamp"}), indent=2))

    if result.success:
        logger.info("Training pipeline completed successfully.")
        return 0
    else:
        logger.warning("Training pipeline did not complete: %s", result.message)
        return 1


if __name__ == "__main__":
    sys.exit(main())
