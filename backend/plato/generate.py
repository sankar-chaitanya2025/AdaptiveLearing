"""
backend/plato/generate.py
Stage 9 — Plato Offline Generation Pipeline.

Responsibilities:
  1. Select source problems from mastered-zone and/or failure-pattern buckets
  2. Call Plato (Ollama) to generate N variants per source problem
  3. Parse, validate and score each candidate with Gaussian utility
  4. Insert only high-utility, non-duplicate problems into the problem bank
  5. Mark inserted rows with created_by='plato'

This pipeline MUST run offline / nightly — never on the live student request
path.  Trigger it via the admin script or a scheduler.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Set

import httpx

from database import SessionLocal
from models.problem import Problem
from plato.config import PlatoConfig
from plato.schemas import CandidateProblem, GenerationResult
from plato.service import (
    existing_hashes,
    fetch_failure_pattern_problems,
    fetch_mastered_problems,
    insert_plato_problem,
)
from plato.utils import (
    content_hash,
    extract_json,
    gaussian_utility,
    validate_candidate,
)

logger = logging.getLogger("plato.generate")


class PlatoGenerator:
    """
    Offline problem-generation pipeline driven by Plato (smaller Ollama model).

    Usage (admin script / APScheduler):
        cfg       = PlatoConfig()
        generator = PlatoGenerator(cfg)
        results   = asyncio.run(generator.run())
        for r in results:
            print(r.model_dump_json(indent=2))
    """

    def __init__(self, cfg: Optional[PlatoConfig] = None) -> None:
        self.cfg = cfg or PlatoConfig()

    # -----------------------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------------------

    async def run(
        self,
        db_override=None,
        topic_filter: Optional[str] = None,
    ) -> List[GenerationResult]:
        """
        Full generation cycle.  Opens its own DB session unless db_override
        is provided (useful for integration tests).

        Returns a list of GenerationResult — one per source problem attempted.
        """
        db = db_override or SessionLocal()
        close_db = db_override is None
        results: List[GenerationResult] = []

        try:
            # Pre-compute existing content hashes for dedup
            seen_hashes: Set[str] = existing_hashes(db)
            logger.info(
                "Generation run started. Existing problem hashes loaded: %d",
                len(seen_hashes),
            )

            # Collect source problems from both buckets
            mastered = fetch_mastered_problems(db, self.cfg, topic=topic_filter)
            failure_pattern = fetch_failure_pattern_problems(db, self.cfg)

            # De-duplicate across buckets by problem ID
            combined: Dict[uuid.UUID, Problem] = {}
            for p in mastered:
                combined[p.id] = p
            for p in failure_pattern:
                combined[p.id] = p

            source_problems = list(combined.values())
            logger.info(
                "Source problems: %d mastered + %d failure-pattern (deduplicated to %d).",
                len(mastered), len(failure_pattern), len(source_problems),
            )

            if not source_problems:
                logger.warning(
                    "No source problems found. "
                    "Ensure capability vectors or problem bank are populated."
                )
                return results

            # Generate variants for each source problem
            for prob in source_problems:
                result = await self._generate_for_problem(db, prob, seen_hashes)
                results.append(result)
                # Update seen_hashes so variants of the same source don't
                # duplicate each other within this run.
                # (inserted_ids gives us IDs, but we track by content hash)

        finally:
            if close_db:
                db.close()

        total_accepted = sum(r.candidates_accepted for r in results)
        logger.info(
            "=== Generation run complete: %d source problems, %d problems inserted. ===",
            len(results),
            total_accepted,
        )
        return results

    # -----------------------------------------------------------------------
    # Per-problem generation
    # -----------------------------------------------------------------------

    async def _generate_for_problem(
        self,
        db,
        source: Problem,
        seen_hashes: Set[str],
    ) -> GenerationResult:
        """
        Generate cfg.variants_per_problem candidates for one source problem.
        Accepts candidates that pass validation and exceed min_utility_insert.
        """
        result = GenerationResult(
            source_problem_id=source.id,
            topic=source.topic,
            source_difficulty=source.difficulty,
            candidates_generated=0,
            candidates_accepted=0,
            candidates_rejected=0,
        )

        # Determine generation mode based on source difficulty
        if source.difficulty >= self.cfg.mastered_threshold:
            mode = "harder"
            target_sq = min(source.difficulty + 0.15, 1.0)
        else:
            mode = "targeted"
            target_sq = source.difficulty

        for _ in range(self.cfg.variants_per_problem):
            result.candidates_generated += 1
            candidate_dict, error = await self._call_ollama(source, mode)

            if error or candidate_dict is None:
                result.candidates_rejected += 1
                result.errors.append(error or "Ollama returned None")
                continue

            # Inject topic from source (Plato may omit it)
            if not candidate_dict.get("topic"):
                candidate_dict["topic"] = source.topic

            # Structural validation
            ok, reason = validate_candidate(candidate_dict)
            if not ok:
                result.candidates_rejected += 1
                result.errors.append(f"Validation failed: {reason}")
                logger.debug("Candidate rejected (%s): %s", reason, candidate_dict.get("title", "?"))
                continue

            # Deduplication
            chash = content_hash(candidate_dict["statement"])
            if chash in seen_hashes:
                result.candidates_rejected += 1
                result.errors.append("Duplicate content hash — skipped")
                logger.debug("Duplicate candidate skipped: %s", candidate_dict.get("title", "?"))
                continue

            # Gaussian utility scoring against target capability level
            utility = gaussian_utility(target_sq, mu=self.cfg.mu, sigma=self.cfg.sigma)
            candidate_dict["utility_score"] = utility

            if utility < self.cfg.min_utility_insert:
                result.candidates_rejected += 1
                result.errors.append(
                    f"Utility {utility:.3f} below threshold {self.cfg.min_utility_insert}"
                )
                logger.debug(
                    "Candidate utility %.3f < threshold %.3f — rejected.",
                    utility, self.cfg.min_utility_insert,
                )
                continue

            # Insert into problem bank
            inserted = insert_plato_problem(db, candidate_dict, utility)
            if inserted is not None:
                result.candidates_accepted += 1
                result.inserted_ids.append(str(inserted.id))
                seen_hashes.add(chash)  # Prevent intra-run duplicates
            else:
                result.candidates_rejected += 1
                result.errors.append("DB insert failed — see service logs")

        logger.info(
            "Problem %s [%s]: generated=%d accepted=%d rejected=%d",
            source.id, source.topic,
            result.candidates_generated,
            result.candidates_accepted,
            result.candidates_rejected,
        )
        return result

    # -----------------------------------------------------------------------
    # Ollama call
    # -----------------------------------------------------------------------

    async def _call_ollama(
        self,
        source: Problem,
        mode: str,
    ) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Ask Plato to generate a problem variant.
        Returns (parsed_dict, None) on success, (None, error_str) on failure.
        """
        prompt = self._build_prompt(source, mode)
        url = f"http://{self.cfg.ollama_host}/api/generate"

        try:
            async with httpx.AsyncClient(timeout=self.cfg.ollama_timeout) as client:
                resp = await client.post(url, json={
                    "model": self.cfg.model,
                    "prompt": (
                        f"{prompt}\n\n"
                        "Respond ONLY with valid JSON. "
                        "Do not include explanations, markdown, or code fences."
                    ),
                    "stream": False,
                    "options": {"temperature": 0.7},  # Higher temp for variety
                })
                resp.raise_for_status()
                raw = resp.json().get("response", "")
                parsed = extract_json(raw)
                if parsed is None:
                    return None, f"JSON extraction failed. Raw snippet: {raw[:200]!r}"
                return parsed, None

        except httpx.TimeoutException:
            return None, f"Ollama timeout after {self.cfg.ollama_timeout}s"
        except httpx.HTTPStatusError as exc:
            return None, f"Ollama HTTP error {exc.response.status_code}"
        except Exception as exc:
            return None, f"Unexpected Ollama error: {exc}"

    # -----------------------------------------------------------------------
    # Prompt builder
    # -----------------------------------------------------------------------

    @staticmethod
    def _build_prompt(source: Problem, mode: str) -> str:
        """
        Build the generation prompt.  Mode is 'harder' or 'targeted'.
        Output schema mirrors RefinedProblem from brain_b.py.
        """
        mode_instruction = (
            "Generate a HARDER variant of this problem. "
            "The new problem must require more advanced reasoning or additional edge-case handling."
            if mode == "harder"
            else
            "Generate a TARGETED variant of this problem that specifically addresses "
            "common student misconceptions for this topic and difficulty level."
        )

        return f"""You are Plato, an educational problem generator.

SOURCE PROBLEM:
Title: {source.title}
Topic: {source.topic}
Difficulty: {source.difficulty}
Statement: {source.statement}

TASK: {mode_instruction}

Return a single JSON object with EXACTLY these fields:
{{
  "title": "<short descriptive title>",
  "statement": "<full problem statement, at least 30 words>",
  "difficulty": <float 0.0-1.0>,
  "solution": "<reference solution code or explanation>",
  "answer": "<expected output or answer>",
  "visible_tests": [{{"input": "<input>", "expected": "<output>"}}],
  "hidden_tests": [{{"input": "<input>", "expected": "<output>"}}],
  "topic": "{source.topic}",
  "prerequisite_topics": []
}}"""
