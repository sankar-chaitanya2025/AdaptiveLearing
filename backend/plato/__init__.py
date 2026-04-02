"""
backend/plato/__init__.py
Stage 9 — Plato Offline Generator Pipeline.

Public re-exports so callers can do:
    from plato import PlatoTrainer, PlatoGenerator, PlatoConfig
"""

from .config import PlatoConfig
from .schemas import TrainingExample, CandidateProblem, GenerationResult, TrainingRunResult
from .train import PlatoTrainer
from .generate import PlatoGenerator

__all__ = [
    "PlatoConfig",
    "TrainingExample",
    "CandidateProblem",
    "GenerationResult",
    "TrainingRunResult",
    "PlatoTrainer",
    "PlatoGenerator",
]
