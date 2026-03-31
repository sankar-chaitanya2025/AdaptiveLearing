"""
AdaptLab Stage 8 — Dialogue Engine
Orchestrates Brain A (Qwen3:1.7b) and Brain B (Qwen3:8b) across multi-turn
Socratic dialogue sessions.

Architecture
------------
Brain A (1.7b)  Fast evaluator — binary judgement of student understanding.
Brain B (8b)    Teacher Oracle — generates follow-up questions, bridge
                explanations, and triggers RefinedProblem creation (Stage 7).
"""

from __future__ import annotations

import json
import re
import textwrap
from dataclasses import dataclass, field
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Constants — adjust to match your Ollama setup
# ---------------------------------------------------------------------------

OLLAMA_BASE_URL   = "http://localhost:11434"
BRAIN_A_MODEL     = "qwen3:1.7b"
BRAIN_B_MODEL     = "qwen3:8b"
MAX_TURNS         = 4          # Killswitch threshold (inclusive)
REQUEST_TIMEOUT   = 60.0       # seconds


# ---------------------------------------------------------------------------
# Dataclasses (strict JSON-mapped contracts)
# ---------------------------------------------------------------------------

@dataclass
class BrainAEvaluation:
    """
    Output contract for Brain A's evaluation call.

    Fields
    ------
    understanding_shown : True if the student's text demonstrates the
                          target_insight well enough to close the session.
    confidence          : 0.0 – 1.0 soft score (for logging / analytics).
    reason              : One-sentence justification (for audit trail).
    """
    understanding_shown: bool
    confidence: float
    reason: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BrainAEvaluation":
        return cls(
            understanding_shown=bool(d["understanding_shown"]),
            confidence=float(d.get("confidence", 0.0)),
            reason=str(d.get("reason", "")),
        )


@dataclass
class BrainBQuestion:
    """
    Output contract for Brain B's follow-up question.

    Fields
    ------
    question  : The Socratic question to present to the student.
    hint_level: 0 = no hint, 1 = subtle nudge, 2 = partial reveal.
                Brain B is expected to increase this with each turn.
    """
    question: str
    hint_level: int

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BrainBQuestion":
        return cls(
            question=str(d["question"]),
            hint_level=int(d.get("hint_level", 0)),
        )


@dataclass
class BrainBBridge:
    """
    Output contract for Brain B's 'Bridge Explanation' (killswitch turn).

    Fields
    ------
    explanation    : Direct explanation of the concept (no longer Socratic).
    refined_prompt : Seed prompt for Stage 7's RefinedProblem generation.
                     Pass this straight into your existing Stage 7 pipeline.
    """
    explanation: str
    refined_prompt: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BrainBBridge":
        return cls(
            explanation=str(d["explanation"]),
            refined_prompt=str(d["refined_prompt"]),
        )


@dataclass
class DialogueTurnResult:
    """
    The unified response object returned to the API layer after one turn.

    Fields
    ------
    session_id         : Echoed back for convenience.
    status             : "open" | "resolved" | "exhausted"
    tutor_message      : The text to display to the student.
    understanding_shown: Brain A's binary verdict.
    turn_count         : Updated turn counter.
    refined_prompt     : Only populated on the killswitch turn (exhausted).
    next_problem       : Only populated when status == "resolved".
    """
    session_id: int
    status: str
    tutor_message: str
    understanding_shown: bool
    turn_count: int
    refined_prompt: str = ""
    next_problem: str   = ""


# ---------------------------------------------------------------------------
# Low-level LLM helpers
# ---------------------------------------------------------------------------

def _strip_thinking(raw: str) -> str:
    """Remove <think>…</think> blocks emitted by Qwen3 reasoning mode."""
    return re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()


def _extract_json(text: str) -> dict[str, Any]:
    """
    Robustly extract a JSON object from a model response that may contain
    markdown fences or surrounding prose.
    """
    # Strip thinking blocks first
    text = _strip_thinking(text)

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find the first {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())

    raise ValueError(f"No valid JSON found in model response:\n{text[:500]}")


async def _ollama_generate(
    model: str,
    prompt: str,
    system: str = "",
    *,
    client: httpx.AsyncClient,
) -> str:
    """
    Call Ollama's /api/generate endpoint and return the full response text.
    Uses streaming=False for simplicity; swap to streaming if you need it.
    """
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,   # low temp for deterministic JSON output
            "num_predict": 512,
        },
    }
    if system:
        payload["system"] = system

    resp = await client.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["response"]


# ---------------------------------------------------------------------------
# Brain A — fast evaluator
# ---------------------------------------------------------------------------

_BRAIN_A_SYSTEM = textwrap.dedent("""\
    You are a strict but fair learning evaluator.
    You will receive:
      - target_insight : the one conceptual understanding a student must show.
      - student_text   : the student's latest free-text response.

    Your job: decide whether the student's response *demonstrates* the
    target_insight. Be strict — parroting keywords is not enough.

    Reply ONLY with valid JSON, no prose, no markdown fences:
    {
      "understanding_shown": true | false,
      "confidence": 0.0 – 1.0,
      "reason": "<one sentence>"
    }
""")


async def _brain_a_evaluate(
    target_insight: str,
    student_text: str,
    *,
    client: httpx.AsyncClient,
) -> BrainAEvaluation:
    prompt = json.dumps({
        "target_insight": target_insight,
        "student_text": student_text,
    }, ensure_ascii=False)

    raw = await _ollama_generate(
        BRAIN_A_MODEL, prompt, system=_BRAIN_A_SYSTEM, client=client
    )
    return BrainAEvaluation.from_dict(_extract_json(raw))


# ---------------------------------------------------------------------------
# Brain B — Socratic question generator
# ---------------------------------------------------------------------------

_BRAIN_B_QUESTION_SYSTEM = textwrap.dedent("""\
    You are a Socratic tutor (Teacher Oracle).
    You will receive:
      - root_cause      : the conceptual gap the student has.
      - target_insight  : the understanding they need to reach.
      - history         : the conversation so far (list of {role, content}).
      - turn_count      : how many student turns have elapsed (0-indexed).

    Generate a single Socratic question that nudges the student one step
    closer to the target_insight WITHOUT revealing the answer directly.
    Scale hint_level with turn_count: 0 = pure Socratic, 1 = subtle nudge,
    2 = partial reveal.

    Reply ONLY with valid JSON:
    {
      "question": "<your follow-up question>",
      "hint_level": 0 | 1 | 2
    }
""")


async def _brain_b_next_question(
    root_cause: str,
    target_insight: str,
    history: list[dict],
    turn_count: int,
    *,
    client: httpx.AsyncClient,
) -> BrainBQuestion:
    prompt = json.dumps({
        "root_cause": root_cause,
        "target_insight": target_insight,
        "history": history,
        "turn_count": turn_count,
    }, ensure_ascii=False)

    raw = await _ollama_generate(
        BRAIN_B_MODEL, prompt, system=_BRAIN_B_QUESTION_SYSTEM, client=client
    )
    return BrainBQuestion.from_dict(_extract_json(raw))


# ---------------------------------------------------------------------------
# Brain B — killswitch bridge explanation
# ---------------------------------------------------------------------------

_BRAIN_B_BRIDGE_SYSTEM = textwrap.dedent("""\
    You are a Socratic tutor who has exhausted the dialogue loop.
    The student did not reach the target insight after 4 attempts.

    You will receive:
      - root_cause      : the conceptual gap.
      - target_insight  : what they needed to understand.
      - history         : the full conversation transcript.

    Provide:
    1. A clear, direct explanation of the concept (no longer Socratic).
    2. A `refined_prompt` — a concise seed (≤ 80 words) for the problem
       generator that will create a simpler practice problem targeting
       the same root_cause.

    Reply ONLY with valid JSON:
    {
      "explanation": "<direct explanation>",
      "refined_prompt": "<seed for the problem generator>"
    }
""")


async def _brain_b_bridge(
    root_cause: str,
    target_insight: str,
    history: list[dict],
    *,
    client: httpx.AsyncClient,
) -> BrainBBridge:
    prompt = json.dumps({
        "root_cause": root_cause,
        "target_insight": target_insight,
        "history": history,
    }, ensure_ascii=False)

    raw = await _ollama_generate(
        BRAIN_B_MODEL, prompt, system=_BRAIN_B_BRIDGE_SYSTEM, client=client
    )
    return BrainBBridge.from_dict(_extract_json(raw))


# ---------------------------------------------------------------------------
# Brain B — "next problem" after resolution
# ---------------------------------------------------------------------------

_BRAIN_B_NEXT_PROBLEM_SYSTEM = textwrap.dedent("""\
    The student has successfully understood the target concept.
    You will receive:
      - root_cause     : the gap they just overcame.
      - target_insight : what they now understand.

    Generate a short, encouraging transition message and a `next_problem_seed`
    (≤ 80 words) for the problem generator to create a slightly harder
    follow-up problem that builds on the insight.

    Reply ONLY with valid JSON:
    {
      "transition_message": "<encouraging 1-2 sentence message>",
      "next_problem_seed": "<seed for the problem generator>"
    }
""")


async def _brain_b_next_problem(
    root_cause: str,
    target_insight: str,
    *,
    client: httpx.AsyncClient,
) -> dict[str, str]:
    prompt = json.dumps({
        "root_cause": root_cause,
        "target_insight": target_insight,
    }, ensure_ascii=False)

    raw = await _ollama_generate(
        BRAIN_B_MODEL, prompt, system=_BRAIN_B_NEXT_PROBLEM_SYSTEM, client=client
    )
    return _extract_json(raw)


# ---------------------------------------------------------------------------
# DialogueManager — public interface
# ---------------------------------------------------------------------------

class DialogueManager:
    """
    Orchestrates one turn of the Socratic dialogue loop.

    Usage (inside an async FastAPI endpoint)
    ----------------------------------------
    manager = DialogueManager()
    result  = await manager.process_turn(session, student_text, db)
    """

    async def process_turn(
        self,
        session,           # DialogueSession ORM instance
        student_text: str,
        db,                # SQLAlchemy AsyncSession (or sync Session)
    ) -> DialogueTurnResult:
        """
        Execute one student turn:

        1. Append student message to session history.
        2. Call Brain A to evaluate understanding.
        3a. If understood  → mark RESOLVED, call Brain B for next problem.
        3b. If not & turns remaining → call Brain B for follow-up question.
        3c. If not & turns exhausted  → call Brain B for bridge explanation
            and trigger Stage 7 RefinedProblem seed.
        4. Persist updated session to DB.
        5. Return DialogueTurnResult.
        """
        async with httpx.AsyncClient() as client:
            # ----------------------------------------------------------
            # 1. Record the student's message
            # ----------------------------------------------------------
            session.append_turn("student", student_text)

            # ----------------------------------------------------------
            # 2. Brain A — evaluate understanding
            # ----------------------------------------------------------
            evaluation: BrainAEvaluation = await _brain_a_evaluate(
                target_insight=session.target_insight,
                student_text=student_text,
                client=client,
            )

            # ----------------------------------------------------------
            # 3a. Student understood → RESOLVED
            # ----------------------------------------------------------
            if evaluation.understanding_shown:
                next_data = await _brain_b_next_problem(
                    root_cause=session.root_cause,
                    target_insight=session.target_insight,
                    client=client,
                )
                tutor_msg = next_data.get(
                    "transition_message",
                    "Great work! Let's move on to the next challenge.",
                )
                next_problem = next_data.get("next_problem_seed", "")

                session.append_turn("tutor", tutor_msg)
                session.status = "RESOLVED"   # DialogueStatus.RESOLVED as string OK
                await self._save(session, db)

                return DialogueTurnResult(
                    session_id=session.id,
                    status="resolved",
                    tutor_message=tutor_msg,
                    understanding_shown=True,
                    turn_count=session.turn_count,
                    next_problem=next_problem,
                )

            # ----------------------------------------------------------
            # 3b/3c. Student did NOT understand
            # ----------------------------------------------------------
            current_turns = session.turn_count  # already incremented above

            if current_turns >= MAX_TURNS:
                # -------------------------------------------------------
                # 3c. KILLSWITCH — bridge explanation + Stage 7 seed
                # -------------------------------------------------------
                bridge: BrainBBridge = await _brain_b_bridge(
                    root_cause=session.root_cause,
                    target_insight=session.target_insight,
                    history=list(session.history),
                    client=client,
                )
                tutor_msg = bridge.explanation
                session.append_turn("tutor", tutor_msg)
                session.status = "EXHAUSTED"
                await self._save(session, db)

                return DialogueTurnResult(
                    session_id=session.id,
                    status="exhausted",
                    tutor_message=tutor_msg,
                    understanding_shown=False,
                    turn_count=session.turn_count,
                    refined_prompt=bridge.refined_prompt,
                )

            else:
                # -------------------------------------------------------
                # 3b. Continue dialogue — Brain B follow-up question
                # -------------------------------------------------------
                q: BrainBQuestion = await _brain_b_next_question(
                    root_cause=session.root_cause,
                    target_insight=session.target_insight,
                    history=list(session.history),
                    turn_count=current_turns,
                    client=client,
                )
                tutor_msg = q.question
                session.append_turn("tutor", tutor_msg)
                await self._save(session, db)

                return DialogueTurnResult(
                    session_id=session.id,
                    status="open",
                    tutor_message=tutor_msg,
                    understanding_shown=False,
                    turn_count=session.turn_count,
                )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _save(session, db) -> None:
        """
        Persist the session.  Supports both sync and async SQLAlchemy sessions.
        """
        try:
            db.add(session)
            # Async session
            if hasattr(db, "commit") and asyncio_is_coroutinefunction(db.commit):
                await db.commit()
                await db.refresh(session)
            else:
                db.commit()
                db.refresh(session)
        except Exception:
            try:
                if hasattr(db, "rollback"):
                    await db.rollback() if asyncio_is_coroutinefunction(db.rollback) else db.rollback()
            except Exception:
                pass
            raise


def asyncio_is_coroutinefunction(fn) -> bool:
    import asyncio
    return asyncio.iscoroutinefunction(fn)