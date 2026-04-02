"""
backend/api/plato_admin.py
Stage 9 — Admin HTTP endpoints for the Plato pipeline.

These endpoints are for OPERATOR USE ONLY.  They should be protected
by API key middleware or restricted network access before production deploy.

Routes:
    POST /admin/plato/train    — trigger training dataset export
    POST /admin/plato/generate — trigger offline generation cycle
    GET  /admin/plato/status   — last run summary (reads from artifacts dir)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from plato.config import PlatoConfig
from plato.generate import PlatoGenerator
from plato.train import PlatoTrainer

logger = logging.getLogger("plato.admin")

router = APIRouter(prefix="/admin/plato", tags=["plato-admin"])

# ---------------------------------------------------------------------------
# Simple API-key guard — set PLATO_ADMIN_KEY in env.  If unset, all calls
# pass through (dev mode).  Replace with OAuth/JWT in production.
# ---------------------------------------------------------------------------

ADMIN_KEY = os.getenv("PLATO_ADMIN_KEY", "")


def _check_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    if ADMIN_KEY and x_api_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Api-Key header.")


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class TrainResponse(BaseModel):
    success: bool
    message: str
    training_examples: int = 0
    average_utility: float = 0.0
    artifact_path: Optional[str] = None


class GenerateRequest(BaseModel):
    topic_filter: Optional[str] = None


class GenerateResponse(BaseModel):
    source_problems_processed: int
    total_accepted: int
    total_rejected: int
    inserted_ids: list[str]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/train", response_model=TrainResponse, dependencies=[Depends(_check_key)])
def trigger_training(db: Session = Depends(get_db)) -> TrainResponse:
    """
    Synchronously run the Plato WSFT dataset preparation pipeline.
    Returns the training result; may take several seconds depending on DB size.
    """
    cfg = PlatoConfig()
    trainer = PlatoTrainer(cfg)

    try:
        result = trainer.run(db)
    except Exception as exc:
        logger.exception("Training pipeline raised: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return TrainResponse(
        success=result.success,
        message=result.message,
        training_examples=result.training_examples,
        average_utility=result.average_utility,
        artifact_path=result.artifact_path,
    )


@router.post("/generate", response_model=GenerateResponse, dependencies=[Depends(_check_key)])
async def trigger_generation(
    body: GenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> GenerateResponse:
    """
    Run the Plato offline generation cycle.  Ollama calls are async;
    this endpoint awaits completion and returns a summary.

    For very large problem banks, run via the CLI script instead.
    """
    cfg = PlatoConfig()
    generator = PlatoGenerator(cfg)

    try:
        results = await generator.run(db_override=db, topic_filter=body.topic_filter)
    except Exception as exc:
        logger.exception("Generation pipeline raised: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    all_ids = [iid for r in results for iid in r.inserted_ids]
    return GenerateResponse(
        source_problems_processed=len(results),
        total_accepted=sum(r.candidates_accepted for r in results),
        total_rejected=sum(r.candidates_rejected for r in results),
        inserted_ids=all_ids,
    )


@router.get("/status", dependencies=[Depends(_check_key)])
def pipeline_status() -> dict:
    """
    Return metadata about the most recent training artefact on disk.
    Useful for health-checking the nightly pipeline from a monitoring tool.
    """
    artifact_dir = Path(os.getenv("PLATO_ARTIFACT_DIR", "plato_artifacts"))
    if not artifact_dir.exists():
        return {"status": "no_artifacts", "artifact_dir": str(artifact_dir)}

    files = sorted(artifact_dir.glob("plato_dataset_*.jsonl"), reverse=True)
    if not files:
        return {"status": "no_datasets", "artifact_dir": str(artifact_dir)}

    latest = files[0]
    line_count = sum(1 for _ in latest.open(encoding="utf-8"))
    return {
        "status": "ok",
        "latest_dataset": str(latest),
        "examples": line_count,
        "all_datasets": [str(f) for f in files],
    }
