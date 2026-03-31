import httpx
import json
import os
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
    solution: str # Required for Appendix A.3 [cite: 366]
    answer: str   # Required for Appendix A.3 [cite: 366]
    visible_tests: List[Dict]
    hidden_tests: List[Dict]

class BrainB:
    def __init__(self):
        # Default to 'latest' to match your Ollama registry [cite: 57, 58]
        self.model = os.getenv("OLLAMA_MODEL", "qwen3:latest") 
        self.host = os.getenv("OLLAMA_HOST", "localhost:11434")
    
    async def _ollama_chat(self, prompt: str, schema_name: str) -> Dict:
        """Call qwen3:8b with thinking-strip logic """
        # CRITICAL FIX: timeout=None allows 'Thinking Mode' to finish 
        async with httpx.AsyncClient(timeout=None) as client:
            resp = await client.post(f"http://{self.host}/api/generate", json={
                "model": self.model,
                "prompt": f"{prompt}\n\nRespond strictly in valid JSON matching {schema_name}:",
                "stream": False,
                "options": {"temperature": 0.1} # Target deterministic oracle results [cite: 290]
            })
            
            raw = resp.json().get("response", "")
            # Strip CoT tags so json.loads doesn't crash [cite: 377]
            clean = raw.split("</think>")[-1].strip() if "</think>" in raw else raw.strip()
            
            try:
                return json.loads(clean)
            except Exception as e:
                print(f"JSON Parse Error: {e}\nRaw output received: {clean}")
                return {}

    async def full_pipeline(self, problem: Dict, code: str, sandbox: Dict, brain_a: Dict) -> Dict:
        """Stage 7 complete co-evolutionary flow [cite: 11, 315, 384]"""
        # 1. ZPD Routing [cite: 14, 108, 162]
        sq = sandbox.get("visible_passed", 0) / max(sandbox.get("visible_total", 1), 1)
        zpd = zpd_router(sq)
        
        if zpd.zone == "too_difficult":
            return {"status": "too_difficult", "zpd": asdict(zpd)}

        # 2. Classification (Paper A.2 [cite: 315, 371])
        class_prompt = f"Analyze failure in {problem['statement']}\nCode: {code}\nMode: {brain_a['failure_mode']}"
        class_json = await self._ollama_chat(class_prompt, "ClassificationResult")
        
        # Use .get() for safety to prevent attribute errors 
        classification = ClassificationResult(
            gap_type=class_json.get("gap_type", "logic_error"),
            root_cause=class_json.get("root_cause", "Analysis failure"),
            confidence=class_json.get("confidence", 0.0),
            fatigue_detected=class_json.get("fatigue_detected", False),
            prerequisite_gap=class_json.get("prerequisite_gap")
        )

        # 3. Mastered vs Learning Logic [cite: 108, 315]
        if zpd.zone == "mastered":
            # Just refine a harder variant, no dialogue [cite: 108, 391]
            refined = await self._refine(problem, code, classification, "harder")
            return {"status": "mastered", "zpd": asdict(zpd), "refined_problem": asdict(refined)}

        # 4. Socratic Discovery (Learning Zone [cite: 18, 315, 383])
        soc_json = await self._ollama_chat(f"Gap: {classification.root_cause}. Ask Socratic Q.", "SocraticQuestion")
        refined = await self._refine(problem, code, classification, "targeted")

        return {
            "status": "learning",
            "zpd": asdict(zpd),
            "classification": asdict(classification),
            "socratic_question": soc_json.get("question", "What happens in your code here?"),
            "refined_problem": asdict(refined),
            "plato_utility": zpd.utility # Ready for PlatoLog WSFT [cite: 417, 430]
        }

    async def _refine(self, prob: Dict, code: str, res: ClassificationResult, mode: str) -> RefinedProblem:
        """Paper A.3: Teacher refinement function G(q, yfail) [cite: 16, 315, 375]"""
        prompt = f"Create {mode} problem. Original: {prob['statement']}\nFail: {code}\nCause: {res.root_cause}"
        ref_json = await self._ollama_chat(prompt, "RefinedProblem")
        
        return RefinedProblem(
            title=ref_json.get("title", "Refined Task"),
            statement=ref_json.get("statement", "New challenge statement"),
            difficulty=ref_json.get("difficulty", 0.5),
            solution=ref_json.get("solution", ""),
            answer=ref_json.get("answer", ""),
            visible_tests=ref_json.get("visible_tests", []),
            hidden_tests=ref_json.get("hidden_tests", [])
        )