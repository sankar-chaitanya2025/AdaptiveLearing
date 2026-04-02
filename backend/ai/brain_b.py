import httpx
import json
import os
import asyncio  # Crucial for parallel execution
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from .zpd import zpd_router

@dataclass
class ClassificationResult:
    gap_type: str
    root_cause: str
    confidence: float
    fatigue_detected: bool
    prerequisite_gap: Optional[str]

@dataclass
class SocraticQuestion:
    question: str

@dataclass
class RefinedProblem:
    title: str
    statement: str
    difficulty: float
    solution: str 
    answer: str   
    visible_tests: List[Dict]
    hidden_tests: List[Dict]

class BrainB:
    def __init__(self):
        self.model = os.getenv("OLLAMA_MODEL", "qwen3:8b") 
        self.host = os.getenv("OLLAMA_HOST", "localhost:11434")
    
    async def _ollama_chat(self, prompt: str, schema_name: str) -> Dict:
        """
        Call qwen3:8b with a 120s safety timeout.
        Includes robust JSON extraction and error handling.
        """
        # Safety Fix: 120.0s timeout prevents 'Zombie' workers if Ollama hangs
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                resp = await client.post(f"http://{self.host}/api/generate", json={
                    "model": self.model,
                    "prompt": f"{prompt}\n\nRespond strictly in valid JSON matching the schema {schema_name}. Do not explain, just return JSON.",
                    "stream": False,
                    "options": {"temperature": 0.2}
                })
                
                resp.raise_for_status()
                raw = resp.json().get("response", "")
                
                # Strip thinking tags and markdown formatting
                clean = raw.split("</think>")[-1].strip() if "</think>" in raw else raw.strip()
                clean = clean.replace("```json", "").replace("```", "").strip()
                
                return json.loads(clean)

            except httpx.TimeoutException:
                print(f"Ollama Timeout: BrainB request exceeded 120s safety limit.")
                # Fallback to keep the user experience alive
                if schema_name == "SocraticQuestion":
                    return {"question": "I see what you're trying to do there—if you look at your logic again, what is the value of your variable at that specific moment?"}
                return {}
            except Exception as e:
                print(f"Critical BrainB Error: {e}")
                return {}

    async def full_pipeline(self, problem: Dict, code: str, sandbox: Dict, brain_a: Dict) -> Dict:
        """Stage 7 & 8: High-Context, Parallelized Co-evolutionary flow."""
        
        # 1. ZPD Routing
        sq = sandbox.get("visible_passed", 0) / max(sandbox.get("visible_total", 1), 1)
        zpd = zpd_router(sq)
        
        if zpd.zone == "too_difficult":
            return {"status": "too_difficult", "zpd": asdict(zpd)}

        # 2. Classification (Context-Rich Analysis)
        class_prompt = f"""
        TASK: Analyze a student's logic failure.
        PROBLEM: {problem.get('statement', 'Unknown')}
        STUDENT CODE:
        {code}
        FAILURE MODE: {brain_a.get('failure_mode', 'Unknown Error')}
        Identify the specific conceptual gap (root_cause) and classify it.
        """
        class_json = await self._ollama_chat(class_prompt, "ClassificationResult")
        
        classification = ClassificationResult(
            gap_type=class_json.get("gap_type", "logic_error"),
            root_cause=class_json.get("root_cause", "Analysis failure"),
            confidence=class_json.get("confidence", 0.0),
            fatigue_detected=class_json.get("fatigue_detected", False),
            prerequisite_gap=class_json.get("prerequisite_gap")
        )

        # 3. Mastered Zone (Efficiency Path)
        if zpd.zone == "mastered":
            refined = await self._refine(problem, code, classification, "harder")
            return {"status": "mastered", "zpd": asdict(zpd), "refined_problem": asdict(refined)}

        # 4. Socratic Discovery (PARALLEL EXECUTION)
        # Simultaneously generate the question and the refined problem to minimize latency.
        socratic_prompt = f"""
        TASK: You are Socrates. Lead the student to realize their error WITHOUT giving the answer.
        PROBLEM: {problem.get('statement')}
        STUDENT CODE:
        {code}
        IDENTIFIED GAP: {classification.root_cause}
        TARGET INSIGHT: Fix the {classification.gap_type} logic.
        
        RULE: Ask ONE piercing question about their specific lines of code.
        """

        # Dispatch both tasks to the event loop
        soc_task = self._ollama_chat(socratic_prompt, "SocraticQuestion")
        refine_task = self._refine(problem, code, classification, "targeted")

        # Wait for both in parallel (Total time = time of slowest single call)
        soc_json, refined = await asyncio.gather(soc_task, refine_task)

        return {
            "status": "learning",
            "zpd": asdict(zpd),
            "classification": asdict(classification),
            "socratic_question": soc_json.get("question", "What do you think happens to your logic when that condition is met?"),
            "refined_problem": asdict(refined),
            "plato_utility": zpd.utility 
        }

    async def _refine(self, prob: Dict, code: str, res: ClassificationResult, mode: str) -> RefinedProblem:
        """Teacher refinement function G(q, yfail)."""
        prompt = f"""
        GENERATE A {mode.upper()} PROBLEM VARIANT.
        Original Task: {prob.get('statement')}
        Student's Failed Logic: {code}
        Root Cause of Failure: {res.root_cause}
        
        The new problem MUST specifically target the identified logic gap.
        """
        ref_json = await self._ollama_chat(prompt, "RefinedProblem")
        
        return RefinedProblem(
            title=ref_json.get("title", "Updated Challenge"),
            statement=ref_json.get("statement", "Please address the logic gap from the previous attempt."),
            difficulty=ref_json.get("difficulty", 0.5),
            solution=ref_json.get("solution", ""),
            answer=ref_json.get("answer", ""),
            visible_tests=ref_json.get("visible_tests", []),
            hidden_tests=ref_json.get("hidden_tests", [])
        )