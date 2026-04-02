"""
backend/plato/train.py
Stage 9 — Plato WSFT Training Pipeline.

Responsibilities:
  1. Fetch eligible plato_log rows from DB
  2. Convert to weighted TrainingExample objects (with validation)
  3. Export JSONL dataset to disk
  4. Optionally call LoRA fine-tuning hook (currently a documented stub)
  5. Return a structured TrainingRunResult — never raises on data errors

Design:
  - Runs synchronously (nightly batch job, not request-path)
  - Returns TrainingRunResult instead of raising so the scheduler can log and
    continue; fatal infrastructure errors are re-raised to the caller.
  - LoRA hook is a clean extension point: swap `_run_lora_training` body when
    the HuggingFace stack is available without touching any other function.
"""

from __future__ import annotations

import json
import logging
import os
import statistics
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from models.plato_log import PlatoLog
from plato.config import PlatoConfig
from plato.schemas import DatasetRecord, TrainingExample, TrainingRunResult
from plato.service import fetch_training_logs, mark_logs_used
from plato.utils import format_training_input, refined_problem_to_json

logger = logging.getLogger("plato.train")


class PlatoTrainer:
    """
    Offline training pipeline for Plato.

    Usage (nightly script / admin endpoint):
        cfg     = PlatoConfig()
        trainer = PlatoTrainer(cfg)
        result  = trainer.run(db_session)
        print(result.model_dump_json(indent=2))
    """

    def __init__(self, cfg: Optional[PlatoConfig] = None) -> None:
        self.cfg = cfg or PlatoConfig()

    # -----------------------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------------------

    def run(self, db: Session) -> TrainingRunResult:
        """
        Full training pipeline.  Returns TrainingRunResult in all cases.
        """
        logger.info("=== Plato Training Run started ===")

        # 1. Fetch rows
        rows = fetch_training_logs(db, min_utility=self.cfg.min_utility_train)
        total_fetched = len(rows)
        logger.info("Fetched %d plato_log rows (min_utility=%.2f).", total_fetched, self.cfg.min_utility_train)

        # 2. Enforce minimum sample count
        if total_fetched < self.cfg.min_logs:
            msg = (
                f"Insufficient training data: {total_fetched} rows fetched, "
                f"minimum required is {self.cfg.min_logs}. "
                f"Skipping training. Re-run after more Brain B sessions."
            )
            logger.warning(msg)
            return TrainingRunResult(
                success=False,
                message=msg,
                total_rows_fetched=total_fetched,
            )

        # 3. Build training examples
        examples, skipped_ids = self._build_examples(rows)
        if not examples:
            msg = "All fetched rows failed validation. No training dataset produced."
            logger.error(msg)
            return TrainingRunResult(
                success=False,
                message=msg,
                total_rows_fetched=total_fetched,
                rows_skipped=len(skipped_ids),
            )

        avg_utility = statistics.mean(ex.weight for ex in examples)
        logger.info(
            "Built %d valid training examples (%d skipped). Average utility: %.4f",
            len(examples), len(skipped_ids), avg_utility,
        )

        # 4. Export dataset to disk
        artifact_path = self._export_dataset(examples)

        # 5. LoRA fine-tuning hook (stub — swap body when HF stack available)
        self._run_lora_training(artifact_path)

        # 6. Mark rows as used in DB
        used_ids = [ex.source_id for ex in examples]
        mark_logs_used(db, used_ids)

        return TrainingRunResult(
            success=True,
            message=(
                f"Dataset exported to {artifact_path}. "
                f"LoRA training hook called (see logs for status). "
                f"{len(examples)} examples, {len(skipped_ids)} skipped."
            ),
            total_rows_fetched=total_fetched,
            rows_skipped=len(skipped_ids),
            training_examples=len(examples),
            average_utility=avg_utility,
            artifact_path=str(artifact_path),
        )

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _build_examples(
        self,
        rows: List[PlatoLog],
    ) -> Tuple[List[TrainingExample], List[uuid.UUID]]:
        """
        Convert PlatoLog ORM rows into TrainingExample objects.
        Malformed rows are logged and skipped; they do not crash the pipeline.
        Returns (valid_examples, skipped_ids).
        """
        valid: List[TrainingExample] = []
        skipped: List[uuid.UUID] = []

        for row in rows:
            try:
                # Validate refined_problem is non-empty JSON
                if not row.refined_problem:
                    raise ValueError("refined_problem is null or empty")

                # Serialise to canonical JSON string (output label)
                output_text = refined_problem_to_json(row.refined_problem)

                # Build the formatted input prompt
                input_text = format_training_input(
                    original_statement=row.original_statement or "",
                    failure_mode=row.failure_mode or "",
                    root_cause=row.root_cause or "",
                )

                ex = TrainingExample(
                    source_id=row.id,
                    input_text=input_text,
                    output_text=output_text,   # model_validator checks JSON validity
                    weight=row.utility_score,
                    topic=row.topic or "",
                    failure_mode=row.failure_mode or "",
                )
                valid.append(ex)

            except Exception as exc:
                logger.warning(
                    "Skipping plato_log id=%s: %s", row.id, exc
                )
                skipped.append(row.id)

        return valid, skipped

    def _export_dataset(self, examples: List[TrainingExample]) -> Path:
        """
        Write the training dataset to a timestamped JSONL file.

        Format: one JSON object per line with fields:
          prompt, completion, weight, metadata
        Compatible with HuggingFace datasets / trl SFTTrainer.
        """
        artifact_dir = Path(self.cfg.artifact_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        outpath = artifact_dir / f"plato_dataset_{timestamp}.jsonl"

        with outpath.open("w", encoding="utf-8") as fh:
            for ex in examples:
                record = DatasetRecord(
                    prompt=ex.input_text,
                    completion=ex.output_text,
                    weight=ex.weight,
                    metadata={
                        "source_id": str(ex.source_id),
                        "topic": ex.topic,
                        "failure_mode": ex.failure_mode,
                    },
                )
                fh.write(record.model_dump_json() + "\n")

        logger.info("Dataset written: %s (%d lines)", outpath, len(examples))
        return outpath

    def _run_lora_training(self, dataset_path: Path) -> None:
        """
        Hook for LoRA / full fine-tuning.

        Current state: STUB — logs intent and exits cleanly.
        To activate real training: replace the body of this method with your
        HuggingFace trl / PEFT training loop.

        Expected signature is stable: receives the JSONL dataset path,
        reads it, and writes adapter weights to self.cfg.artifact_dir/adapters/.

        Example future body:
            from trl import SFTTrainer
            from transformers import AutoModelForCausalLM, AutoTokenizer
            from datasets import load_dataset
            # … load_dataset, define TrainingArguments, run trainer.train()
        """
        logger.info(
            "[LoRA hook] Dataset available at: %s. "
            "Real fine-tuning not yet wired (HuggingFace/PEFT stack not installed). "
            "Export is production-ready; swap this method body to activate LoRA.",
            dataset_path,
        )
        # Intentionally not raising — dataset export is the deliverable today.
