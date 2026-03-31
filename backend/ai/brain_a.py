"""Brain A: LLM-based submission evaluator using Ollama (qwen3:1.7b)."""
from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass

import httpx

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://host.docker.internal:11434")
_GENERATE_URL = f"{OLLAMA_URL}/api/generate"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class BrainAResult:
    score: float
    difficulty_for_student: float
    feedback: str
    call_brain_b: bool
    failure_mode: str


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_prompt(problem, student_vector: dict, code: str, sandbox_result: dict) -> str:
    """Build the evaluation prompt sent to Ollama."""
    score = student_vector.get(problem.topic, 0.0)

    # Derive pass counts from sandbox result lists
    visible_results = sandbox_result.get("visible", {}).get("results", [])
    hidden_results  = sandbox_result.get("hidden",  {}).get("results", [])

    visible_passed = sum(1 for r in visible_results if r.get("passed"))
    visible_total  = len(problem.visible_tests)
    hidden_passed  = sum(1 for r in hidden_results  if r.get("passed"))
    hidden_total   = len(problem.hidden_tests)

    return f"""/no_think
Problem: {problem.statement}
Topic: {problem.topic}
Student capability on this topic: {score:.2f}
Visible tests passed: {visible_passed}/{visible_total}
Hidden tests passed: {hidden_passed}/{hidden_total}
Code submitted:
```python
{code}
```
Return JSON only:
{{"score": float, "difficulty_for_student": float, "feedback": "one sentence", "call_brain_b": bool, "failure_mode": "edge_case|logic_error|off_by_one|timeout|wrong_approach"}}"""


# ---------------------------------------------------------------------------
# Response cleaning
# ---------------------------------------------------------------------------

def _strip_think_blocks(text: str) -> str:
    """Remove <think>...</think> blocks that qwen3 may emit despite /no_think."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _extract_json(text: str) -> dict:
    """Find the first {...} JSON object in text and parse it."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in response")
    return json.loads(match.group())


# ---------------------------------------------------------------------------
# Fallback factory
# ---------------------------------------------------------------------------

def _fallback(hidden_score: float) -> BrainAResult:
    return BrainAResult(
        score=hidden_score,
        difficulty_for_student=0.5,
        feedback="Good attempt. Review edge cases.",
        call_brain_b=False,
        failure_mode="edge_case",
    )


# ---------------------------------------------------------------------------
# Main async evaluator
# ---------------------------------------------------------------------------

async def evaluate_submission(
    problem,
    student_vector: dict,
    code: str,
    sandbox_result: dict,
) -> BrainAResult:
    """Call Ollama to evaluate a student submission.

    Always returns a BrainAResult — never raises.
    sandbox_result must have keys: "hidden" -> {"score": float, "results": list}
                                   "visible" -> {"score": float, "results": list}
    """
    hidden_score: float = sandbox_result.get("hidden", {}).get("score", 0.0)

    prompt = build_prompt(problem, student_vector, code, sandbox_result)

    payload = {
        "model": "qwen3:1.7b",
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 300,
        },
        "think": False,
    }

    last_exception: Exception | None = None

    for attempt in range(2):  # up to 2 attempts (1 retry)
        if attempt > 0:
            await asyncio.sleep(1)
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(_GENERATE_URL, json=payload)
                resp.raise_for_status()
                raw = resp.json().get("response", "")

            cleaned = _strip_think_blocks(raw)
            data = _extract_json(cleaned)

            return BrainAResult(
                score=float(data.get("score", hidden_score)),
                difficulty_for_student=float(data.get("difficulty_for_student", 0.5)),
                feedback=str(data.get("feedback", "Good attempt. Review edge cases.")),
                call_brain_b=bool(data.get("call_brain_b", False)),
                failure_mode=str(data.get("failure_mode", "edge_case")),
            )

        except (httpx.TimeoutException, json.JSONDecodeError, ValueError) as exc:
            last_exception = exc
            continue  # retry

        except Exception as exc:  # noqa: BLE001
            last_exception = exc
            break  # non-retryable

    # All attempts exhausted — return safe fallback
    return _fallback(hidden_score)
