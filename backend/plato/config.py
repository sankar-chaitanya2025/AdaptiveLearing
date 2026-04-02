"""
backend/plato/config.py
Stage 9 — Environment-driven Plato configuration.

All settings default to safe values and can be overridden via environment
variables.  Import PlatoConfig wherever pipeline parameters are needed.
"""

import os
from dataclasses import dataclass, field


@dataclass
class PlatoConfig:
    """
    Central config for the Plato offline pipeline.
    All values are read from environment variables at instantiation time so
    that docker-compose env overrides work without code changes.
    """

    # Ollama model identifier for Plato (smaller, offline student model).
    model: str = field(
        default_factory=lambda: os.getenv("PLATO_MODEL", "qwen3:1.7b")
    )

    # Minimum plato_logs rows required before training is attempted.
    min_logs: int = field(
        default_factory=lambda: int(os.getenv("PLATO_MIN_LOGS", "200"))
    )

    # Minimum utility_score for a row to enter the training dataset.
    min_utility_train: float = field(
        default_factory=lambda: float(os.getenv("PLATO_MIN_UTILITY_TRAIN", "0.3"))
    )

    # Minimum utility_score for a generated problem to be inserted.
    min_utility_insert: float = field(
        default_factory=lambda: float(os.getenv("PLATO_MIN_UTILITY_INSERT", "0.6"))
    )

    # Number of variants Plato generates per source problem.
    variants_per_problem: int = field(
        default_factory=lambda: int(os.getenv("PLATO_VARIANTS_PER_PROBLEM", "3"))
    )

    # Gaussian parameters — must match brain_b / zpd.py conventions.
    mu: float = field(
        default_factory=lambda: float(os.getenv("PLATO_MU", "0.5"))
    )
    sigma: float = field(
        default_factory=lambda: float(os.getenv("PLATO_SIGMA", "0.2"))
    )

    # Capability threshold above which a topic is considered "mastered".
    mastered_threshold: float = field(
        default_factory=lambda: float(os.getenv("PLATO_MASTERED_THRESHOLD", "0.75"))
    )

    # Ollama host for generation calls.
    ollama_host: str = field(
        default_factory=lambda: os.getenv("OLLAMA_HOST", "localhost:11434")
    )

    # Filesystem path where training artefacts are saved.
    artifact_dir: str = field(
        default_factory=lambda: os.getenv("PLATO_ARTIFACT_DIR", "plato_artifacts")
    )

    # HTTP timeout (seconds) for Ollama generation calls.
    ollama_timeout: float = field(
        default_factory=lambda: float(os.getenv("PLATO_OLLAMA_TIMEOUT", "120.0"))
    )
